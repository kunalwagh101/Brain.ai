import uuid
from datetime import datetime
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent_models import AgentDefinition, AgentRun
from app.auth import get_current_user
from app.database import get_db
from app.evidence_ingestion import (
    MAX_EVIDENCE_BYTES,
    EvidenceConflictError,
    EvidenceIngestionError,
    ingest_evidence,
)
from app.evidence_models import EvidenceKind, EvidenceSourceStatus, EvidenceVisibility
from app.models import Membership, ResourceAccessLevel, User
from app.native_chat import (
    NativeChatConflictError,
    NativeChatError,
    can_write_channel,
    get_visible_channel,
    list_channel_messages,
    list_visible_channels,
    post_user_message,
)
from app.native_chat_models import (
    NativeChannel,
    NativeChannelMembership,
    NativeChannelVisibility,
    NativeMessage,
    NativeMessageActorKind,
    NativeMessageProjectionStatus,
)
from app.native_conversation import (
    add_reaction,
    channel_unread_summaries,
    edit_message,
    list_message_pins,
    list_saved_messages,
    list_thread_replies,
    mark_read,
    mark_thread_read,
    message_affordances,
    message_attachment_metadata,
    pin_message,
    remove_reaction,
    retract_message,
    save_message,
    thread_unread_summaries,
    unpin_message,
    unsave_message,
    visible_message,
)
from app.native_conversation_models import NativeMessagePin, NativeMessageSave
from app.permissions import AuthorizationContext, Permission, require_organization_permission

router = APIRouter(
    prefix="/organizations/{organization_id}/native-conversation",
    tags=["native-conversation"],
)
_read = require_organization_permission(Permission.RESOURCE_READ)
_write = require_organization_permission(Permission.NATIVE_CHAT_WRITE)


class ConversationMessageCreate(BaseModel):
    body: str = Field(default="", max_length=20_000)
    attachment_source_ids: list[uuid.UUID] = Field(default_factory=list, max_length=5)

    model_config = {"extra": "forbid"}


class MentionRead(BaseModel):
    user_id: uuid.UUID
    email: str
    display_name: str | None


class ReactionRead(BaseModel):
    reaction: str
    count: int
    reacted_by_me: bool


class AttachmentRead(BaseModel):
    source_id: uuid.UUID
    title: str
    filename: str
    kind: str
    media_type: str
    byte_size: int
    status: str
    retrieval_available: bool
    source_visibility: str
    native_channel_id: uuid.UUID | None


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
    message_sequence: int
    created_at: datetime
    reply_count: int
    thread_unread_count: int
    thread_latest_reply_id: uuid.UUID | None
    thread_first_unread_reply_id: uuid.UUID | None
    mentions: list[MentionRead]
    reactions: list[ReactionRead]
    attachments: list[AttachmentRead]
    revision: int
    edited_at: datetime | None
    deleted_at: datetime | None
    can_edit: bool
    can_delete: bool


class PinnedMessageRead(BaseModel):
    pin_id: uuid.UUID
    pinned_at: datetime
    pinned_by_user_id: uuid.UUID
    pinned_by_display_name: str
    message: ConversationMessageRead


class SavedMessageRead(BaseModel):
    save_id: uuid.UUID
    saved_at: datetime
    message: ConversationMessageRead


class ChannelUnreadRead(BaseModel):
    channel_id: uuid.UUID
    unread_count: int
    last_read_at: datetime | None
    latest_message_id: uuid.UUID | None
    first_unread_message_id: uuid.UUID | None


class MarkReadWrite(BaseModel):
    through_message_id: uuid.UUID

    model_config = {"extra": "forbid"}


class ThreadUnreadRead(BaseModel):
    root_message_id: uuid.UUID
    unread_count: int
    latest_reply_id: uuid.UUID | None
    first_unread_reply_id: uuid.UUID | None


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


class ChannelAttachmentUploadRead(BaseModel):
    source_id: uuid.UUID
    title: str
    filename: str
    kind: str
    media_type: str
    byte_size: int
    status: str
    retrieval_available: bool
    source_visibility: str
    native_channel_id: uuid.UUID | None


def _saved_user_id(
    db: Session,
    *,
    organization_id: uuid.UUID,
    current_user: User,
) -> uuid.UUID:
    if current_user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
        )
    membership = db.scalar(
        select(Membership.id).where(
            Membership.organization_id == organization_id,
            Membership.user_id == current_user.id,
        )
    )
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )
    return current_user.id


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


