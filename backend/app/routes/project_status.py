import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.permissions import AuthorizationContext, Permission, require_organization_permission
from app.project_status import (
    ProjectStatusError,
    ProjectStatusSnapshot,
    build_project_status,
    delete_project_progress_item,
    list_project_statuses,
    upsert_project_progress_item,
)
from app.project_status_models import ProjectWorkState

router = APIRouter(
    prefix="/organizations/{organization_id}/project-status",
    tags=["project-status"],
)
_read = require_organization_permission(Permission.RESOURCE_READ)
_write = require_organization_permission(Permission.RESOURCE_WRITE)


class ProjectProgressUpdate(BaseModel):
    state: ProjectWorkState
    weight: int = Field(default=1, ge=1, le=10_000)
    note: str | None = Field(default=None, max_length=1000)


class ProjectProgressRead(BaseModel):
    id: uuid.UUID
    work_item_node_id: uuid.UUID
    work_item_name: str
    state: ProjectWorkState
    weight: int
    note: str | None
    updated_at: datetime


class ProjectMemoryRead(BaseModel):
    id: uuid.UUID
    kind: str
    state: str
    summary: str
    confidence: float
    work_graph_node_id: uuid.UUID | None
    canonical_event_id: uuid.UUID
    search_document_id: uuid.UUID | None


class ProjectEvidenceRead(BaseModel):
    document_id: uuid.UUID
    canonical_event_id: uuid.UUID
    work_graph_node_id: uuid.UUID | None
    source_provider: str
    object_type: str
    object_external_id: str
    title: str
    occurred_at: datetime | None
    provenance: dict[str, object]


class ProjectStatusRead(BaseModel):
    project_node_id: uuid.UUID
    project_name: str
    progress_percent: float | None
    progress_basis: str
    status: str
    progress_items: list[ProjectProgressRead]
    active_blockers: list[ProjectMemoryRead]
    confirmed_decisions: list[ProjectMemoryRead]
    candidate_memories: list[ProjectMemoryRead]
    evidence: list[ProjectEvidenceRead]


def _request_id(request: Request) -> str | None:
    value = getattr(request.state, "request_id", None)
    return value if isinstance(value, str) else None


def _read_snapshot(snapshot: ProjectStatusSnapshot) -> ProjectStatusRead:
    return ProjectStatusRead(
        project_node_id=snapshot.project_node_id,
        project_name=snapshot.project_name,
        progress_percent=snapshot.progress_percent,
        progress_basis=snapshot.progress_basis,
        status=snapshot.status,
        progress_items=[ProjectProgressRead(**item.__dict__) for item in snapshot.progress_items],
        active_blockers=[ProjectMemoryRead(**item.__dict__) for item in snapshot.active_blockers],
        confirmed_decisions=[
            ProjectMemoryRead(**item.__dict__) for item in snapshot.confirmed_decisions
        ],
        candidate_memories=[
            ProjectMemoryRead(**item.__dict__) for item in snapshot.candidate_memories
        ],
        evidence=[ProjectEvidenceRead(**item.__dict__) for item in snapshot.evidence],
    )


@router.get("", response_model=list[ProjectStatusRead])
def list_projects(
    organization_id: uuid.UUID,
    authorization: Annotated[AuthorizationContext, Depends(_read)],
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[ProjectStatusRead]:
    snapshots = list_project_statuses(
        db,
        organization_id=organization_id,
        user_id=authorization.user_id,
        role=authorization.role,
        limit=limit,
    )
    return [_read_snapshot(snapshot) for snapshot in snapshots]


@router.get("/{project_node_id}", response_model=ProjectStatusRead)
def get_project(
    organization_id: uuid.UUID,
    project_node_id: uuid.UUID,
    authorization: Annotated[AuthorizationContext, Depends(_read)],
    db: Annotated[Session, Depends(get_db)],
) -> ProjectStatusRead:
    snapshot = build_project_status(
        db,
        organization_id=organization_id,
        user_id=authorization.user_id,
        role=authorization.role,
        project_node_id=project_node_id,
    )
    if snapshot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return _read_snapshot(snapshot)


@router.put(
    "/{project_node_id}/progress-items/{work_item_node_id}",
    response_model=ProjectStatusRead,
)
def update_progress_item(
    organization_id: uuid.UUID,
    project_node_id: uuid.UUID,
    work_item_node_id: uuid.UUID,
    payload: ProjectProgressUpdate,
    request: Request,
    authorization: Annotated[AuthorizationContext, Depends(_write)],
    db: Annotated[Session, Depends(get_db)],
) -> ProjectStatusRead:
    try:
        upsert_project_progress_item(
            db,
            organization_id=organization_id,
            user_id=authorization.user_id,
            role=authorization.role,
            project_node_id=project_node_id,
            work_item_node_id=work_item_node_id,
            state=payload.state,
            weight=payload.weight,
            note=payload.note,
            request_id=_request_id(request),
        )
    except ProjectStatusError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    snapshot = build_project_status(
        db,
        organization_id=organization_id,
        user_id=authorization.user_id,
        role=authorization.role,
        project_node_id=project_node_id,
    )
    if snapshot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return _read_snapshot(snapshot)


@router.delete(
    "/{project_node_id}/progress-items/{work_item_node_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_progress_item(
    organization_id: uuid.UUID,
    project_node_id: uuid.UUID,
    work_item_node_id: uuid.UUID,
    request: Request,
    authorization: Annotated[AuthorizationContext, Depends(_write)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    try:
        delete_project_progress_item(
            db,
            organization_id=organization_id,
            user_id=authorization.user_id,
            role=authorization.role,
            project_node_id=project_node_id,
            work_item_node_id=work_item_node_id,
            request_id=_request_id(request),
        )
    except ProjectStatusError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
