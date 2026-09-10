import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.decision_memory import project_memory_candidates, review_memory_candidate
from app.decision_memory_models import DecisionMemoryCandidate, MemoryReviewAction, MemoryState
from app.evidence_ingestion import ingest_evidence
from app.evidence_models import EvidenceKind, EvidenceVisibility
from app.models import Membership, MembershipRole, Organization, User
from app.search_models import SearchDocument


def _seed(db: Session):
    user = User(email=f"memory-upload-{uuid.uuid4()}@example.com")
    organization = Organization(name="Memory Upload", slug=f"memory-upload-{uuid.uuid4().hex[:8]}")
    db.add_all([user, organization])
    db.flush()
    db.add(
        Membership(
            organization_id=organization.id,
            user_id=user.id,
            role=MembershipRole.MEMBER,
        )
    )
    db.commit()
    return organization, user


def test_transcript_upload_projects_decision_and_blocker_candidates(db_session: Session) -> None:
    organization, user = _seed(db_session)
    source = ingest_evidence(
        db_session,
        organization_id=organization.id,
        actor_user_id=user.id,
        kind=EvidenceKind.TRANSCRIPT,
        title="Atlas review",
        filename="atlas.txt",
        media_type="text/plain",
        content=(
            b"Decision: ship Atlas on Friday.\n"
            b"Blocker: production credentials are still missing."
        ),
        visibility=EvidenceVisibility.ORGANIZATION,
        occurred_at=None,
        idempotency_key="memory-transcript",
    )
    document = db_session.scalar(
        select(SearchDocument).where(
            SearchDocument.organization_id == organization.id,
            SearchDocument.object_external_id == str(source.id),
        )
    )
    assert document is not None

    result = project_memory_candidates(db_session, document)
    candidates = list(
        db_session.scalars(
            select(DecisionMemoryCandidate).where(
                DecisionMemoryCandidate.organization_id == organization.id
            )
        )
    )

    assert result.created == 2
    assert len(candidates) == 2
    assert all(candidate.state == MemoryState.CANDIDATE for candidate in candidates)
    assert all(candidate.search_document_id == document.id for candidate in candidates)
    assert all(candidate.work_graph_node_id == document.work_graph_node_id for candidate in candidates)


def test_reextraction_does_not_supersede_human_reopened_candidate(db_session: Session) -> None:
    organization, user = _seed(db_session)
    source = ingest_evidence(
        db_session,
        organization_id=organization.id,
        actor_user_id=user.id,
        kind=EvidenceKind.DOCUMENT,
        title="Atlas decision",
        filename="atlas.txt",
        media_type="text/plain",
        content=b"Decision: use PostgreSQL for Atlas.",
        visibility=EvidenceVisibility.ORGANIZATION,
        occurred_at=None,
        idempotency_key="memory-human-authority",
    )
    document = db_session.scalar(
        select(SearchDocument).where(
            SearchDocument.organization_id == organization.id,
            SearchDocument.object_external_id == str(source.id),
        )
    )
    assert document is not None
    project_memory_candidates(db_session, document)
    candidate = db_session.scalar(
        select(DecisionMemoryCandidate).where(
            DecisionMemoryCandidate.organization_id == organization.id
        )
    )
    assert candidate is not None

    review_memory_candidate(
        db_session,
        organization_id=organization.id,
        user_id=user.id,
        candidate_id=candidate.id,
        action=MemoryReviewAction.REJECT,
        reason="This was recorded too early.",
        summary=None,
    )
    reopened = review_memory_candidate(
        db_session,
        organization_id=organization.id,
        user_id=user.id,
        candidate_id=candidate.id,
        action=MemoryReviewAction.REOPEN,
        reason="The team confirmed this should return to review.",
        summary=None,
    )
    assert reopened.state == MemoryState.CANDIDATE

    document.content = "Ordinary status update with no explicit decision marker."
    db_session.commit()
    project_memory_candidates(db_session, document)
    db_session.refresh(candidate)

    assert candidate.state == MemoryState.CANDIDATE