def _raise_evidence_error(exc: EvidenceIngestionError) -> None:
    if isinstance(exc, EvidenceConflictError):
        code = status.HTTP_409_CONFLICT
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
    roots = [message for message in messages if message.thread_root_id is None]
    thread_summaries = thread_unread_summaries(
        db,
        roots=roots,
        user_id=user_id,
    )
    attachment_map = message_attachment_metadata(
        db,
        messages=messages,
        user_id=user_id,
    )
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
                message_sequence=message.message_sequence,
                created_at=message.created_at,
                reply_count=int(extra["reply_count"]),
                thread_unread_count=(
                    thread_summaries.get(message.id, (0, None, None, None))[0]
                    if message.thread_root_id is None
                    else 0
                ),
                thread_latest_reply_id=(
                    thread_summaries.get(message.id, (0, None, None, None))[2]
                    if message.thread_root_id is None
                    else None
                ),
                thread_first_unread_reply_id=(
                    thread_summaries.get(message.id, (0, None, None, None))[3]
                    if message.thread_root_id is None
                    else None
                ),
                mentions=[] if deleted else extra["mentions"],
                reactions=[] if deleted else extra["reactions"],
                attachments=[] if deleted else attachment_map[message.id],
                revision=message.revision,
                edited_at=message.edited_at,
                deleted_at=message.deleted_at,
                can_edit=can_mutate,
                can_delete=can_mutate,
            )
        )
    return result


def _pin_reads(
    db: Session,
    rows: list[tuple[NativeMessagePin, NativeMessage]],
    user_id: uuid.UUID,
) -> list[PinnedMessageRead]:
    if not rows:
        return []
    pin_user_ids = {row[0].pinned_by_user_id for row in rows}
    pin_labels = {
        user.id: user.display_name or user.email
        for user in db.scalars(
            select(User).where(User.id.in_(pin_user_ids))
        )
    }
    messages = [message for _, message in rows]
    reads = {
        item.id: item
        for item in _message_reads(db, messages, user_id)
    }
    return [
        PinnedMessageRead(
            pin_id=pin.id,
            pinned_at=pin.created_at,
            pinned_by_user_id=pin.pinned_by_user_id,
            pinned_by_display_name=pin_labels.get(
                pin.pinned_by_user_id,
                "Unknown member",
            ),
            message=reads[message.id],
        )
        for pin, message in rows
        if message.id in reads
    ]


def _save_reads(
    db: Session,
    rows: list[tuple[NativeMessageSave, NativeMessage]],
    user_id: uuid.UUID,
) -> list[SavedMessageRead]:
    if not rows:
        return []
    messages = [message for _, message in rows]
    reads = {
        item.id: item
        for item in _message_reads(db, messages, user_id)
    }
    return [
        SavedMessageRead(
            save_id=save.id,
            saved_at=save.created_at,
            message=reads[message.id],
        )
        for save, message in rows
        if message.id in reads
    ]


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
        count, read_state, latest_message_id, first_unread_message_id = summaries[channel.id]
        result.append(
            ChannelUnreadRead(
                channel_id=channel.id,
                unread_count=count,
                last_read_at=read_state.last_read_at if read_state else None,
                latest_message_id=latest_message_id,
                first_unread_message_id=first_unread_message_id,
            )
        )
    return result


