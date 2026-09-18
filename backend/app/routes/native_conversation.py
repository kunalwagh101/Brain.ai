import uuid
from datetime import datetime
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    Query,
    Request,
    Response,
    status,
)
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent_models import AgentDefinition, AgentRun
from app.database import get_db
from app.models import Membership, User
from app.native_chat import (
    NativeChatConflictError,
    NativeChatError,
    can_write_channel,
    list_channel_messages,
    list_visible_channels,
    post_user_message,
)
from app.native_chat_models import (
    NativeMessage,
    NativeMessageActorKind,
    NativeMessageProjectionStatus,
)
from app.native_conversation import (
    add_reaction,
    channel_unread_summaries,
    edit_message,
    list_thread_replies,
    mark_read,
    message_affordances,
    remove_reaction,
    retract_message,
    unread_count,
    visible_message,
)
from app.permissions import AuthorizationContext, Permission, require_organization_permission

router = APIRouter(
    prefix="/organizations/{organization_id}/native-conversation",
    tags=["native-conversation"],
)
_read = require_organization_permission(Permission.RESOURCE_READ)
_write = require_organization_permission(Permission.NATIVE_CHAT_WRITE)


class ConversationMessageCreate(BaseModel):
    body: str = Field(min_length=1, max_length=20_000)

    model_config = {"extra": "forbid"}


class MentionRead(BaseModel):
    user_id: uuid.UUID
    email: str
    display_name: str | None


class ReactionRead(BaseModel):
    reaction: str
    count: int
    reacted_by_me: bool


