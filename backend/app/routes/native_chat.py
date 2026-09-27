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
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agent_models import AgentDefinition, AgentRun
from app.database import get_db
from app.models import Membership, MembershipRole, ResourceAccessLevel, User
from app.native_chat import (
    NativeChatConflictError,
    NativeChatError,
    can_write_channel,
    create_channel,
    get_visible_channel,
    list_channel_messages,
    list_visible_channels,
    post_user_message,
    revoke_channel_member,
    set_channel_archived,
    update_channel_settings,
    upsert_channel_member,
)
from app.native_chat_models import (
    NativeChannel,
    NativeChannelMembership,
    NativeChannelStatus,
    NativeChannelVisibility,
    NativeMessage,
    NativeMessageActorKind,
    NativeMessageProjectionStatus,
)
from app.permissions import (
    AuthorizationContext,
    Permission,
    require_organization_permission,
    role_has_permission,
)

router = APIRouter(
    prefix="/organizations/{organization_id}/native-channels",
    tags=["native-chat"],
)
_read = require_organization_permission(Permission.RESOURCE_READ)
_write = require_organization_permission(Permission.NATIVE_CHAT_WRITE)


class NativeChannelCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=500)
    visibility: NativeChannelVisibility = NativeChannelVisibility.ORGANIZATION

    model_config = {"extra": "forbid"}


class NativeChannelSettingsWrite(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=500)
    expected_revision: int = Field(ge=1)

    model_config = {"extra": "forbid"}


class NativeChannelLifecycleWrite(BaseModel):
    expected_revision: int = Field(ge=1)

    model_config = {"extra": "forbid"}


