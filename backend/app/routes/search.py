import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.permissions import AuthorizationContext, Permission, require_organization_permission
from app.search import reconcile_search_documents, search_evidence

router = APIRouter(
    prefix="/organizations/{organization_id}/search",
    tags=["search"],
)
_read_search = require_organization_permission(Permission.RESOURCE_READ)
_manage_search = require_organization_permission(Permission.INTEGRATION_MANAGE)


class SearchResultRead(BaseModel):
    canonical_event_id: uuid.UUID
    source_provider: str
    source_event_id: str
    event_type: str
    object_type: str
    object_external_id: str
    title: str
    snippet: str
    occurred_at: datetime | None
    provenance: dict[str, object]


class SearchReconcileRead(BaseModel):
    processed: int
    remaining: int


@router.get("", response_model=list[SearchResultRead])
def search_organization_evidence(
    organization_id: uuid.UUID,
    authorization: Annotated[AuthorizationContext, Depends(_read_search)],
    db: Annotated[Session, Depends(get_db)],
    q: Annotated[str, Query(min_length=2, max_length=200)],
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> list[SearchResultRead]:
    results = search_evidence(
        db,
        organization_id=organization_id,
        user_id=authorization.user_id,
        role=authorization.role,
        query=q,
        limit=limit,
    )
    return [SearchResultRead(**result.__dict__) for result in results]


@router.post("/reconcile", response_model=SearchReconcileRead)
def reconcile_search_index(
    organization_id: uuid.UUID,
    authorization: Annotated[AuthorizationContext, Depends(_manage_search)],
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
