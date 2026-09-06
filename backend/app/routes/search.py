import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.embeddings import EmbeddingError, build_embedding_client
from app.permissions import AuthorizationContext, Permission, require_organization_permission
from app.search import SearchMode, reconcile_search_documents, search_documents

router = APIRouter(prefix="/organizations/{organization_id}/search", tags=["search"])
_read_search = require_organization_permission(Permission.RESOURCE_READ)
_write_search = require_organization_permission(Permission.RESOURCE_WRITE)


class SearchResultRead(BaseModel):
    document_id: uuid.UUID
    canonical_event_id: uuid.UUID
    source_provider: str
    source_event_id: str | None
    object_type: str
    object_external_id: str
    title: str
    content: str
    occurred_at: str | None
    score: float
    provenance: dict[str, object]


class SearchResponseRead(BaseModel):
    query: str
    mode: SearchMode
    semantic_status: str
    results: list[SearchResultRead]


class SearchReconcileRead(BaseModel):
    processed: int
    remaining: int


@router.get("", response_model=SearchResponseRead)
def search(
    organization_id: uuid.UUID,
    authorization: Annotated[AuthorizationContext, Depends(_read_search)],
    db: Annotated[Session, Depends(get_db)],
    q: Annotated[str, Query(min_length=1, max_length=500)],
    mode: SearchMode = SearchMode.HYBRID,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> SearchResponseRead:
    normalized = " ".join(q.split())
    try:
        embedding_client, embedding_model = build_embedding_client()
    except EmbeddingError:
        embedding_client, embedding_model = None, None
    data = search_documents(
        db,
        organization_id=organization_id,
        user_id=authorization.user_id,
        query=normalized,
        mode=mode,
        limit=limit,
        embedding_client=embedding_client,
        embedding_model=embedding_model,
    )
    return SearchResponseRead(
        query=normalized,
        mode=mode,
        semantic_status=data.semantic_status,
        results=[
            SearchResultRead(
                document_id=hit.document.id,
                canonical_event_id=hit.document.canonical_event_id,
                source_provider=hit.document.source_provider,
                source_event_id=(
                    hit.document.provenance.get("source_event_id")
                    if isinstance(hit.document.provenance.get("source_event_id"), str)
                    else None
                ),
                object_type=hit.document.object_type,
                object_external_id=hit.document.object_external_id,
                title=hit.document.title,
                content=hit.document.content,
                occurred_at=(
                    hit.document.occurred_at.isoformat() if hit.document.occurred_at else None
                ),
                score=hit.score,
                provenance=hit.document.provenance,
            )
            for hit in data.hits
        ],
    )


@router.post("/reconcile", response_model=SearchReconcileRead)
def reconcile(
    organization_id: uuid.UUID,
    authorization: Annotated[AuthorizationContext, Depends(_write_search)],
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> SearchReconcileRead:
    del authorization
    processed, remaining = reconcile_search_documents(
        db,
        organization_id=organization_id,
        limit=limit,
    )
    return SearchReconcileRead(processed=processed, remaining=remaining)
