import json
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.decision_memory import (
    DecisionMemoryError,
    list_memory_reviews,
    list_visible_memory_candidates,
    project_memory_candidates,
    reconcile_memory_candidates,
    review_memory_candidate,
)
from app.decision_memory_models import (
    DecisionMemoryCandidate,
    DecisionMemoryExtraction,
    MemoryKind,
    MemoryReviewAction,
    MemoryState,
)
from app.models import (
    CanonicalEvent,
    IntegrationConnection,
    IntegrationStatus,
    Membership,
    MembershipRole,
    Organization,
    RawEvent,
    ResourceAccessLevel,
    ResourceGrant,
    SlackChannelAuthorization,
    User,
)
from app.search import project_search_document
from app.search_models import SearchDocument
from app.work_graph import project_canonical_event


def _seed(db: Session, suffix: str):
    owner = User(email=f"owner-memory-{suffix}@example.com")
    member = User(email=f"member-memory-{suffix}@example.com")
    organization = Organization(name=f"Memory Org {suffix}", slug=f"memory-{suffix}")
    db.add_all([owner, member, organization])
    db.flush()
    db.add_all(
        [
            Membership(
                organization_id=organization.id,
                user_id=owner.id,
                role=MembershipRole.OWNER,
            ),
            Membership(
                organization_id=organization.id,
                user_id=member.id,
                role=MembershipRole.MEMBER,
            ),
        ]
    )
    db.commit()
    return organization, owner, member


def _document(
    db: Session,
    *,
    organization: Organization,
    owner: User,
    provider: str,
    visibility: str,
    object_id: str,
    text: str,
    channel_id: str | None = None,
    repository_id: str | None = None,
) -> tuple[CanonicalEvent, SearchDocument]:
    connection = IntegrationConnection(
        organization_id=organization.id,
        provider=provider,
        external_account_id=f"{provider}-memory-{object_id}",
        display_name=f"{provider} memory",
        scopes=[],
        provider_metadata={},
        created_by_user_id=owner.id,
    )
    db.add(connection)
    db.flush()

    if provider == "slack":
        payload = {
            "event": {
                "channel": channel_id,
                "type": "message",
                "text": text,
                "ts": "1.0",
                "user": "U1",
            }
        }
    else:
        payload = {
            "action": "opened",
            "repository": {
                "id": int(repository_id or "1"),
                "full_name": "acme/repo",
            },
            "pull_request": {
                "id": 1,
                "title": text,
                "body": text,
            },
        }
    source_acl = (
        [f"github:repository:{repository_id}"]
        if repository_id is not None and visibility != "public_repository"
        else []
    )
    raw = RawEvent(
        organization_id=organization.id,
        integration_connection_id=connection.id,
        provider=provider,
        source_event_id=f"memory-{object_id}",
        source_event_type="message" if provider == "slack" else "pull_request",
        delivery_kind="webhook",
        source_timestamp=datetime.now(UTC),
        content_type="application/json",
        payload_sha256="b" * 64,
        raw_payload=json.dumps(payload).encode(),
        source_visibility=visibility,
        source_acl=source_acl,
    )
    db.add(raw)
    db.flush()
    event = CanonicalEvent(
        organization_id=organization.id,
        raw_event_id=raw.id,
        integration_connection_id=connection.id,
        schema_version=1,
        event_type="message.created" if provider == "slack" else "pull_request.opened",
        action="created" if provider == "slack" else "opened",
        actor_type=f"{provider}_user",
        actor_external_id="U1",
        actor_display_name="User",
        object_type="message" if provider == "slack" else "pull_request",
        object_external_id=object_id,
        object_display_name=text,
        source_provider=provider,
        source_event_id=raw.source_event_id,
        source_event_type=raw.source_event_type,
        occurred_at=datetime.now(UTC),
        source_visibility=visibility,
        source_acl=source_acl,
        provenance={"raw_event_id": str(raw.id)},
        event_metadata={
            "channel_id": channel_id,
            "repository_id": repository_id,
            "repository": "acme/repo" if repository_id else None,
            "text": text if provider == "slack" else None,
        },
    )
    db.add(event)
    db.commit()
    project_canonical_event(db, event)
    document = project_search_document(db, event)
    return event, document


