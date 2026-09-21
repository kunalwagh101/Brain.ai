import hashlib
import json
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.canonical_events import canonicalize_raw_event
from app.models import (
    CanonicalEvent,
    IntegrationConnection,
    Membership,
    MembershipRole,
    Organization,
    RawEvent,
    ResourceAccessLevel,
    ResourceGrant,
    SlackChannelAuthorization,
    SourceIdentity,
    SourceIdentityState,
    User,
)
from app.search import index_canonical_event, reconcile_search_documents, search_evidence
from app.search_models import SearchDocument
from app.work_graph import project_canonical_event


def _seed_org(db: Session, suffix: str):
    owner = User(email=f"owner-search-{suffix}@example.com")
    member = User(email=f"member-search-{suffix}@example.com")
    organization = Organization(name=f"Search {suffix}", slug=f"search-{suffix}")
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


def _event(
    db: Session,
    *,
    organization: Organization,
    owner: User,
    provider: str,
    visibility: str,
    source_acl: list[str],
    object_id: str,
    title: str,
    metadata: dict[str, object],
    indexed: bool = True,
) -> CanonicalEvent:
    connection = IntegrationConnection(
        organization_id=organization.id,
        provider=provider,
        external_account_id=f"{provider}-{organization.slug}-{object_id}",
        display_name=f"{provider} search fixture",
        scopes=[],
        provider_metadata={},
        created_by_user_id=owner.id,
    )
    db.add(connection)
    db.flush()
    raw_payload = json.dumps({"fixture": object_id}).encode()
    raw = RawEvent(
        organization_id=organization.id,
        integration_connection_id=connection.id,
        provider=provider,
        source_event_id=f"delivery-{object_id}",
        source_event_type="message" if provider == "slack" else "pull_request",
        delivery_kind="webhook",
        source_timestamp=datetime.now(UTC),
        content_type="application/json",
        payload_sha256=hashlib.sha256(raw_payload).hexdigest(),
        raw_payload=raw_payload,
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
        actor_external_id=f"actor-{object_id}",
        actor_display_name="Fixture Actor",
        object_type="message" if provider == "slack" else "pull_request",
        object_external_id=object_id,
        object_display_name=title,
        source_provider=provider,
        source_event_id=raw.source_event_id,
        source_event_type=raw.source_event_type,
        occurred_at=datetime.now(UTC),
        source_visibility=visibility,
        source_acl=source_acl,
        provenance={
            "raw_event_id": str(raw.id),
            "payload_sha256": raw.payload_sha256,
        },
        event_metadata=metadata,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    project_canonical_event(db, event)
    if indexed:
        index_canonical_event(db, event)
    return event


def test_public_search_returns_only_authorized_result_with_provenance(
    db_session: Session,
) -> None:
    organization, owner, member = _seed_org(db_session, "public")
    event = _event(
        db_session,
        organization=organization,
        owner=owner,
        provider="slack",
        visibility="public_channel",
        source_acl=[],
        object_id="C1:100",
        title="Launch thread",
        metadata={"channel_id": "C1", "text": "Payment certification blocks launch"},
    )

    results = search_evidence(
        db_session,
        organization_id=organization.id,
        user_id=member.id,
        role=MembershipRole.MEMBER,
        query="payment launch",
        limit=10,
    )

    assert len(results) == 1
    result = results[0]
    assert result.canonical_event_id == event.id
    assert result.source_provider == "slack"
    assert result.provenance["raw_event_id"] == str(event.raw_event_id)
    assert "Payment certification" in result.snippet


def test_private_github_search_requires_explicit_grant_even_for_owner(
    db_session: Session,
) -> None:
    organization, owner, member = _seed_org(db_session, "github-private")
    event = _event(
        db_session,
        organization=organization,
        owner=owner,
        provider="github",
        visibility="private_repository",
        source_acl=["github:repository:42"],
        object_id="99",
        title="Secret payments refactor",
        metadata={"repository_id": "42", "repository": "acme/private"},
    )

    for user, role in (
        (owner, MembershipRole.OWNER),
        (member, MembershipRole.MEMBER),
    ):
        assert search_evidence(
            db_session,
            organization_id=organization.id,
            user_id=user.id,
            role=role,
            query="payments",
            limit=10,
        ) == []

    db_session.add(
        ResourceGrant(
            organization_id=organization.id,
            resource_type="github.repository",
            resource_id="42",
            user_id=member.id,
            access=ResourceAccessLevel.READ,
            created_by_user_id=owner.id,
        )
    )
    db_session.commit()

    allowed = search_evidence(
        db_session,
        organization_id=organization.id,
        user_id=member.id,
        role=MembershipRole.MEMBER,
        query="payments",
        limit=10,
    )
    assert [item.canonical_event_id for item in allowed] == [event.id]


def test_revoked_private_slack_membership_disappears_from_search(
    db_session: Session,
) -> None:
    organization, owner, member = _seed_org(db_session, "slack-private")
    slack_user_id = "U-SEARCH-MEMBER"
    event = _event(
        db_session,
        organization=organization,
        owner=owner,
        provider="slack",
        visibility="private_channel",
        source_acl=[slack_user_id],
        object_id="C-private:100",
        title="Private launch thread",
        metadata={"channel_id": "C-private", "text": "Orion acquisition planning"},
    )
    db_session.add(
        SourceIdentity(
            organization_id=organization.id,
            provider="slack",
            external_id=slack_user_id,
            display_name="Private Member",
            email=None,
            email_verified=False,
            state=SourceIdentityState.RESOLVED,
            resolved_user_id=member.id,
            resolution_method="manual",
            first_seen_at=datetime.now(UTC),
            last_seen_at=datetime.now(UTC),
        )
    )
    authorization = SlackChannelAuthorization(
        organization_id=organization.id,
        integration_connection_id=event.integration_connection_id,
        channel_id="C-private",
        channel_name="private",
        is_private=True,
        member_ids=[slack_user_id],
        authorized_by_user_id=owner.id,
    )
    db_session.add(authorization)
    db_session.commit()

    visible = search_evidence(
        db_session,
        organization_id=organization.id,
        user_id=member.id,
        role=MembershipRole.MEMBER,
        query="Orion",
        limit=10,
    )
    assert [item.canonical_event_id for item in visible] == [event.id]

    authorization.member_ids = []
    db_session.commit()

    assert search_evidence(
        db_session,
        organization_id=organization.id,
        user_id=member.id,
        role=MembershipRole.MEMBER,
        query="Orion",
        limit=10,
    ) == []


def test_search_is_tenant_scoped(db_session: Session) -> None:
    org_one, owner_one, member_one = _seed_org(db_session, "tenant-one")
    org_two, _, member_two = _seed_org(db_session, "tenant-two")
    event = _event(
        db_session,
        organization=org_one,
        owner=owner_one,
        provider="slack",
        visibility="public_channel",
        source_acl=[],
        object_id="C1:tenant",
        title="Nebula plan",
        metadata={"channel_id": "C1", "text": "Nebula confidential codename"},
    )

    own_results = search_evidence(
        db_session,
        organization_id=org_one.id,
        user_id=member_one.id,
        role=MembershipRole.MEMBER,
        query="Nebula",
        limit=10,
    )
    assert [item.canonical_event_id for item in own_results] == [event.id]

    assert search_evidence(
        db_session,
        organization_id=org_two.id,
        user_id=member_two.id,
        role=MembershipRole.MEMBER,
        query="Nebula",
        limit=10,
    ) == []


def test_search_reconciliation_is_bounded_and_idempotent(db_session: Session) -> None:
    organization, owner, _ = _seed_org(db_session, "reconcile")
    first = _event(
        db_session,
        organization=organization,
        owner=owner,
        provider="slack",
        visibility="public_channel",
        source_acl=[],
        object_id="C1:first",
        title="First",
        metadata={"channel_id": "C1", "text": "First searchable event"},
        indexed=False,
    )
    second = _event(
        db_session,
        organization=organization,
        owner=owner,
        provider="slack",
        visibility="public_channel",
        source_acl=[],
        object_id="C1:second",
        title="Second",
        metadata={"channel_id": "C1", "text": "Second searchable event"},
        indexed=False,
    )

    processed, remaining = reconcile_search_documents(
        db_session,
        organization_id=organization.id,
        limit=1,
    )
    assert (processed, remaining) == (1, 1)

    processed, remaining = reconcile_search_documents(
        db_session,
        organization_id=organization.id,
        limit=10,
    )
    assert (processed, remaining) == (1, 0)

    processed, remaining = reconcile_search_documents(
        db_session,
        organization_id=organization.id,
        limit=10,
    )
    assert (processed, remaining) == (0, 0)
    indexed_ids = set(db_session.scalars(select(SearchDocument.canonical_event_id)))
    assert indexed_ids == {first.id, second.id}


def test_canonicalization_projects_search_document_automatically(
    db_session: Session,
) -> None:
    organization, owner, member = _seed_org(db_session, "auto-index")
    connection = IntegrationConnection(
        organization_id=organization.id,
        provider="slack",
        external_account_id="slack-auto-index",
        display_name="Slack auto index",
        scopes=[],
        provider_metadata={},
        created_by_user_id=owner.id,
    )
    db_session.add(connection)
    db_session.flush()
    payload = {
        "channel_id": "C-auto",
        "message": {
            "ts": "100.0",
            "user": "U-auto",
            "text": "Automatic retrieval indexing works",
        },
    }
    raw_payload = json.dumps(payload).encode()
    raw = RawEvent(
        organization_id=organization.id,
        integration_connection_id=connection.id,
        provider="slack",
        source_event_id="backfill:C-auto:100.0",
        source_event_type="message",
        delivery_kind="backfill",
        source_timestamp=datetime.now(UTC),
        content_type="application/json",
        payload_sha256=hashlib.sha256(raw_payload).hexdigest(),
        raw_payload=raw_payload,
        source_visibility="public_channel",
        source_acl=[],
    )
    db_session.add(raw)
    db_session.commit()

    canonical = canonicalize_raw_event(db_session, raw)
    assert canonical.event is not None
    document = db_session.scalar(
        select(SearchDocument).where(
            SearchDocument.canonical_event_id == canonical.event.id
        )
    )
    assert document is not None
    assert "Automatic retrieval indexing works" in document.search_text

    results = search_evidence(
        db_session,
        organization_id=organization.id,
        user_id=member.id,
        role=MembershipRole.MEMBER,
        query="retrieval indexing",
        limit=10,
    )
    assert [item.canonical_event_id for item in results] == [canonical.event.id]
