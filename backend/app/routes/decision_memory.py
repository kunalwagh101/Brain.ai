import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.decision_memory import (
    DecisionMemoryError,
    get_visible_memory_candidate,
    list_memory_reviews,
    list_visible_memory_candidates,
    memory_candidate_evidence,
    reconcile_memory_candidates,
    review_memory_candidate,
)
from app.decision_memory_models import (
    DecisionMemoryCandidate,
    DecisionMemoryReview,
    MemoryKind,
    MemoryReviewAction,
    MemoryState,
)
from app.permissions import AuthorizationContext, Permission, require_organization_permission

router = APIRouter(
    prefix="/organizations/{organization_id}/memory",
    tags=["decision-memory"],
)
_read_memory = require_organization_permission(Permission.RESOURCE_READ)
_write_memory = require_organization_permission(Permission.RESOURCE_WRITE)


class MemoryCandidateRead(BaseModel):
    id: uuid.UUID
    kind: MemoryKind
    state: MemoryState
    summary: str
    confidence: float
    extraction_method: str
    extraction_version: str
    canonical_event_id: uuid.UUID
    search_document_id: uuid.UUID | None
    work_graph_node_id: uuid.UUID | None
    source_provider: str
    source_event_id: str
    source_event_type: str
    occurred_at: datetime | None
    evidence_title: str
    evidence_excerpt: str
    provenance: dict[str, object]
    created_at: datetime
    updated_at: datetime


class MemoryReviewCreate(BaseModel):
    action: MemoryReviewAction
    reason: str = Field(min_length=1, max_length=1000)
    summary: str | None = Field(default=None, min_length=3, max_length=1000)


class MemoryReviewRead(BaseModel):
    id: uuid.UUID
    actor_user_id: uuid.UUID
    action: MemoryReviewAction
    previous_state: MemoryState
    new_state: MemoryState
    previous_summary: str
    new_summary: str
    reason: str
    created_at: datetime

    model_config = {"from_attributes": True}


class MemoryReconcileRead(BaseModel):
    processed_documents: int
    created_candidates: int
    remaining_documents: int


def _evidence_excerpt(content: str, summary: str, limit: int = 800) -> str:
    content = " ".join(content.split())
    if not content:
        return ""
    index = content.casefold().find(summary.casefold())
    start = max(0, index - 200) if index >= 0 else 0
    excerpt = content[start : start + limit]
    if start > 0:
        excerpt = f"…{excerpt}"
    if start + limit < len(content):
        excerpt = f"{excerpt}…"
    return excerpt


def _candidate_read(db: Session, candidate: DecisionMemoryCandidate) -> MemoryCandidateRead:
    event, document = memory_candidate_evidence(db, candidate)
    return MemoryCandidateRead(
        id=candidate.id,
        kind=candidate.kind,
        state=candidate.state,
        summary=candidate.summary,
        confidence=candidate.confidence,
        extraction_method=candidate.extraction_method,
        extraction_version=candidate.extraction_version,
        canonical_event_id=candidate.canonical_event_id,
        search_document_id=candidate.search_document_id,
        work_graph_node_id=candidate.work_graph_node_id,
        source_provider=event.source_provider,
        source_event_id=event.source_event_id,
        source_event_type=event.source_event_type,
        occurred_at=event.occurred_at,
        evidence_title=document.title,
        evidence_excerpt=_evidence_excerpt(document.content, candidate.summary),
        provenance={
            **document.provenance,
            "canonical_event_id": str(event.id),
            "search_document_id": str(document.id),
        },
        created_at=candidate.created_at,
        updated_at=candidate.updated_at,
    )


@router.post("/reconcile", response_model=MemoryReconcileRead)
def reconcile_memory(
    organization_id: uuid.UUID,
    authorization: Annotated[AuthorizationContext, Depends(_write_memory)],
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> MemoryReconcileRead:
    del authorization
    processed, created, remaining = reconcile_memory_candidates(
        db,
        organization_id=organization_id,
        limit=limit,
    )
    return MemoryReconcileRead(
        processed_documents=processed,
        created_candidates=created,
        remaining_documents=remaining,
    )


@router.get("", response_model=list[MemoryCandidateRead])
def list_memory(
    organization_id: uuid.UUID,
    authorization: Annotated[AuthorizationContext, Depends(_read_memory)],
    db: Annotated[Session, Depends(get_db)],
    kind: MemoryKind | None = None,
    state_filter: Annotated[MemoryState | None, Query(alias="state")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[MemoryCandidateRead]:
    candidates = list_visible_memory_candidates(
        db,
        organization_id=organization_id,
        user_id=authorization.user_id,
        kind=kind,
        state=state_filter,
        limit=limit,
    )
    return [_candidate_read(db, candidate) for candidate in candidates]


@router.get("/{candidate_id}", response_model=MemoryCandidateRead)
def get_memory(
    organization_id: uuid.UUID,
    candidate_id: uuid.UUID,
    authorization: Annotated[AuthorizationContext, Depends(_read_memory)],
    db: Annotated[Session, Depends(get_db)],
) -> MemoryCandidateRead:
    candidate = get_visible_memory_candidate(
        db,
        organization_id=organization_id,
        user_id=authorization.user_id,
        candidate_id=candidate_id,
    )
    if candidate is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Memory candidate not found",
        )
    return _candidate_read(db, candidate)


@router.post("/{candidate_id}/review", response_model=MemoryCandidateRead)
def review_memory(
    organization_id: uuid.UUID,
    candidate_id: uuid.UUID,
    payload: MemoryReviewCreate,
    authorization: Annotated[AuthorizationContext, Depends(_write_memory)],
    db: Annotated[Session, Depends(get_db)],
) -> MemoryCandidateRead:
    try:
        candidate = review_memory_candidate(
            db,
            organization_id=organization_id,
            user_id=authorization.user_id,
            candidate_id=candidate_id,
            action=payload.action,
            reason=payload.reason,
            summary=payload.summary,
        )
    except DecisionMemoryError as exc:
        message = str(exc)
        code = (
            status.HTTP_404_NOT_FOUND
            if message == "Memory candidate not found"
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(status_code=code, detail=message) from exc
    return _candidate_read(db, candidate)


@router.get("/{candidate_id}/reviews", response_model=list[MemoryReviewRead])
def get_memory_reviews(
    organization_id: uuid.UUID,
    candidate_id: uuid.UUID,
    authorization: Annotated[AuthorizationContext, Depends(_read_memory)],
    db: Annotated[Session, Depends(get_db)],
) -> list[DecisionMemoryReview]:
    reviews = list_memory_reviews(
        db,
        organization_id=organization_id,
        user_id=authorization.user_id,
        candidate_id=candidate_id,
    )
    if reviews is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Memory candidate not found",
        )
    return reviews
