import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.native_workspace import (
    NativeWorkspaceConflictError,
    NativeWorkspaceError,
    can_manage_team,
    create_team,
    get_team,
    list_teams,
    set_team_archived,
    update_team,
)
from app.native_workspace_models import NativeTeam, NativeTeamStatus
from app.permissions import AuthorizationContext, Permission, require_organization_permission

router = APIRouter(
    prefix="/organizations/{organization_id}/native-teams",
    tags=["native-teams"],
)
_read = require_organization_permission(Permission.ORGANIZATION_READ)
_write = require_organization_permission(Permission.NATIVE_CHAT_WRITE)


class TeamCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)

    model_config = {"extra": "forbid"}


class TeamUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    expected_revision: int = Field(ge=1)

    model_config = {"extra": "forbid"}


class TeamLifecycleWrite(BaseModel):
    expected_revision: int = Field(ge=1)

    model_config = {"extra": "forbid"}


class TeamRead(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    slug: str
    description: str | None
    status: NativeTeamStatus
    revision: int
    created_by_user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None
    can_manage: bool


def _request_id(request: Request) -> str | None:
    value = request.headers.get("x-request-id")
    return value.strip()[:128] if value and value.strip() else None


def _read_team(team: NativeTeam, authorization: AuthorizationContext) -> TeamRead:
    return TeamRead(
        id=team.id,
        organization_id=team.organization_id,
        name=team.name,
        slug=team.slug,
        description=team.description,
        status=team.status,
        revision=team.revision,
        created_by_user_id=team.created_by_user_id,
        created_at=team.created_at,
        updated_at=team.updated_at,
        archived_at=team.archived_at,
        can_manage=can_manage_team(
            team,
            actor_user_id=authorization.user_id,
            actor_role=authorization.role,
        ),
    )


def _raise_workspace_error(exc: NativeWorkspaceError) -> None:
    if exc.code == "team_not_found":
        code = status.HTTP_404_NOT_FOUND
    elif isinstance(exc, NativeWorkspaceConflictError):
        code = status.HTTP_409_CONFLICT
    else:
        code = status.HTTP_400_BAD_REQUEST
    raise HTTPException(
        status_code=code,
        detail={"code": exc.code, "message": str(exc)},
    ) from exc


@router.get("", response_model=list[TeamRead])
def read_teams(
    organization_id: uuid.UUID,
    authorization: Annotated[AuthorizationContext, Depends(_read)],
    db: Annotated[Session, Depends(get_db)],
    include_archived: bool = False,
) -> list[TeamRead]:
    rows = list_teams(
        db,
        organization_id=organization_id,
        include_archived=include_archived,
    )
    return [_read_team(row, authorization) for row in rows]


@router.post("", response_model=TeamRead, status_code=status.HTTP_201_CREATED)
def create_native_team(
    organization_id: uuid.UUID,
    payload: TeamCreate,
    request: Request,
    authorization: Annotated[AuthorizationContext, Depends(_write)],
    db: Annotated[Session, Depends(get_db)],
) -> TeamRead:
    try:
        row = create_team(
            db,
            organization_id=organization_id,
            actor_user_id=authorization.user_id,
            name=payload.name,
            description=payload.description,
            request_id=_request_id(request),
        )
    except NativeWorkspaceError as exc:
        _raise_workspace_error(exc)
    return _read_team(row, authorization)


@router.patch("/{team_id}", response_model=TeamRead)
def edit_native_team(
    organization_id: uuid.UUID,
    team_id: uuid.UUID,
    payload: TeamUpdate,
    request: Request,
    authorization: Annotated[AuthorizationContext, Depends(_write)],
    db: Annotated[Session, Depends(get_db)],
) -> TeamRead:
    try:
        row = update_team(
            db,
            organization_id=organization_id,
            team_id=team_id,
            actor_user_id=authorization.user_id,
            actor_role=authorization.role,
            expected_revision=payload.expected_revision,
            name=payload.name,
            description=payload.description,
            request_id=_request_id(request),
        )
    except NativeWorkspaceError as exc:
        _raise_workspace_error(exc)
    return _read_team(row, authorization)


@router.post("/{team_id}/archive", response_model=TeamRead)
def archive_native_team(
    organization_id: uuid.UUID,
    team_id: uuid.UUID,
    payload: TeamLifecycleWrite,
    request: Request,
    authorization: Annotated[AuthorizationContext, Depends(_write)],
    db: Annotated[Session, Depends(get_db)],
) -> TeamRead:
    try:
        row = set_team_archived(
            db,
            organization_id=organization_id,
            team_id=team_id,
            actor_user_id=authorization.user_id,
            actor_role=authorization.role,
            expected_revision=payload.expected_revision,
            archived=True,
            request_id=_request_id(request),
        )
    except NativeWorkspaceError as exc:
        _raise_workspace_error(exc)
    return _read_team(row, authorization)


@router.post("/{team_id}/restore", response_model=TeamRead)
def restore_native_team(
    organization_id: uuid.UUID,
    team_id: uuid.UUID,
    payload: TeamLifecycleWrite,
    request: Request,
    authorization: Annotated[AuthorizationContext, Depends(_write)],
    db: Annotated[Session, Depends(get_db)],
) -> TeamRead:
    try:
        row = set_team_archived(
            db,
            organization_id=organization_id,
            team_id=team_id,
            actor_user_id=authorization.user_id,
            actor_role=authorization.role,
            expected_revision=payload.expected_revision,
            archived=False,
            request_id=_request_id(request),
        )
    except NativeWorkspaceError as exc:
        _raise_workspace_error(exc)
    return _read_team(row, authorization)
