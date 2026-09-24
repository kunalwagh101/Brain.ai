import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.decision_memory import project_memory_candidates, review_memory_candidate
from app.decision_memory_models import DecisionMemoryCandidate, MemoryReviewAction
from app.evidence_ingestion import ingest_evidence
from app.evidence_models import EvidenceKind, EvidenceVisibility
from app.models import Membership, MembershipRole, Organization, User
from app.project_status import (
    ProjectStatusError,
    build_project_status,
    upsert_project_progress_item,
)
from app.project_status_models import ProjectWorkState
from app.search_models import SearchDocument
from app.work_graph import create_manual_edge, create_manual_node
from app.work_graph_models import WorkGraphEdgeType, WorkGraphNodeType


def _seed(db: Session):
    owner = User(email=f"project-owner-{uuid.uuid4()}@example.com")
    member = User(email=f"project-member-{uuid.uuid4()}@example.com")
    organization = Organization(
        name="Project Status",
        slug=f"project-status-{uuid.uuid4().hex[:8]}",
    )
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


def _project_and_items(db: Session, organization, owner):
    project = create_manual_node(
        db,
        organization_id=organization.id,
        node_type=WorkGraphNodeType.PROJECT,
        key=f"atlas-{uuid.uuid4().hex[:6]}",
        display_name="Atlas",
        actor_user_id=owner.id,
    )
    item_one = create_manual_node(
        db,
        organization_id=organization.id,
        node_type=WorkGraphNodeType.WORK_ITEM,
        key=f"api-{uuid.uuid4().hex[:6]}",
        display_name="Ship API",
        actor_user_id=owner.id,
    )
    item_two = create_manual_node(
        db,
        organization_id=organization.id,
        node_type=WorkGraphNodeType.WORK_ITEM,
        key=f"ui-{uuid.uuid4().hex[:6]}",
        display_name="Ship UI",
        actor_user_id=owner.id,
    )
    for item in (item_one, item_two):
        create_manual_edge(
            db,
            organization_id=organization.id,
            source_node_id=project.id,
            target_node_id=item.id,
            edge_type=WorkGraphEdgeType.CONTAINS,
            actor_user_id=owner.id,
            reason="Configured project work",
        )
    return project, item_one, item_two


def test_unconfigured_project_never_invents_percentage(db_session: Session) -> None:
    organization, owner, _ = _seed(db_session)
    project, _, _ = _project_and_items(db_session, organization, owner)

    snapshot = build_project_status(
        db_session,
        organization_id=organization.id,
        user_id=owner.id,
        role=MembershipRole.OWNER,
        project_node_id=project.id,
    )

    assert snapshot is not None
    assert snapshot.progress_percent is None
    assert snapshot.progress_basis == "unconfigured"
    assert snapshot.status == "unconfigured"


def test_progress_is_weighted_only_from_configured_structured_work(db_session: Session) -> None:
    organization, owner, _ = _seed(db_session)
    project, api_item, ui_item = _project_and_items(db_session, organization, owner)

    upsert_project_progress_item(
        db_session,
        organization_id=organization.id,
        user_id=owner.id,
        role=MembershipRole.OWNER,
        project_node_id=project.id,
        work_item_node_id=api_item.id,
        state=ProjectWorkState.DONE,
        weight=3,
        note="Release evidence reviewed",
    )
    upsert_project_progress_item(
        db_session,
        organization_id=organization.id,
        user_id=owner.id,
        role=MembershipRole.OWNER,
        project_node_id=project.id,
        work_item_node_id=ui_item.id,
        state=ProjectWorkState.IN_PROGRESS,
        weight=1,
        note=None,
    )

    snapshot = build_project_status(
        db_session,
        organization_id=organization.id,
        user_id=owner.id,
        role=MembershipRole.OWNER,
        project_node_id=project.id,
    )

    assert snapshot is not None
    assert snapshot.progress_percent == 75.0
    assert snapshot.progress_basis == "visible_configured_work_items"
    assert snapshot.status == "in_progress"
    assert {item.work_item_node_id for item in snapshot.progress_items} == {
        api_item.id,
        ui_item.id,
    }


def test_unlinked_work_item_cannot_change_project_progress(db_session: Session) -> None:
    organization, owner, _ = _seed(db_session)
    project, _, _ = _project_and_items(db_session, organization, owner)
    unrelated = create_manual_node(
        db_session,
        organization_id=organization.id,
        node_type=WorkGraphNodeType.WORK_ITEM,
        key=f"unrelated-{uuid.uuid4().hex[:6]}",
        display_name="Unrelated work",
        actor_user_id=owner.id,
    )

    with pytest.raises(ProjectStatusError, match="not linked"):
        upsert_project_progress_item(
            db_session,
            organization_id=organization.id,
            user_id=owner.id,
            role=MembershipRole.OWNER,
            project_node_id=project.id,
            work_item_node_id=unrelated.id,
            state=ProjectWorkState.DONE,
            weight=1,
            note=None,
        )


