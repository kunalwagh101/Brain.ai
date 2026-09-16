import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.direct_message_models import DirectMessage
from app.direct_messages import (
    DirectConversationView,
    DirectMessageError,
    create_or_get_direct_conversation,
    direct_message_author_name,
    list_direct_conversations,
    list_direct_messages,
    send_direct_message,
)
from app.permissions import AuthorizationContext, Permission, require_organization_permission

router = APIRouter(
    prefix="/organizations/{organization_id}/direct-messages",
    tags=["direct-messages"],
)
_read = require_organization_permission(Permission.ORGANIZATION_READ)
_write = require_organization_permission(Permission.NATIVE_CHAT_WRITE)


class DirectConversationCreate(BaseModel):
    target_email: str = Field(min_length=3, max_length=320)

    model_config = {"extra": "forbid"}


class DirectConversationRead(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    other_user_id: uuid.UUID
    other_display_name: str
    other_email: str
    created_at: datetime
    updated_at: datetime


class DirectMessageCreate(BaseModel):
    body: str = Field(min_length=1, max_length=20_000)

    model_config = {"extra": "forbid"}


class DirectMessageRead(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    conversation_id: uuid.UUID
    author_user_id: uuid.UUID
    author_display_name: str
    is_mine: bool
    body: str
    body_sha256: str
    created_at: datetime


def _conversation_read(view: DirectConversationView) -> DirectConversationRead:
    conversation = view.conversation
    return DirectConversationRead(
        id=conversation.id,
        organization_id=conversation.organization_id,
        other_user_id=view.other_user.id,
        other_display_name=view.other_user.display_name or view.other_user.email,
        other_email=view.other_user.email,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
    )


def _message_read(
    db: Session,
    message: DirectMessage,
    *,
    current_user_id: uuid.UUID,
) -> DirectMessageRead:
    return DirectMessageRead(
        id=message.id,
        organization_id=message.organization_id,
        conversation_id=message.conversation_id,
        author_user_id=message.author_user_id,
        author_display_name=direct_message_author_name(db, message.author_user_id),
        is_mine=message.author_user_id == current_user_id,
        body=message.body,
        body_sha256=message.body_sha256,
        created_at=message.created_at,
    )


def _raise_dm_error(exc: DirectMessageError) -> None:
    if exc.code in {"conversation_not_found", "target_not_found", "target_not_available"}:
        code = status.HTTP_404_NOT_FOUND
    elif exc.code == "self_dm_not_allowed":
        code = status.HTTP_409_CONFLICT
    else:
        code = status.HTTP_400_BAD_REQUEST
    raise HTTPException(status_code=code, detail=exc.code) from exc


@router.get("", response_model=list[DirectConversationRead])
def list_conversations(
    organization_id: uuid.UUID,
    access: Annotated[AuthorizationContext, Depends(_read)],
    db: Annotated[Session, Depends(get_db)],
) -> list[DirectConversationRead]:
    return [
        _conversation_read(view)
        for view in list_direct_conversations(
            db,
            organization_id=organization_id,
            user_id=access.user_id,
        )
    ]


@router.post("", response_model=DirectConversationRead, status_code=status.HTTP_201_CREATED)
def create_conversation(
    organization_id: uuid.UUID,
    payload: DirectConversationCreate,
    access: Annotated[AuthorizationContext, Depends(_write)],
    db: Annotated[Session, Depends(get_db)],
) -> DirectConversationRead:
    try:
        conversation = create_or_get_direct_conversation(
            db,
            organization_id=organization_id,
            actor_user_id=access.user_id,
            target_email=payload.target_email,
        )
    except DirectMessageError as exc:
        _raise_dm_error(exc)
    views = list_direct_conversations(
        db,
        organization_id=organization_id,
        user_id=access.user_id,
    )
    for view in views:
        if view.conversation.id == conversation.id:
            return _conversation_read(view)
    raise HTTPException(status_code=404, detail="conversation_not_found")


@router.get("/{conversation_id}/messages", response_model=list[DirectMessageRead])
def read_messages(
    organization_id: uuid.UUID,
    conversation_id: uuid.UUID,
    access: Annotated[AuthorizationContext, Depends(_read)],
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
) -> list[DirectMessageRead]:
    try:
        messages = list_direct_messages(
            db,
            organization_id=organization_id,
            conversation_id=conversation_id,
            user_id=access.user_id,
            limit=limit,
        )
    except DirectMessageError as exc:
        _raise_dm_error(exc)
    return [
        _message_read(db, message, current_user_id=access.user_id)
        for message in messages
    ]


@router.post(
    "/{conversation_id}/messages",
    response_model=DirectMessageRead,
    status_code=status.HTTP_201_CREATED,
)
def post_message(
    organization_id: uuid.UUID,
    conversation_id: uuid.UUID,
    payload: DirectMessageCreate,
    access: Annotated[AuthorizationContext, Depends(_write)],
    db: Annotated[Session, Depends(get_db)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> DirectMessageRead:
    try:
        message = send_direct_message(
            db,
            organization_id=organization_id,
            conversation_id=conversation_id,
            author_user_id=access.user_id,
            body=payload.body,
            idempotency_key=idempotency_key,
        )
    except DirectMessageError as exc:
        _raise_dm_error(exc)
    return _message_read(db, message, current_user_id=access.user_id)
