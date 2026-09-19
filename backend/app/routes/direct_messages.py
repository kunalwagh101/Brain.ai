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
    get_direct_message,
    list_direct_conversations,
    list_direct_messages,
    mark_direct_conversation_read,
    send_direct_message,
)
from app.permissions import AuthorizationContext, Permission, require_organization_permission

router = APIRouter(
    prefix="/organizations/{organization_id}/direct-messages",
    tags=["direct-messages"],
)
_dm_access = require_organization_permission(Permission.NATIVE_CHAT_WRITE)


class DirectConversationCreate(BaseModel):
    target_email: str = Field(min_length=3, max_length=320)

    model_config = {"extra": "forbid"}


class DirectConversationRead(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    other_user_id: uuid.UUID
    other_display_name: str
    other_email: str
    can_send: bool
    unread_count: int
    latest_message_id: uuid.UUID | None
    first_unread_message_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class DirectMessageCreate(BaseModel):
    body: str = Field(min_length=1, max_length=20_000)

    model_config = {"extra": "forbid"}


class DirectMarkRead(BaseModel):
    through_message_id: uuid.UUID

    model_config = {"extra": "forbid"}


class DirectConversationUnreadRead(BaseModel):
    conversation_id: uuid.UUID
    unread_count: int
    latest_message_id: uuid.UUID | None
    first_unread_message_id: uuid.UUID | None


class DirectMessageRead(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    conversation_id: uuid.UUID
    author_user_id: uuid.UUID
    author_display_name: str
    is_mine: bool
    body: str
    body_sha256: str
    sequence: int
    created_at: datetime


def _conversation_read(view: DirectConversationView) -> DirectConversationRead:
    conversation = view.conversation
    return DirectConversationRead(
        id=conversation.id,
        organization_id=conversation.organization_id,
        other_user_id=view.other_user.id,
        other_display_name=view.other_user.display_name or view.other_user.email,
        other_email=view.other_user.email,
        can_send=view.can_send,
        unread_count=view.unread_count,
        latest_message_id=view.latest_message_id,
        first_unread_message_id=view.first_unread_message_id,
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
        sequence=message.sequence,
        created_at=message.created_at,
    )


def _raise_dm_error(exc: DirectMessageError) -> None:
    if exc.code in {
        "conversation_not_found",
        "message_not_found",
        "target_not_found",
        "target_not_available",
    }:
        code = status.HTTP_404_NOT_FOUND
    elif exc.code in {
        "self_dm_not_allowed",
        "recipient_unavailable",
        "idempotency_key_reused",
    }:
        code = status.HTTP_409_CONFLICT
    elif exc.code == "actor_not_available":
        code = status.HTTP_403_FORBIDDEN
    else:
        code = status.HTTP_400_BAD_REQUEST
    raise HTTPException(status_code=code, detail=exc.code) from exc


@router.get("", response_model=list[DirectConversationRead])
def list_conversations(
    organization_id: uuid.UUID,
    access: Annotated[AuthorizationContext, Depends(_dm_access)],
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
    access: Annotated[AuthorizationContext, Depends(_dm_access)],
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
    access: Annotated[AuthorizationContext, Depends(_dm_access)],
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=200)] = 200,
    before_sequence: Annotated[int | None, Query(ge=1)] = None,
) -> list[DirectMessageRead]:
    try:
        messages = list_direct_messages(
            db,
            organization_id=organization_id,
            conversation_id=conversation_id,
            user_id=access.user_id,
            limit=limit,
            before_sequence=before_sequence,
        )
    except DirectMessageError as exc:
        _raise_dm_error(exc)
    return [
        _message_read(db, message, current_user_id=access.user_id)
        for message in messages
    ]


@router.get(
    "/{conversation_id}/messages/{message_id}",
    response_model=DirectMessageRead,
)
def read_message(
    organization_id: uuid.UUID,
    conversation_id: uuid.UUID,
    message_id: uuid.UUID,
    access: Annotated[AuthorizationContext, Depends(_dm_access)],
    db: Annotated[Session, Depends(get_db)],
) -> DirectMessageRead:
    try:
        message = get_direct_message(
            db,
            organization_id=organization_id,
            conversation_id=conversation_id,
            message_id=message_id,
            user_id=access.user_id,
        )
    except DirectMessageError as exc:
        _raise_dm_error(exc)
    return _message_read(db, message, current_user_id=access.user_id)


@router.post(
    "/{conversation_id}/read",
    response_model=DirectConversationUnreadRead,
)
def mark_read(
    organization_id: uuid.UUID,
    conversation_id: uuid.UUID,
    payload: DirectMarkRead,
    access: Annotated[AuthorizationContext, Depends(_dm_access)],
    db: Annotated[Session, Depends(get_db)],
) -> DirectConversationUnreadRead:
    try:
        mark_direct_conversation_read(
            db,
            organization_id=organization_id,
            conversation_id=conversation_id,
            user_id=access.user_id,
            through_message_id=payload.through_message_id,
        )
        views = list_direct_conversations(
            db,
            organization_id=organization_id,
            user_id=access.user_id,
        )
    except DirectMessageError as exc:
        _raise_dm_error(exc)
    view = next(
        (item for item in views if item.conversation.id == conversation_id),
        None,
    )
    if view is None:
        raise HTTPException(status_code=404, detail="conversation_not_found")
    return DirectConversationUnreadRead(
        conversation_id=conversation_id,
        unread_count=view.unread_count,
        latest_message_id=view.latest_message_id,
        first_unread_message_id=view.first_unread_message_id,
    )


@router.post(
    "/{conversation_id}/messages",
    response_model=DirectMessageRead,
    status_code=status.HTTP_201_CREATED,
)
def post_message(
    organization_id: uuid.UUID,
    conversation_id: uuid.UUID,
    payload: DirectMessageCreate,
    access: Annotated[AuthorizationContext, Depends(_dm_access)],
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