def test_generic_evidence_and_human_confirmed_blocker_drive_project_status(
    db_session: Session,
) -> None:
    organization, owner, _ = _seed(db_session)
    project, api_item, _ = _project_and_items(db_session, organization, owner)
    upsert_project_progress_item(
        db_session,
        organization_id=organization.id,
        user_id=owner.id,
        role=MembershipRole.OWNER,
        project_node_id=project.id,
        work_item_node_id=api_item.id,
        state=ProjectWorkState.IN_PROGRESS,
        weight=1,
        note=None,
    )
    source = ingest_evidence(
        db_session,
        organization_id=organization.id,
        actor_user_id=owner.id,
        kind=EvidenceKind.TRANSCRIPT,
        title="Atlas release review",
        filename="atlas-review.txt",
        media_type="text/plain",
        content=b"Blocker: production credentials are still missing.",
        visibility=EvidenceVisibility.ORGANIZATION,
        occurred_at=None,
        idempotency_key=f"project-evidence-{uuid.uuid4()}",
    )
    document = db_session.scalar(
        select(SearchDocument).where(
            SearchDocument.organization_id == organization.id,
            SearchDocument.object_external_id == str(source.id),
        )
    )
    assert document is not None
    assert document.work_graph_node_id is not None
    create_manual_edge(
        db_session,
        organization_id=organization.id,
        source_node_id=project.id,
        target_node_id=document.work_graph_node_id,
        edge_type=WorkGraphEdgeType.RELATED_TO,
        actor_user_id=owner.id,
        reason="Release review is Atlas evidence",
    )
    project_memory_candidates(db_session, document)
    candidate = db_session.scalar(
        select(DecisionMemoryCandidate).where(
            DecisionMemoryCandidate.organization_id == organization.id
        )
    )
    assert candidate is not None

    before_review = build_project_status(
        db_session,
        organization_id=organization.id,
        user_id=owner.id,
        role=MembershipRole.OWNER,
        project_node_id=project.id,
    )
    assert before_review is not None
    assert before_review.status == "in_progress"
    assert before_review.active_blockers == ()
    assert len(before_review.candidate_memories) == 1
    assert any(
        item.source_provider == "generic_upload"
        for item in before_review.evidence
    )

    review_memory_candidate(
        db_session,
        organization_id=organization.id,
        user_id=owner.id,
        candidate_id=candidate.id,
        action=MemoryReviewAction.CONFIRM,
        reason="Confirmed in the release review",
        summary=None,
    )
    after_review = build_project_status(
        db_session,
        organization_id=organization.id,
        user_id=owner.id,
        role=MembershipRole.OWNER,
        project_node_id=project.id,
    )

    assert after_review is not None
    assert after_review.status == "blocked"
    assert len(after_review.active_blockers) == 1
    assert after_review.active_blockers[0].id == candidate.id
    assert after_review.progress_percent == 0.0


def test_restricted_project_evidence_is_not_disclosed_to_other_member(
    db_session: Session,
) -> None:
    organization, owner, member = _seed(db_session)
    project, _, _ = _project_and_items(db_session, organization, owner)
    source = ingest_evidence(
        db_session,
        organization_id=organization.id,
        actor_user_id=owner.id,
        kind=EvidenceKind.DOCUMENT,
        title="Restricted Atlas note",
        filename="atlas-private.txt",
        media_type="text/plain",
        content=b"Decision: rotate the Atlas signing key on Friday.",
        visibility=EvidenceVisibility.RESTRICTED,
        occurred_at=None,
        idempotency_key=f"project-restricted-{uuid.uuid4()}",
    )
    document = db_session.scalar(
        select(SearchDocument).where(
            SearchDocument.organization_id == organization.id,
            SearchDocument.object_external_id == str(source.id),
        )
    )
    assert document is not None
    assert document.work_graph_node_id is not None
    create_manual_edge(
        db_session,
        organization_id=organization.id,
        source_node_id=project.id,
        target_node_id=document.work_graph_node_id,
        edge_type=WorkGraphEdgeType.RELATED_TO,
        actor_user_id=owner.id,
        reason="Private Atlas evidence",
    )
    project_memory_candidates(db_session, document)

    owner_snapshot = build_project_status(
        db_session,
        organization_id=organization.id,
        user_id=owner.id,
        role=MembershipRole.OWNER,
        project_node_id=project.id,
    )
    member_snapshot = build_project_status(
        db_session,
        organization_id=organization.id,
        user_id=member.id,
        role=MembershipRole.MEMBER,
        project_node_id=project.id,
    )

    assert owner_snapshot is not None
    assert member_snapshot is not None
    assert len(owner_snapshot.evidence) == 1
    assert len(owner_snapshot.candidate_memories) == 1
    assert member_snapshot.evidence == ()
    assert member_snapshot.candidate_memories == ()
    assert member_snapshot.confirmed_decisions == ()
    assert member_snapshot.active_blockers == ()