@router.post(
    "/channels/{channel_id}/attachments/uploads",
    response_model=ChannelAttachmentUploadRead,
    status_code=status.HTTP_201_CREATED,
)
async def upload_channel_attachment(
    organization_id: uuid.UUID,
    channel_id: uuid.UUID,
    request: Request,
    authorization: Annotated[AuthorizationContext, Depends(_write)],
    db: Annotated[Session, Depends(get_db)],
    file: Annotated[UploadFile, File()],
    kind: Annotated[EvidenceKind, Form()] = EvidenceKind.DOCUMENT,
    title: Annotated[str | None, Form(max_length=512)] = None,
    idempotency_key: Annotated[
        str | None,
        Header(alias="Idempotency-Key", max_length=128),
    ] = None,
) -> ChannelAttachmentUploadRead:
    channel = get_visible_channel(
        db,
        organization_id=organization_id,
        channel_id=channel_id,
        user_id=authorization.user_id,
    )
    if channel is None or not can_write_channel(
        db,
        channel,
        user_id=authorization.user_id,
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Channel not found")

    content = await file.read(MAX_EVIDENCE_BYTES + 1)
    if len(content) > MAX_EVIDENCE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={"code": "upload_too_large", "message": "Attachment exceeds 10 MB"},
        )

    visibility = (
        EvidenceVisibility.ORGANIZATION
        if channel.visibility == NativeChannelVisibility.ORGANIZATION
        else EvidenceVisibility.RESTRICTED
    )
    restricted_grants: dict[uuid.UUID, ResourceAccessLevel] | None = None
    if channel.visibility == NativeChannelVisibility.RESTRICTED:
        restricted_grants = {
            member.user_id: member.access
            for member in db.scalars(
                select(NativeChannelMembership).where(
                    NativeChannelMembership.organization_id == organization_id,
                    NativeChannelMembership.channel_id == channel_id,
                    NativeChannelMembership.revoked_at.is_(None),
                )
            )
        }

    try:
        source = ingest_evidence(
            db,
            organization_id=organization_id,
            actor_user_id=authorization.user_id,
            kind=kind,
            title=title,
            filename=file.filename or "upload",
            media_type=file.content_type or "application/octet-stream",
            content=content,
            visibility=visibility,
            occurred_at=None,
            idempotency_key=idempotency_key,
            request_id=_request_id(request),
            native_channel_id=channel.id,
            restricted_grants=restricted_grants,
        )
    except EvidenceIngestionError as exc:
        _raise_evidence_error(exc)

    return ChannelAttachmentUploadRead(
        source_id=source.id,
        title=source.title,
        filename=source.filename,
        kind=source.kind.value,
        media_type=source.media_type,
        byte_size=source.byte_size,
        status=source.status.value,
        retrieval_available=source.status == EvidenceSourceStatus.ACTIVE,
        source_visibility=source.source_visibility.value,
        native_channel_id=source.native_channel_id,
    )