class ConversationMessageRead(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    channel_id: uuid.UUID
    thread_root_id: uuid.UUID | None
    actor_kind: NativeMessageActorKind
    author_user_id: uuid.UUID | None
    agent_run_id: uuid.UUID | None
    actor_display_name: str
    body: str
    body_sha256: str
    projection_status: NativeMessageProjectionStatus
    canonical_event_id: uuid.UUID | None
    created_at: datetime
    reply_count: int
    mentions: list[MentionRead]
    reactions: list[ReactionRead]
    revision: int
    edited_at: datetime | None
    deleted_at: datetime | None
    can_edit: bool
    can_delete: bool


class ChannelUnreadRead(BaseModel):
    channel_id: uuid.UUID
    unread_count: int
    last_read_at: datetime | None
    latest_message_id: uuid.UUID | None


class MarkReadWrite(BaseModel):
    through_message_id: uuid.UUID

    model_config = {"extra": "forbid"}


class ReactionWrite(BaseModel):
    reaction: str = Field(min_length=1, max_length=32)

    model_config = {"extra": "forbid"}


class MessageEditWrite(BaseModel):
    body: str = Field(min_length=1, max_length=20_000)
    expected_revision: int = Field(ge=1)

    model_config = {"extra": "forbid"}


class MessageRetractWrite(BaseModel):
    expected_revision: int = Field(ge=1)

    model_config = {"extra": "forbid"}


def _request_id(request: Request) -> str | None:
    value = getattr(request.state, "request_id", None)
    return value if isinstance(value, str) else None


def _raise_chat_error(exc: NativeChatError) -> None:
    if isinstance(exc, NativeChatConflictError):
        code = status.HTTP_409_CONFLICT
    elif exc.code in {
        "channel_not_found",
        "message_not_found",
        "thread_root_not_found",
    }:
        code = status.HTTP_404_NOT_FOUND
    else:
        code = status.HTTP_400_BAD_REQUEST
    raise HTTPException(
        status_code=code,
        detail={"code": exc.code, "message": str(exc)},
    ) from exc


def _actor_labels(db: Session, messages: list[NativeMessage]) -> dict[uuid.UUID, str]:
    user_ids = {message.author_user_id for message in messages if message.author_user_id}
    run_ids = {message.agent_run_id for message in messages if message.agent_run_id}
    organization_ids = {message.organization_id for message in messages}
    labels: dict[uuid.UUID, str] = {}
    if user_ids:
        for user in db.scalars(
            select(User)
            .join(Membership, Membership.user_id == User.id)
            .where(
                User.id.in_(user_ids),
                Membership.organization_id.in_(organization_ids),
            )
        ).unique():
            labels[user.id] = user.display_name or user.email
    if run_ids:
        rows = db.execute(
            select(AgentRun.id, AgentDefinition.name)
            .join(AgentDefinition, AgentDefinition.id == AgentRun.agent_definition_id)
            .where(
                AgentRun.id.in_(run_ids),
                AgentRun.organization_id.in_(organization_ids),
            )
        ).all()
        for run_id, name in rows:
            labels[run_id] = f"{name} · agent"
    return labels


def _message_reads(
    db: Session,
    messages: list[NativeMessage],
    user_id: uuid.UUID,
) -> list[ConversationMessageRead]:
    labels = _actor_labels(db, messages)
    affordances = message_affordances(db, messages=messages, user_id=user_id)
    result: list[ConversationMessageRead] = []
    for message in messages:
        actor_id = message.author_user_id or message.agent_run_id
        extra = affordances[message.id]
        deleted = message.deleted_at is not None
        channel = db.get(NativeChannel, message.channel_id)
        can_mutate = bool(
            not deleted
            and message.actor_kind == NativeMessageActorKind.USER
            and message.author_user_id == user_id
            and channel is not None
            and can_write_channel(db, channel, user_id=user_id)
        )
        result.append(
            ConversationMessageRead(
                id=message.id,
                organization_id=message.organization_id,
                channel_id=message.channel_id,
                thread_root_id=message.thread_root_id,
                actor_kind=message.actor_kind,
                author_user_id=message.author_user_id,
                agent_run_id=message.agent_run_id,
                actor_display_name=labels.get(actor_id, "Unknown actor"),
                body="" if deleted else message.body,
                body_sha256="" if deleted else message.body_sha256,
                projection_status=message.projection_status,
                canonical_event_id=message.canonical_event_id,
                created_at=message.created_at,
                reply_count=int(extra["reply_count"]),
                mentions=[] if deleted else extra["mentions"],
                reactions=[] if deleted else extra["reactions"],
                revision=message.revision,
                edited_at=message.edited_at,
                deleted_at=message.deleted_at,
                can_edit=can_mutate,
                can_delete=can_mutate,
            )
        )
    return result


@router.get("/channels", response_model=list[ChannelUnreadRead])
def list_channel_unread(
    organization_id: uuid.UUID,
    authorization: Annotated[AuthorizationContext, Depends(_read)],
    db: Annotated[Session, Depends(get_db)],
) -> list[ChannelUnreadRead]:
    channels = list_visible_channels(
        db,
        organization_id=organization_id,
        user_id=authorization.user_id,
    )
    summaries = channel_unread_summaries(
        db,
        organization_id=organization_id,
        channels=channels,
        user_id=authorization.user_id,
    )
    result = []
    for channel in channels:
        count, read_state, latest_message_id = summaries[channel.id]
        result.append(
            ChannelUnreadRead(
                channel_id=channel.id,
                unread_count=count,
                last_read_at=read_state.last_read_at if read_state else None,
                latest_message_id=latest_message_id,
            )
        )
    return result


@router.get(
    "/channels/{channel_id}/messages",
    response_model=list[ConversationMessageRead],
)
def list_roots(
    organization_id: uuid.UUID,
    channel_id: uuid.UUID,
    authorization: Annotated[AuthorizationContext, Depends(_read)],
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    before: datetime | None = None,
) -> list[ConversationMessageRead]:
    try:
        _, messages = list_channel_messages(
            db,
            organization_id=organization_id,
            channel_id=channel_id,
            user_id=authorization.user_id,
            limit=limit,
            before=before,
        )
    except NativeChatError as exc:
        _raise_chat_error(exc)
    return _message_reads(db, messages, authorization.user_id)


def _send(
    db: Session,
    *,
    organization_id: uuid.UUID,
    channel_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    body: str,
    idempotency_key: str | None,
    request_id: str | None,
    thread_root_id: uuid.UUID | None,
) -> NativeMessage:
    message = post_user_message(
        db,
        organization_id=organization_id,
        channel_id=channel_id,
        actor_user_id=actor_user_id,
        body=body,
        idempotency_key=idempotency_key,
        thread_root_id=thread_root_id,
        request_id=request_id,
    )
    return message


@router.post(
    "/channels/{channel_id}/messages",
    response_model=ConversationMessageRead,
    status_code=status.HTTP_201_CREATED,
)
def send_root(
    organization_id: uuid.UUID,
    channel_id: uuid.UUID,
    payload: ConversationMessageCreate,
    request: Request,
    authorization: Annotated[AuthorizationContext, Depends(_write)],
    db: Annotated[Session, Depends(get_db)],
    idempotency_key: Annotated[
        str | None,
        Header(alias="Idempotency-Key", max_length=128),
    ] = None,
) -> ConversationMessageRead:
    try:
        message = _send(
            db,
            organization_id=organization_id,
            channel_id=channel_id,
            actor_user_id=authorization.user_id,
            body=payload.body,
            idempotency_key=idempotency_key,
            request_id=_request_id(request),
            thread_root_id=None,
        )
    except NativeChatError as exc:
        _raise_chat_error(exc)
    return _message_reads(db, [message], authorization.user_id)[0]


@router.get(
    "/channels/{channel_id}/messages/{message_id}",
    response_model=ConversationMessageRead,
)
def read_message(
    organization_id: uuid.UUID,
    channel_id: uuid.UUID,
    message_id: uuid.UUID,
    authorization: Annotated[AuthorizationContext, Depends(_read)],
    db: Annotated[Session, Depends(get_db)],
) -> ConversationMessageRead:
    try:
        _, message = visible_message(
            db,
            organization_id=organization_id,
            channel_id=channel_id,
            message_id=message_id,
            user_id=authorization.user_id,
        )
    except NativeChatError as exc:
        _raise_chat_error(exc)
    return _message_reads(db, [message], authorization.user_id)[0]


@router.patch(
    "/channels/{channel_id}/messages/{message_id}",
    response_model=ConversationMessageRead,
)
def edit_native_message(
    organization_id: uuid.UUID,
    channel_id: uuid.UUID,
    message_id: uuid.UUID,
    payload: MessageEditWrite,
    request: Request,
    authorization: Annotated[AuthorizationContext, Depends(_write)],
    db: Annotated[Session, Depends(get_db)],
) -> ConversationMessageRead:
    try:
        message = edit_message(
            db,
            organization_id=organization_id,
            channel_id=channel_id,
            message_id=message_id,
            user_id=authorization.user_id,
            body=payload.body,
            expected_revision=payload.expected_revision,
            request_id=_request_id(request),
        )
    except NativeChatError as exc:
        _raise_chat_error(exc)
    return _message_reads(db, [message], authorization.user_id)[0]


@router.delete(
    "/channels/{channel_id}/messages/{message_id}",
    response_model=ConversationMessageRead,
)
def retract_native_message(
    organization_id: uuid.UUID,
    channel_id: uuid.UUID,
    message_id: uuid.UUID,
    payload: MessageRetractWrite,
    request: Request,
    authorization: Annotated[AuthorizationContext, Depends(_write)],
    db: Annotated[Session, Depends(get_db)],
) -> ConversationMessageRead:
    try:
        message = retract_message(
            db,
            organization_id=organization_id,
            channel_id=channel_id,
            message_id=message_id,
            user_id=authorization.user_id,
            expected_revision=payload.expected_revision,
            request_id=_request_id(request),
        )
    except NativeChatError as exc:
        _raise_chat_error(exc)
    return _message_reads(db, [message], authorization.user_id)[0]


@router.get(
    "/channels/{channel_id}/messages/{root_message_id}/replies",
    response_model=list[ConversationMessageRead],
)
def list_replies(
    organization_id: uuid.UUID,
    channel_id: uuid.UUID,
    root_message_id: uuid.UUID,
    authorization: Annotated[AuthorizationContext, Depends(_read)],
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> list[ConversationMessageRead]:
    try:
        _, replies = list_thread_replies(
            db,
            organization_id=organization_id,
            channel_id=channel_id,
            root_message_id=root_message_id,
            user_id=authorization.user_id,
            limit=limit,
        )
    except NativeChatError as exc:
        _raise_chat_error(exc)
    return _message_reads(db, replies, authorization.user_id)


@router.post(
    "/channels/{channel_id}/messages/{root_message_id}/replies",
    response_model=ConversationMessageRead,
    status_code=status.HTTP_201_CREATED,
)
def send_reply(
    organization_id: uuid.UUID,
    channel_id: uuid.UUID,
    root_message_id: uuid.UUID,
    payload: ConversationMessageCreate,
    request: Request,
    authorization: Annotated[AuthorizationContext, Depends(_write)],
    db: Annotated[Session, Depends(get_db)],
    idempotency_key: Annotated[
        str | None,
        Header(alias="Idempotency-Key", max_length=128),
    ] = None,
) -> ConversationMessageRead:
    try:
        message = _send(
            db,
            organization_id=organization_id,
            channel_id=channel_id,
            actor_user_id=authorization.user_id,
            body=payload.body,
            idempotency_key=idempotency_key,
            request_id=_request_id(request),
            thread_root_id=root_message_id,
        )
    except NativeChatError as exc:
        _raise_chat_error(exc)
    return _message_reads(db, [message], authorization.user_id)[0]


@router.put(
    "/channels/{channel_id}/messages/{message_id}/reaction",
    response_model=ReactionRead,
)
def put_reaction(
    organization_id: uuid.UUID,
    channel_id: uuid.UUID,
    message_id: uuid.UUID,
    payload: ReactionWrite,
    authorization: Annotated[AuthorizationContext, Depends(_write)],
    db: Annotated[Session, Depends(get_db)],
) -> ReactionRead:
    try:
        add_reaction(
            db,
            organization_id=organization_id,
            channel_id=channel_id,
            message_id=message_id,
            user_id=authorization.user_id,
            reaction=payload.reaction,
        )
        _, message = visible_message(
            db,
            organization_id=organization_id,
            channel_id=channel_id,
            message_id=message_id,
            user_id=authorization.user_id,
        )
    except NativeChatError as exc:
        _raise_chat_error(exc)
    reactions = message_affordances(
        db,
        messages=[message],
        user_id=authorization.user_id,
    )[message_id]["reactions"]
    return next(item for item in reactions if item["reaction"] == payload.reaction)


@router.delete(
    "/channels/{channel_id}/messages/{message_id}/reaction",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_reaction(
    organization_id: uuid.UUID,
    channel_id: uuid.UUID,
    message_id: uuid.UUID,
    payload: ReactionWrite,
    authorization: Annotated[AuthorizationContext, Depends(_write)],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    try:
        remove_reaction(
            db,
            organization_id=organization_id,
            channel_id=channel_id,
            message_id=message_id,
            user_id=authorization.user_id,
            reaction=payload.reaction,
        )
    except NativeChatError as exc:
        _raise_chat_error(exc)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/channels/{channel_id}/read",
    response_model=ChannelUnreadRead,
)
def mark_channel_read(
    organization_id: uuid.UUID,
    channel_id: uuid.UUID,
    payload: MarkReadWrite,
    authorization: Annotated[AuthorizationContext, Depends(_read)],
    db: Annotated[Session, Depends(get_db)],
) -> ChannelUnreadRead:
    try:
        state = mark_read(
            db,
            organization_id=organization_id,
            channel_id=channel_id,
            user_id=authorization.user_id,
            through_message_id=payload.through_message_id,
        )
        channel, _ = visible_message(
            db,
            organization_id=organization_id,
            channel_id=channel_id,
            message_id=payload.through_message_id,
            user_id=authorization.user_id,
        )
        count, _ = unread_count(
            db,
            organization_id=organization_id,
            channel=channel,
            user_id=authorization.user_id,
        )
    except NativeChatError as exc:
        _raise_chat_error(exc)
    return ChannelUnreadRead(
        channel_id=channel_id,
        unread_count=count,
        last_read_at=state.last_read_at,
        latest_message_id=payload.through_message_id,
    )