def test_explicit_markers_create_only_candidates_and_projection_is_idempotent(
    db_session: Session,
) -> None:
    organization, owner, _ = _seed(db_session, "explicit")
    _, document = _document(
        db_session,
        organization=organization,
        owner=owner,
        provider="github",
        visibility="public_repository",
        object_id="PR-1",
        text=(
            "Decision: use PostgreSQL for the primary store. "
            "We are blocked by missing production credentials. "
            "Redis might be useful later."
        ),
        repository_id="11",
    )

    first = project_memory_candidates(db_session, document)
    second = project_memory_candidates(db_session, document)

    assert first.processed is True
    assert first.created == 2
    assert first.emitted == 2
    assert second.processed is False
    candidates = list(
        db_session.scalars(
            select(DecisionMemoryCandidate).where(
                DecisionMemoryCandidate.organization_id == organization.id
            )
        )
    )
    assert {candidate.kind for candidate in candidates} == {
        MemoryKind.DECISION,
        MemoryKind.BLOCKER,
    }
    assert all(candidate.state == MemoryState.CANDIDATE for candidate in candidates)
    assert all(candidate.confidence >= 0.9 for candidate in candidates)


def test_public_slack_memory_requires_current_channel_authorization(
    db_session: Session,
) -> None:
    organization, owner, member = _seed(db_session, "public-slack")
    event, document = _document(
        db_session,
        organization=organization,
        owner=owner,
        provider="slack",
        visibility="public_channel",
        object_id="C1:1",
        text="Decision: release on Friday",
        channel_id="C1",
    )
    project_memory_candidates(db_session, document)

    assert list_visible_memory_candidates(
        db_session,
        organization_id=organization.id,
        user_id=member.id,
        kind=None,
        state=None,
        limit=20,
    ) == []

    authorization = SlackChannelAuthorization(
        organization_id=organization.id,
        integration_connection_id=event.integration_connection_id,
        channel_id="C1",
        channel_name="general",
        is_private=False,
        member_ids=[],
        authorized_by_user_id=owner.id,
    )
    db_session.add(authorization)
    db_session.commit()
    assert len(
        list_visible_memory_candidates(
            db_session,
            organization_id=organization.id,
            user_id=member.id,
            kind=MemoryKind.DECISION,
            state=None,
            limit=20,
        )
    ) == 1

    db_session.delete(authorization)
    db_session.commit()
    assert list_visible_memory_candidates(
        db_session,
        organization_id=organization.id,
        user_id=member.id,
        kind=None,
        state=None,
        limit=20,
    ) == []


def test_private_github_memory_requires_explicit_grant_even_for_owner(
    db_session: Session,
) -> None:
    organization, owner, _ = _seed(db_session, "private-github")
    _, document = _document(
        db_session,
        organization=organization,
        owner=owner,
        provider="github",
        visibility="private_repository",
        object_id="PR-2",
        text="Blocker: security review is incomplete",
        repository_id="77",
    )
    project_memory_candidates(db_session, document)

    assert list_visible_memory_candidates(
        db_session,
        organization_id=organization.id,
        user_id=owner.id,
        kind=None,
        state=None,
        limit=20,
    ) == []

    db_session.add(
        ResourceGrant(
            organization_id=organization.id,
            resource_type="github.repository",
            resource_id="77",
            user_id=owner.id,
            access=ResourceAccessLevel.READ,
            created_by_user_id=owner.id,
        )
    )
    db_session.commit()
    assert len(
        list_visible_memory_candidates(
            db_session,
            organization_id=organization.id,
            user_id=owner.id,
            kind=MemoryKind.BLOCKER,
            state=None,
            limit=20,
        )
    ) == 1