class NativeChannelRead(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    work_graph_node_id: uuid.UUID | None
    name: str
    slug: str
    description: str | None
    team_id: uuid.UUID | None
    channel_group_id: uuid.UUID | None
    visibility: NativeChannelVisibility
    status: NativeChannelStatus
    created_by_user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None
    settings_revision: int
    member_count: int
    can_post: bool
    can_manage: bool
    can_manage_members: bool


class NativeChannelMemberWrite(BaseModel):
    access: ResourceAccessLevel = ResourceAccessLevel.READ

    model_config = {"extra": "forbid"}


class NativeChannelMemberInvite(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    access: ResourceAccessLevel = ResourceAccessLevel.READ

    model_config = {"extra": "forbid"}


class NativeChannelMemberRead(BaseModel):
    user_id: uuid.UUID
    email: str
    display_name: str | None
    role: MembershipRole
    access: ResourceAccessLevel
    revoked_at: datetime | None


class NativeMessageCreate(BaseModel):
    body: str = Field(min_length=1, max_length=20_000)

    model_config = {"extra": "forbid"}


class NativeMessageRead(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    channel_id: uuid.UUID
    actor_kind: NativeMessageActorKind
    author_user_id: uuid.UUID | None
    agent_run_id: uuid.UUID | None
    actor_display_name: str
    body: str
    body_sha256: str
    projection_status: NativeMessageProjectionStatus
    canonical_event_id: uuid.UUID | None
    created_at: datetime
    revision: int
    edited_at: datetime | None
    deleted_at: datetime | None


def _request_id(request: Request) -> str | None:
    value = getattr(request.state, "request_id", None)
    return value if isinstance(value, str) else None


def _raise_chat_error(exc: NativeChatError) -> None:
    if isinstance(exc, NativeChatConflictError):
        code = status.HTTP_409_CONFLICT
    elif exc.code in {"channel_not_found", "member_not_found", "agent_run_not_found"}:
        code = status.HTTP_404_NOT_FOUND
    else:
        code = status.HTTP_400_BAD_REQUEST
    raise HTTPException(
        status_code=code,
        detail={"code": exc.code, "message": str(exc)},
    ) from exc


def _can_manage(channel: NativeChannel, authorization: AuthorizationContext) -> bool:
    return channel.created_by_user_id == authorization.user_id or authorization.role in {
        MembershipRole.OWNER,
        MembershipRole.ADMIN,
    }


def _channel_read(
    db: Session,
    channel: NativeChannel,
    authorization: AuthorizationContext,
) -> NativeChannelRead:
    member_count = int(
        db.scalar(
            select(func.count())
            .select_from(NativeChannelMembership)
            .where(
                NativeChannelMembership.organization_id == channel.organization_id,
                NativeChannelMembership.channel_id == channel.id,
                NativeChannelMembership.revoked_at.is_(None),
            )
        )
        or 0
    )
    can_manage = (
        role_has_permission(authorization.role, Permission.NATIVE_CHAT_WRITE)
        and _can_manage(channel, authorization)
    )
    return NativeChannelRead(
        id=channel.id,
        organization_id=channel.organization_id,
        work_graph_node_id=channel.work_graph_node_id,
        name=channel.name,
        slug=channel.slug,
        description=channel.description,
        team_id=channel.team_id,
        channel_group_id=channel.channel_group_id,
        visibility=channel.visibility,
        status=channel.status,
        created_by_user_id=channel.created_by_user_id,
        created_at=channel.created_at,
        updated_at=channel.updated_at,
        archived_at=channel.archived_at,
        settings_revision=channel.settings_revision,
        member_count=member_count,
        can_post=(
            role_has_permission(authorization.role, Permission.NATIVE_CHAT_WRITE)
            and can_write_channel(db, channel, user_id=authorization.user_id)
        ),
        can_manage=can_manage,
        can_manage_members=(
            channel.visibility == NativeChannelVisibility.RESTRICTED
            and can_manage
        ),
    )


def _member_read(
    db: Session,
    membership: NativeChannelMembership,
) -> NativeChannelMemberRead:
    user = db.get(User, membership.user_id)
    organization_membership = db.scalar(
        select(Membership).where(
            Membership.organization_id == membership.organization_id,
            Membership.user_id == membership.user_id,
        )
    )
    if user is None or organization_membership is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Channel member identity is unavailable",
        )
    return NativeChannelMemberRead(
        user_id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=organization_membership.role,
        access=membership.access,
        revoked_at=membership.revoked_at,
    )


def _managed_restricted_channel(
    db: Session,
    *,
    organization_id: uuid.UUID,
    channel_id: uuid.UUID,
    authorization: AuthorizationContext,
) -> NativeChannel:
    channel = db.scalar(
        select(NativeChannel).where(
            NativeChannel.id == channel_id,
            NativeChannel.organization_id == organization_id,
            NativeChannel.visibility == NativeChannelVisibility.RESTRICTED,
        )
    )
    if channel is None or not _can_manage(channel, authorization):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Channel not found")
    return channel


def _actor_labels(db: Session, messages: list[NativeMessage]) -> dict[uuid.UUID, str]:
    user_ids = {
        message.author_user_id
        for message in messages
        if message.author_user_id is not None
    }
    run_ids = {
        message.agent_run_id
        for message in messages
        if message.agent_run_id is not None
    }
    labels: dict[uuid.UUID, str] = {}
    if user_ids:
        for user in db.scalars(select(User).where(User.id.in_(user_ids))):
            labels[user.id] = user.display_name or user.email
    if run_ids:
        rows = db.execute(
            select(AgentRun.id, AgentDefinition.name)
            .join(AgentDefinition, AgentDefinition.id == AgentRun.agent_definition_id)
            .where(AgentRun.id.in_(run_ids))
        ).all()
        for run_id, name in rows:
            labels[run_id] = f"{name} · agent"
    return labels


def _message_reads(db: Session, messages: list[NativeMessage]) -> list[NativeMessageRead]:
    labels = _actor_labels(db, messages)
    result: list[NativeMessageRead] = []
    for message in messages:
        actor_id = message.author_user_id or message.agent_run_id
        actor_label = labels.get(actor_id, "Unknown actor") if actor_id else "Unknown actor"
        result.append(
            NativeMessageRead(
                id=message.id,
                organization_id=message.organization_id,
                channel_id=message.channel_id,
                actor_kind=message.actor_kind,
                author_user_id=message.author_user_id,
                agent_run_id=message.agent_run_id,
                actor_display_name=actor_label,
                body="" if message.deleted_at is not None else message.body,
                body_sha256="" if message.deleted_at is not None else message.body_sha256,
                projection_status=message.projection_status,
                canonical_event_id=message.canonical_event_id,
                created_at=message.created_at,
                revision=message.revision,
                edited_at=message.edited_at,
                deleted_at=message.deleted_at,
            )
        )
    return result


@router.get("", response_model=list[NativeChannelRead])
def list_channels(
    organization_id: uuid.UUID,
    authorization: Annotated[AuthorizationContext, Depends(_read)],
    db: Annotated[Session, Depends(get_db)],
    include_archived: bool = False,
) -> list[NativeChannelRead]:
    channels = list_visible_channels(
        db,
        organization_id=organization_id,
        user_id=authorization.user_id,
        include_archived=include_archived,
    )
    return [_channel_read(db, channel, authorization) for channel in channels]


@router.post("", response_model=NativeChannelRead, status_code=status.HTTP_201_CREATED)
def create_native_channel(
    organization_id: uuid.UUID,
    payload: NativeChannelCreate,
    request: Request,
    authorization: Annotated[AuthorizationContext, Depends(_write)],
    db: Annotated[Session, Depends(get_db)],
) -> NativeChannelRead:
    try:
        channel = create_channel(
            db,
            organization_id=organization_id,
            actor_user_id=authorization.user_id,
            name=payload.name,
            description=payload.description,
            visibility=payload.visibility,
            request_id=_request_id(request),
        )
    except NativeChatError as exc:
        _raise_chat_error(exc)
    return _channel_read(db, channel, authorization)


@router.get("/{channel_id}", response_model=NativeChannelRead)
def read_channel(
    organization_id: uuid.UUID,
    channel_id: uuid.UUID,
    authorization: Annotated[AuthorizationContext, Depends(_read)],
    db: Annotated[Session, Depends(get_db)],
) -> NativeChannelRead:
    channel = get_visible_channel(
        db,
        organization_id=organization_id,
        channel_id=channel_id,
        user_id=authorization.user_id,
    )
    if channel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Channel not found")
    return _channel_read(db, channel, authorization)


@router.patch("/{channel_id}/settings", response_model=NativeChannelRead)
def edit_channel_settings(
    organization_id: uuid.UUID,
    channel_id: uuid.UUID,
    payload: NativeChannelSettingsWrite,
    request: Request,
    authorization: Annotated[AuthorizationContext, Depends(_write)],
    db: Annotated[Session, Depends(get_db)],
) -> NativeChannelRead:
    try:
        channel = update_channel_settings(
            db,
            organization_id=organization_id,
            channel_id=channel_id,
            actor_user_id=authorization.user_id,
            actor_role=authorization.role,
            expected_revision=payload.expected_revision,
            name=payload.name,
            description=payload.description,
            request_id=_request_id(request),
        )
    except NativeChatError as exc:
        _raise_chat_error(exc)
    return _channel_read(db, channel, authorization)


@router.post("/{channel_id}/archive", response_model=NativeChannelRead)
def archive_channel(
    organization_id: uuid.UUID,
    channel_id: uuid.UUID,
    payload: NativeChannelLifecycleWrite,
    request: Request,
    authorization: Annotated[AuthorizationContext, Depends(_write)],
    db: Annotated[Session, Depends(get_db)],
) -> NativeChannelRead:
    try:
        channel = set_channel_archived(
            db,
            organization_id=organization_id,
            channel_id=channel_id,
            actor_user_id=authorization.user_id,
            actor_role=authorization.role,
            expected_revision=payload.expected_revision,
            archived=True,
            request_id=_request_id(request),
        )
    except NativeChatError as exc:
        _raise_chat_error(exc)
    return _channel_read(db, channel, authorization)


@router.post("/{channel_id}/restore", response_model=NativeChannelRead)
def restore_channel(
    organization_id: uuid.UUID,
    channel_id: uuid.UUID,
    payload: NativeChannelLifecycleWrite,
    request: Request,
    authorization: Annotated[AuthorizationContext, Depends(_write)],
    db: Annotated[Session, Depends(get_db)],
) -> NativeChannelRead:
    try:
        channel = set_channel_archived(
            db,
            organization_id=organization_id,
            channel_id=channel_id,
            actor_user_id=authorization.user_id,
            actor_role=authorization.role,
            expected_revision=payload.expected_revision,
            archived=False,
            request_id=_request_id(request),
        )
    except NativeChatError as exc:
        _raise_chat_error(exc)
    return _channel_read(db, channel, authorization)


@router.get("/{channel_id}/members", response_model=list[NativeChannelMemberRead])
def list_channel_members(
    organization_id: uuid.UUID,
    channel_id: uuid.UUID,
    authorization: Annotated[AuthorizationContext, Depends(_write)],
    db: Annotated[Session, Depends(get_db)],
) -> list[NativeChannelMemberRead]:
    _managed_restricted_channel(
        db,
        organization_id=organization_id,
        channel_id=channel_id,
        authorization=authorization,
    )
    memberships = list(
        db.scalars(
            select(NativeChannelMembership)
            .where(
                NativeChannelMembership.organization_id == organization_id,
                NativeChannelMembership.channel_id == channel_id,
                NativeChannelMembership.revoked_at.is_(None),
            )
            .order_by(NativeChannelMembership.created_at, NativeChannelMembership.id)
        )
    )
    return [_member_read(db, membership) for membership in memberships]


@router.post(
    "/{channel_id}/members",
    response_model=NativeChannelMemberRead,
    status_code=status.HTTP_201_CREATED,
)
def invite_channel_member(
    organization_id: uuid.UUID,
    channel_id: uuid.UUID,
    payload: NativeChannelMemberInvite,
    request: Request,
    authorization: Annotated[AuthorizationContext, Depends(_write)],
    db: Annotated[Session, Depends(get_db)],
) -> NativeChannelMemberRead:
    _managed_restricted_channel(
        db,
        organization_id=organization_id,
        channel_id=channel_id,
        authorization=authorization,
    )
    email = payload.email.strip().lower()
    target = db.scalar(
        select(User)
        .join(Membership, Membership.user_id == User.id)
        .where(
            Membership.organization_id == organization_id,
            User.email == email,
            User.status == "active",
        )
    )
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
    try:
        membership = upsert_channel_member(
            db,
            organization_id=organization_id,
            channel_id=channel_id,
            actor_user_id=authorization.user_id,
            actor_role=authorization.role,
            user_id=target.id,
            access=payload.access,
            request_id=_request_id(request),
        )
    except NativeChatError as exc:
        _raise_chat_error(exc)
    return _member_read(db, membership)


@router.put("/{channel_id}/members/{user_id}", response_model=NativeChannelMemberRead)
def grant_channel_member(
    organization_id: uuid.UUID,
    channel_id: uuid.UUID,
    user_id: uuid.UUID,
    payload: NativeChannelMemberWrite,
    request: Request,
    authorization: Annotated[AuthorizationContext, Depends(_write)],
    db: Annotated[Session, Depends(get_db)],
) -> NativeChannelMemberRead:
    try:
        membership = upsert_channel_member(
            db,
            organization_id=organization_id,
            channel_id=channel_id,
            actor_user_id=authorization.user_id,
            actor_role=authorization.role,
            user_id=user_id,
            access=payload.access,
            request_id=_request_id(request),
        )
    except NativeChatError as exc:
        _raise_chat_error(exc)
    return _member_read(db, membership)


@router.delete("/{channel_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_member(
    organization_id: uuid.UUID,
    channel_id: uuid.UUID,
    user_id: uuid.UUID,
    request: Request,
    authorization: Annotated[AuthorizationContext, Depends(_write)],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    try:
        revoke_channel_member(
            db,
            organization_id=organization_id,
            channel_id=channel_id,
            actor_user_id=authorization.user_id,
            actor_role=authorization.role,
            user_id=user_id,
            request_id=_request_id(request),
        )
    except NativeChatError as exc:
        _raise_chat_error(exc)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{channel_id}/messages", response_model=list[NativeMessageRead])
def list_messages(
    organization_id: uuid.UUID,
    channel_id: uuid.UUID,
    authorization: Annotated[AuthorizationContext, Depends(_read)],
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    before: datetime | None = None,
) -> list[NativeMessageRead]:
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
    return _message_reads(db, messages)


@router.post(
    "/{channel_id}/messages",
    response_model=NativeMessageRead,
    status_code=status.HTTP_201_CREATED,
)
def send_message(
    organization_id: uuid.UUID,
    channel_id: uuid.UUID,
    payload: NativeMessageCreate,
    request: Request,
    authorization: Annotated[AuthorizationContext, Depends(_write)],
    db: Annotated[Session, Depends(get_db)],
    idempotency_key: Annotated[
        str | None,
        Header(alias="Idempotency-Key", max_length=128),
    ] = None,
) -> NativeMessageRead:
    try:
        message = post_user_message(
            db,
            organization_id=organization_id,
            channel_id=channel_id,
            actor_user_id=authorization.user_id,
            body=payload.body,
            idempotency_key=idempotency_key,
            request_id=_request_id(request),
        )
    except NativeChatError as exc:
        _raise_chat_error(exc)
    return _message_reads(db, [message])[0]
