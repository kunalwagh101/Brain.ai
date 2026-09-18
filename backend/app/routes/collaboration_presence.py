import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.collaboration_presence import (
    CollaborationContextKind,
    CollaborationPresenceError,
    get_context_presence,
    heartbeat_presence,
    set_typing,
    clear_typing,
)
from app.database import get_db
from app.permissions import (
    AuthorizationContext,
    Permission,
    require_organization_permission,
)

router = APIRouter(
    prefix="/organizations/{organization_id}/collaboration-presence",
    tags=["collaboration-presence"],
)
_access = require_organization_permission(Permission.NATIVE_CHAT_WRITE)


class CollaborationUserRead(BaseModel):
    user_id: uuid.UUID
    display_name: str


class CollaborationContextRead(BaseModel):
    online_users: list[CollaborationUserRead]
    typing_users: list[CollaborationUserRead]


class PresenceHeartbeatRead(BaseModel):
    online: bool


def _raise_presence_error(exc: CollaborationPresenceError) -> None:
    if exc.code == "context_not_found":
        code = status.HTTP_404_NOT_FOUND
    elif exc.code == "presence_not_available":
        code = status.HTTP_403_FORBIDDEN
    else:
        code = status.HTTP_400_BAD_REQUEST
    raise HTTPException(status_code=code, detail=exc.code) from exc


@router.post("/heartbeat", response_model=PresenceHeartbeatRead)
def presence_heartbeat(
    organization_id: uuid.UUID,
    access: Annotated[AuthorizationContext, Depends(_access)],
    db: Annotated[Session, Depends(get_db)],
) -> PresenceHeartbeatRead:
    try:
        heartbeat_presence(
            db,
            organization_id=organization_id,
            user_id=access.user_id,
        )
    except CollaborationPresenceError as exc:
        _raise_presence_error(exc)
    return PresenceHeartbeatRead(online=True)


@router.get(
    "/{context_kind}/{context_id}",
    response_model=CollaborationContextRead,
)
def read_context_presence(
    organization_id: uuid.UUID,
    context_kind: CollaborationContextKind,
    context_id: uuid.UUID,
    access: Annotated[AuthorizationContext, Depends(_access)],
    db: Annotated[Session, Depends(get_db)],
) -> CollaborationContextRead:
    try:
        view = get_context_presence(
            db,
            organization_id=organization_id,
            current_user_id=access.user_id,
            context_kind=context_kind,
            context_id=context_id,
        )
    except CollaborationPresenceError as exc:
        _raise_presence_error(exc)
    return CollaborationContextRead(
        online_users=[
            CollaborationUserRead(
                user_id=item.user_id,
                display_name=item.display_name,
            )
            for item in view.online_users
        ],
        typing_users=[
            CollaborationUserRead(
                user_id=item.user_id,
                display_name=item.display_name,
            )
            for item in view.typing_users
        ],
    )


@router.put(
    "/{context_kind}/{context_id}/typing",
    status_code=status.HTTP_204_NO_CONTENT,
)
def refresh_typing(
    organization_id: uuid.UUID,
    context_kind: CollaborationContextKind,
    context_id: uuid.UUID,
    access: Annotated[AuthorizationContext, Depends(_access)],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    try:
        set_typing(
            db,
            organization_id=organization_id,
            user_id=access.user_id,
            context_kind=context_kind,
            context_id=context_id,
        )
    except CollaborationPresenceError as exc:
        _raise_presence_error(exc)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "/{context_kind}/{context_id}/typing",
    status_code=status.HTTP_204_NO_CONTENT,
)
def stop_typing(
    organization_id: uuid.UUID,
    context_kind: CollaborationContextKind,
    context_id: uuid.UUID,
    access: Annotated[AuthorizationContext, Depends(_access)],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    clear_typing(
        db,
        organization_id=organization_id,
        user_id=access.user_id,
        context_kind=context_kind,
        context_id=context_id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