@router.get(
    "/saved",
    response_model=list[SavedMessageRead],
)
def list_saved(
    organization_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> list[SavedMessageRead]:
    user_id = _saved_user_id(
        db,
        organization_id=organization_id,
        current_user=current_user,
    )
    rows = list_saved_messages(
        db,
        organization_id=organization_id,
        user_id=user_id,
        limit=limit,
    )
    return _save_reads(db, rows, user_id)


@router.put(
    "/channels/{channel_id}/messages/{message_id}/saved",
    response_model=SavedMessageRead,
)
def save_native_message(
    organization_id: uuid.UUID,
    channel_id: uuid.UUID,
    message_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> SavedMessageRead:
    user_id = _saved_user_id(
        db,
        organization_id=organization_id,
        current_user=current_user,
    )
    try:
        save = save_message(
            db,
            organization_id=organization_id,
            channel_id=channel_id,
            message_id=message_id,
            user_id=user_id,
        )
        _, message = visible_message(
            db,
            organization_id=organization_id,
            channel_id=channel_id,
            message_id=message_id,
            user_id=user_id,
        )
    except NativeChatError as exc:
        _raise_chat_error(exc)
    return _save_reads(
        db,
        [(save, message)],
        user_id,
    )[0]


@router.delete(
    "/channels/{channel_id}/messages/{message_id}/saved",
    status_code=status.HTTP_204_NO_CONTENT,
)
def unsave_native_message(
    organization_id: uuid.UUID,
    channel_id: uuid.UUID,
    message_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    user_id = _saved_user_id(
        db,
        organization_id=organization_id,
        current_user=current_user,
    )
    try:
        unsave_message(
            db,
            organization_id=organization_id,
            channel_id=channel_id,
            message_id=message_id,
            user_id=user_id,
        )
    except NativeChatError as exc:
        _raise_chat_error(exc)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/channels/{channel_id}/pins",
    response_model=list[PinnedMessageRead],
)
def list_pins(
    organization_id: uuid.UUID,
    channel_id: uuid.UUID,
    authorization: Annotated[AuthorizationContext, Depends(_read)],
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[PinnedMessageRead]:
    try:
        rows = list_message_pins(
            db,
            organization_id=organization_id,
            channel_id=channel_id,
            user_id=authorization.user_id,
            limit=limit,
        )
    except NativeChatError as exc:
        _raise_chat_error(exc)
    return _pin_reads(db, rows, authorization.user_id)


@router.put(
    "/channels/{channel_id}/messages/{message_id}/pin",
    response_model=PinnedMessageRead,
)
def pin_native_message(
    organization_id: uuid.UUID,
    channel_id: uuid.UUID,
    message_id: uuid.UUID,
    authorization: Annotated[AuthorizationContext, Depends(_write)],
    db: Annotated[Session, Depends(get_db)],
) -> PinnedMessageRead:
    try:
        pin = pin_message(
            db,
            organization_id=organization_id,
            channel_id=channel_id,
            message_id=message_id,
            user_id=authorization.user_id,
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
    return _pin_reads(
        db,
        [(pin, message)],
        authorization.user_id,
    )[0]


@router.delete(
    "/channels/{channel_id}/messages/{message_id}/pin",
    status_code=status.HTTP_204_NO_CONTENT,
)
def unpin_native_message(
    organization_id: uuid.UUID,
    channel_id: uuid.UUID,
    message_id: uuid.UUID,
    authorization: Annotated[AuthorizationContext, Depends(_write)],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    try:
        unpin_message(
            db,
            organization_id=organization_id,
            channel_id=channel_id,
            message_id=message_id,
            user_id=authorization.user_id,
        )
    except NativeChatError as exc:
        _raise_chat_error(exc)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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
    before_sequence: Annotated[int | None, Query(ge=1)] = None,
) -> list[ConversationMessageRead]:
    try:
        _, messages = list_channel_messages(
            db,
            organization_id=organization_id,
            channel_id=channel_id,
            user_id=authorization.user_id,
            limit=limit,
            before=before,
            before_sequence=before_sequence,
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
    attachment_source_ids: list[uuid.UUID],
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
        attachment_source_ids=attachment_source_ids,
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
            attachment_source_ids=payload.attachment_source_ids,
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
    before_sequence: Annotated[int | None, Query(ge=1)] = None,
) -> list[ConversationMessageRead]:
    try:
        _, replies = list_thread_replies(
            db,
            organization_id=organization_id,
            channel_id=channel_id,
            root_message_id=root_message_id,
            user_id=authorization.user_id,
            limit=limit,
            before_sequence=before_sequence,
        )
    except NativeChatError as exc:
        _raise_chat_error(exc)
    return _message_reads(db, replies, authorization.user_id)


@router.post(
    "/channels/{channel_id}/messages/{root_message_id}/thread-read",
    response_model=ThreadUnreadRead,
)
def mark_thread_as_read(
    organization_id: uuid.UUID,
    channel_id: uuid.UUID,
    root_message_id: uuid.UUID,
    payload: MarkReadWrite,
    authorization: Annotated[AuthorizationContext, Depends(_read)],
    db: Annotated[Session, Depends(get_db)],
) -> ThreadUnreadRead:
    try:
        mark_thread_read(
            db,
            organization_id=organization_id,
            channel_id=channel_id,
            root_message_id=root_message_id,
            user_id=authorization.user_id,
            through_message_id=payload.through_message_id,
        )
        _, root = visible_message(
            db,
            organization_id=organization_id,
            channel_id=channel_id,
            message_id=root_message_id,
            user_id=authorization.user_id,
        )
        summary = thread_unread_summaries(
            db,
            roots=[root],
            user_id=authorization.user_id,
        )[root.id]
    except NativeChatError as exc:
        _raise_chat_error(exc)
    return ThreadUnreadRead(
        root_message_id=root_message_id,
        unread_count=summary[0],
        latest_reply_id=summary[2],
        first_unread_reply_id=summary[3],
    )


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
            attachment_source_ids=payload.attachment_source_ids,
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
        summary = channel_unread_summaries(
            db,
            organization_id=organization_id,
            channels=[channel],
            user_id=authorization.user_id,
        )[channel.id]
        count, _, latest_message_id, first_unread_message_id = summary
    except NativeChatError as exc:
        _raise_chat_error(exc)
    return ChannelUnreadRead(
        channel_id=channel_id,
        unread_count=count,
        last_read_at=state.last_read_at,
        latest_message_id=latest_message_id,
        first_unread_message_id=first_unread_message_id,
    )