def test_revocation_and_deletion_hide_memory_without_deleting_audit_state(
    db_session: Session,
) -> None:
    organization, owner, _ = _seed(db_session, "revocation")
    event, document = _document(
        db_session,
        organization=organization,
        owner=owner,
        provider="github",
        visibility="public_repository",
        object_id="PR-3",
        text="Decision: deploy through the release pipeline",
        repository_id="88",
    )
    project_memory_candidates(db_session, document)
    candidate = db_session.scalar(select(DecisionMemoryCandidate))
    assert candidate is not None

    assert len(
        list_visible_memory_candidates(
            db_session,
            organization_id=organization.id,
            user_id=owner.id,
            kind=None,
            state=None,
            limit=20,
        )
    ) == 1

    connection = db_session.get(IntegrationConnection, event.integration_connection_id)
    assert connection is not None
    connection.status = IntegrationStatus.REVOKED
    db_session.commit()
    assert list_visible_memory_candidates(
        db_session,
        organization_id=organization.id,
        user_id=owner.id,
        kind=None,
        state=None,
        limit=20,
    ) == []
    assert db_session.get(DecisionMemoryCandidate, candidate.id) is not None

    connection.status = IntegrationStatus.ACTIVE
    document.is_deleted = True
    db_session.commit()
    assert list_visible_memory_candidates(
        db_session,
        organization_id=organization.id,
        user_id=owner.id,
        kind=None,
        state=None,
        limit=20,
    ) == []
    assert db_session.get(DecisionMemoryCandidate, candidate.id) is not None


def test_human_review_transitions_are_audited_and_invalid_transition_fails(
    db_session: Session,
) -> None:
    organization, owner, _ = _seed(db_session, "review")
    _, document = _document(
        db_session,
        organization=organization,
        owner=owner,
        provider="github",
        visibility="public_repository",
        object_id="PR-4",
        text="Blocker: production database access is missing",
        repository_id="99",
    )
    project_memory_candidates(db_session, document)
    blocker = db_session.scalar(
        select(DecisionMemoryCandidate).where(
            DecisionMemoryCandidate.kind == MemoryKind.BLOCKER
        )
    )
    assert blocker is not None

    confirmed = review_memory_candidate(
        db_session,
        organization_id=organization.id,
        user_id=owner.id,
        candidate_id=blocker.id,
        action=MemoryReviewAction.CONFIRM,
        reason="Verified against the deployment thread",
        summary=None,
    )
    assert confirmed.state == MemoryState.CONFIRMED
    resolved = review_memory_candidate(
        db_session,
        organization_id=organization.id,
        user_id=owner.id,
        candidate_id=blocker.id,
        action=MemoryReviewAction.RESOLVE,
        reason="Database access was granted",
        summary=None,
    )
    assert resolved.state == MemoryState.RESOLVED
    reopened = review_memory_candidate(
        db_session,
        organization_id=organization.id,
        user_id=owner.id,
        candidate_id=blocker.id,
        action=MemoryReviewAction.REOPEN,
        reason="Access was revoked again",
        summary=None,
    )
    assert reopened.state == MemoryState.CONFIRMED
    edited = review_memory_candidate(
        db_session,
        organization_id=organization.id,
        user_id=owner.id,
        candidate_id=blocker.id,
        action=MemoryReviewAction.EDIT,
        reason="Make the blocker specific",
        summary="Production database credentials are unavailable",
    )
    assert edited.summary == "Production database credentials are unavailable"

    reviews = list_memory_reviews(
        db_session,
        organization_id=organization.id,
        user_id=owner.id,
        candidate_id=blocker.id,
    )
    assert reviews is not None
    assert [review.action for review in reviews] == [
        MemoryReviewAction.CONFIRM,
        MemoryReviewAction.RESOLVE,
        MemoryReviewAction.REOPEN,
        MemoryReviewAction.EDIT,
    ]
    assert reviews[-1].previous_summary != reviews[-1].new_summary

    with pytest.raises(DecisionMemoryError, match="not allowed"):
        review_memory_candidate(
            db_session,
            organization_id=organization.id,
            user_id=owner.id,
            candidate_id=blocker.id,
            action=MemoryReviewAction.CONFIRM,
            reason="Already confirmed",
            summary=None,
        )


def test_decisions_cannot_be_resolved_like_blockers(db_session: Session) -> None:
    organization, owner, _ = _seed(db_session, "decision-state")
    _, document = _document(
        db_session,
        organization=organization,
        owner=owner,
        provider="github",
        visibility="public_repository",
        object_id="PR-5",
        text="Decision: use a modular monolith",
        repository_id="100",
    )
    project_memory_candidates(db_session, document)
    decision = db_session.scalar(
        select(DecisionMemoryCandidate).where(
            DecisionMemoryCandidate.kind == MemoryKind.DECISION
        )
    )
    assert decision is not None
    review_memory_candidate(
        db_session,
        organization_id=organization.id,
        user_id=owner.id,
        candidate_id=decision.id,
        action=MemoryReviewAction.CONFIRM,
        reason="Architecture review accepted it",
        summary=None,
    )
    with pytest.raises(DecisionMemoryError, match="not allowed"):
        review_memory_candidate(
            db_session,
            organization_id=organization.id,
            user_id=owner.id,
            candidate_id=decision.id,
            action=MemoryReviewAction.RESOLVE,
            reason="Invalid decision transition",
            summary=None,
        )


def test_cross_tenant_memory_is_not_visible(db_session: Session) -> None:
    organization, owner, _ = _seed(db_session, "tenant-one")
    other_organization, other_owner, _ = _seed(db_session, "tenant-two")
    _, other_document = _document(
        db_session,
        organization=other_organization,
        owner=other_owner,
        provider="github",
        visibility="public_repository",
        object_id="PR-6",
        text="Decision: keep tenant two confidential",
        repository_id="101",
    )
    project_memory_candidates(db_session, other_document)

    assert list_visible_memory_candidates(
        db_session,
        organization_id=organization.id,
        user_id=owner.id,
        kind=None,
        state=None,
        limit=20,
    ) == []


def test_reextraction_supersedes_stale_unreviewed_candidate(db_session: Session) -> None:
    organization, owner, _ = _seed(db_session, "reextract")
    _, document = _document(
        db_session,
        organization=organization,
        owner=owner,
        provider="github",
        visibility="public_repository",
        object_id="PR-7",
        text="Decision: use PostgreSQL",
        repository_id="102",
    )
    project_memory_candidates(db_session, document)
    original = db_session.scalar(select(DecisionMemoryCandidate))
    assert original is not None

    document.title = "Decision: use CockroachDB"
    document.content = "Decision: use CockroachDB"
    db_session.commit()
    result = project_memory_candidates(db_session, document)
    assert result.processed is True
    assert result.created == 1
    db_session.refresh(original)
    assert original.state == MemoryState.SUPERSEDED
    active = list(
        db_session.scalars(
            select(DecisionMemoryCandidate).where(
                DecisionMemoryCandidate.state == MemoryState.CANDIDATE
            )
        )
    )
    assert len(active) == 1
    assert active[0].summary == "use CockroachDB"


def test_reconciliation_records_zero_candidate_documents_once(db_session: Session) -> None:
    organization, owner, _ = _seed(db_session, "zero")
    _document(
        db_session,
        organization=organization,
        owner=owner,
        provider="github",
        visibility="public_repository",
        object_id="PR-8",
        text="Routine status update with no explicit decision or blocker",
        repository_id="103",
    )

    first = reconcile_memory_candidates(
        db_session,
        organization_id=organization.id,
        limit=100,
    )
    second = reconcile_memory_candidates(
        db_session,
        organization_id=organization.id,
        limit=100,
    )
    assert first == (1, 0, 0)
    assert second == (0, 0, 0)
    extraction = db_session.scalar(select(DecisionMemoryExtraction))
    assert extraction is not None
    assert extraction.candidate_count == 0
