import hashlib
import json
import re
import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.agent_models import AgentRun
from app.data_governance import append_audit_event
from app.evidence_ingestion import evidence_source_visible_to_user
from app.evidence_models import EvidenceSource, EvidenceSourceStatus, EvidenceVisibility
from app.models import (
    CanonicalEvent,
    IntegrationConnection,
    IntegrationHealth,
    IntegrationStatus,
    Membership,
    MembershipRole,
    RawEvent,
    RawEventStatus,
    ResourceAccessLevel,
    ResourceGrant,
    User,
)
from app.native_chat_models import (
    NativeChannel,
    NativeChannelMembership,
    NativeChannelStatus,
    NativeChannelVisibility,
    NativeMessage,
    NativeMessageActorKind,
    NativeMessageProjectionStatus,
    NativeMessageRevision,
)
from app.native_conversation_models import NativeMessageAttachment, NativeMessageMention
from app.permissions import Permission, role_has_permission
from app.raw_events import persist_raw_event
from app.search import project_search_document
from app.search_models import SearchDocument, SearchEmbeddingStatus
from app.work_graph import create_manual_edge, project_canonical_event
from app.work_graph_models import WorkGraphEdgeType, WorkGraphNode, WorkGraphNodeType

NATIVE_CHAT_PROVIDER = "brain_native"
NATIVE_CHAT_ACCOUNT = "brain:native-chat-v1"
MAX_MESSAGE_CHARS = 20_000
MAX_CHANNEL_NAME_CHARS = 160
MAX_CHANNEL_DESCRIPTION_CHARS = 500
_SLUG_RE = re.compile(r"[^a-z0-9]+")
_MENTION_EMAIL_RE = re.compile(
    r"(?<![A-Za-z0-9._%+\-])@([A-Za-z0-9.!#$%&'*+/=?^_`{|}~\-]+"
    r"@[A-Za-z0-9.-]+\.[A-Za-z]{2,63})",
    re.IGNORECASE,
)


class NativeChatError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code[:128]


class NativeChatConflictError(NativeChatError):
    pass


def _source_visibility(channel: NativeChannel) -> str:
    return (
        "organization"
        if channel.visibility == NativeChannelVisibility.ORGANIZATION
        else "restricted"
    )


def _normalize_channel_name(value: str) -> str:
    name = " ".join(value.strip().split())
    if not name or len(name) > MAX_CHANNEL_NAME_CHARS:
        raise NativeChatError("invalid_channel_name", "Channel name is invalid")
    return name


def _slugify(name: str) -> str:
    slug = _SLUG_RE.sub("-", name.casefold()).strip("-")[:96]
    if not slug:
        raise NativeChatError(
            "invalid_channel_slug",
            "Channel name cannot produce a channel slug",
        )
    return slug


def _normalize_description(value: str | None) -> str | None:
    if value is None:
        return None
    description = " ".join(value.strip().split())
    if len(description) > MAX_CHANNEL_DESCRIPTION_CHARS:
        raise NativeChatError(
            "invalid_channel_description",
            "Channel description is too long",
        )
    return description or None


def normalize_message_body(value: str, *, allow_empty: bool = False) -> str:
    body = value.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not body and not allow_empty:
        raise NativeChatError("empty_message", "Message must not be empty")
    if len(body) > MAX_MESSAGE_CHARS:
        raise NativeChatError(
            "message_too_large",
            "Message exceeds the 20,000 character limit",
        )
    return body


def _managed_connection(
    db: Session,
    *,
    organization_id: uuid.UUID,
    actor_user_id: uuid.UUID,
) -> IntegrationConnection:
    connection = db.scalar(
        select(IntegrationConnection).where(
            IntegrationConnection.organization_id == organization_id,
            IntegrationConnection.provider == NATIVE_CHAT_PROVIDER,
            IntegrationConnection.external_account_id == NATIVE_CHAT_ACCOUNT,
        )
    )
    if connection is not None:
        if connection.status != IntegrationStatus.ACTIVE:
            raise NativeChatConflictError(
                "native_chat_disabled",
                "Brain native chat is disabled for this organization",
            )
        return connection

    connection = IntegrationConnection(
        organization_id=organization_id,
        provider=NATIVE_CHAT_PROVIDER,
        external_account_id=NATIVE_CHAT_ACCOUNT,
        display_name="Brain native channels",
        status=IntegrationStatus.ACTIVE,
        health=IntegrationHealth.HEALTHY,
        scopes=["native_chat:read", "native_chat:write"],
        provider_metadata={"managed_by": "brain", "adapter": "native-chat-v1"},
        secret_ref=None,
        created_by_user_id=actor_user_id,
    )
    db.add(connection)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        connection = db.scalar(
            select(IntegrationConnection).where(
                IntegrationConnection.organization_id == organization_id,
                IntegrationConnection.provider == NATIVE_CHAT_PROVIDER,
                IntegrationConnection.external_account_id == NATIVE_CHAT_ACCOUNT,
            )
        )
        if connection is None or connection.status != IntegrationStatus.ACTIVE:
            raise NativeChatConflictError(
                "native_chat_unavailable",
                "Brain native chat connection could not be created",
            ) from None
    db.refresh(connection)
    return connection


def _active_membership(
    db: Session,
    *,
    organization_id: uuid.UUID,
    channel_id: uuid.UUID,
    user_id: uuid.UUID,
) -> NativeChannelMembership | None:
    return db.scalar(
        select(NativeChannelMembership).where(
            NativeChannelMembership.organization_id == organization_id,
            NativeChannelMembership.channel_id == channel_id,
            NativeChannelMembership.user_id == user_id,
            NativeChannelMembership.revoked_at.is_(None),
        )
    )


def can_read_channel(
    db: Session,
    channel: NativeChannel,
    *,
    user_id: uuid.UUID,
) -> bool:
    if channel.visibility == NativeChannelVisibility.ORGANIZATION:
        return True
    return _active_membership(
        db,
        organization_id=channel.organization_id,
        channel_id=channel.id,
        user_id=user_id,
    ) is not None


def can_write_channel(
    db: Session,
    channel: NativeChannel,
    *,
    user_id: uuid.UUID,
) -> bool:
    if channel.status != NativeChannelStatus.ACTIVE:
        return False
    if channel.visibility == NativeChannelVisibility.ORGANIZATION:
        return True
    membership = _active_membership(
        db,
        organization_id=channel.organization_id,
        channel_id=channel.id,
        user_id=user_id,
    )
    return membership is not None and membership.access == ResourceAccessLevel.WRITE


def get_visible_channel(
    db: Session,
    *,
    organization_id: uuid.UUID,
    channel_id: uuid.UUID,
    user_id: uuid.UUID,
) -> NativeChannel | None:
    channel = db.scalar(
        select(NativeChannel).where(
            NativeChannel.id == channel_id,
            NativeChannel.organization_id == organization_id,
        )
    )
    if channel is None or not can_read_channel(db, channel, user_id=user_id):
        return None
    return channel


def list_visible_channels(
    db: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    include_archived: bool = False,
) -> list[NativeChannel]:
    query = select(NativeChannel).where(
        NativeChannel.organization_id == organization_id
    )
    if not include_archived:
        query = query.where(NativeChannel.status == NativeChannelStatus.ACTIVE)
    channels = list(
        db.scalars(query.order_by(NativeChannel.name, NativeChannel.id))
    )
    return [
        channel
        for channel in channels
        if can_read_channel(db, channel, user_id=user_id)
    ]


def _grant_node(
    db: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    node_id: uuid.UUID,
    access: ResourceAccessLevel,
    granted_by_user_id: uuid.UUID,
) -> None:
    existing = db.scalar(
        select(ResourceGrant).where(
            ResourceGrant.organization_id == organization_id,
            ResourceGrant.resource_type == "work_graph.node",
            ResourceGrant.resource_id == str(node_id),
            ResourceGrant.user_id == user_id,
        )
    )
    if existing is None:
        db.add(
            ResourceGrant(
                organization_id=organization_id,
                resource_type="work_graph.node",
                resource_id=str(node_id),
                user_id=user_id,
                access=access,
                created_by_user_id=granted_by_user_id,
            )
        )
    else:
        existing.access = access
        existing.created_by_user_id = granted_by_user_id


def _channel_evidence_node_ids(
    db: Session,
    channel: NativeChannel,
) -> list[uuid.UUID]:
    current_ids = set(
        db.scalars(
            select(NativeMessage.canonical_event_id).where(
                NativeMessage.organization_id == channel.organization_id,
                NativeMessage.channel_id == channel.id,
                NativeMessage.canonical_event_id.is_not(None),
            )
        )
    )
    revision_ids = set(
        db.scalars(
            select(NativeMessageRevision.canonical_event_id).where(
                NativeMessageRevision.organization_id == channel.organization_id,
                NativeMessageRevision.channel_id == channel.id,
                NativeMessageRevision.canonical_event_id.is_not(None),
            )
        )
    )
    canonical_ids = current_ids | revision_ids
    node_ids = set()
    if canonical_ids:
        node_ids.update(
            db.scalars(
                select(WorkGraphNode.id).where(
                    WorkGraphNode.organization_id == channel.organization_id,
                    WorkGraphNode.canonical_event_id.in_(canonical_ids),
                )
            )
        )
    node_ids.update(
        node_id
        for node_id in db.scalars(
            select(SearchDocument.work_graph_node_id).where(
                SearchDocument.organization_id == channel.organization_id,
                SearchDocument.channel_id == str(channel.id),
                SearchDocument.work_graph_node_id.is_not(None),
            )
        )
        if node_id is not None
    )
    return list(node_ids)


def _grant_channel_history(
    db: Session,
    *,
    channel: NativeChannel,
    user_id: uuid.UUID,
    access: ResourceAccessLevel,
    granted_by_user_id: uuid.UUID,
) -> None:
    if channel.work_graph_node_id is not None:
        _grant_node(
            db,
            organization_id=channel.organization_id,
            user_id=user_id,
            node_id=channel.work_graph_node_id,
            access=access,
            granted_by_user_id=granted_by_user_id,
        )
    for node_id in _channel_evidence_node_ids(db, channel):
        _grant_node(
            db,
            organization_id=channel.organization_id,
            user_id=user_id,
            node_id=node_id,
            access=access,
            granted_by_user_id=granted_by_user_id,
        )


def _revoke_channel_grants(
    db: Session,
    *,
    channel: NativeChannel,
    user_id: uuid.UUID,
) -> None:
    node_ids = _channel_evidence_node_ids(db, channel)
    if channel.work_graph_node_id is not None:
        node_ids.append(channel.work_graph_node_id)
    if not node_ids:
        return
    db.execute(
        delete(ResourceGrant).where(
            ResourceGrant.organization_id == channel.organization_id,
            ResourceGrant.resource_type == "work_graph.node",
            ResourceGrant.user_id == user_id,
            ResourceGrant.resource_id.in_(
                [str(node_id) for node_id in set(node_ids)]
            ),
        )
    )


def create_channel(
    db: Session,
    *,
    organization_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    name: str,
    description: str | None,
    visibility: NativeChannelVisibility,
    request_id: str | None = None,
) -> NativeChannel:
    normalized_name = _normalize_channel_name(name)
    slug = _slugify(normalized_name)
    normalized_description = _normalize_description(description)
    _managed_connection(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
    )

    channel_id = uuid.uuid4()
    track_id = uuid.uuid4()
    visibility_value = (
        "organization"
        if visibility == NativeChannelVisibility.ORGANIZATION
        else "restricted"
    )
    track = WorkGraphNode(
        id=track_id,
        organization_id=organization_id,
        node_type=WorkGraphNodeType.TRACK,
        stable_key=f"native:track:{channel_id}",
        display_name=normalized_name,
        source_visibility=visibility_value,
        source_acl=[],
        attributes={
            "source": "brain_native",
            "provider": NATIVE_CHAT_PROVIDER,
            "native_channel_id": str(channel_id),
            "channel_slug": slug,
            "created_by_user_id": str(actor_user_id),
        },
    )
    channel = NativeChannel(
        id=channel_id,
        organization_id=organization_id,
        work_graph_node_id=track_id,
        name=normalized_name,
        slug=slug,
        description=normalized_description,
        visibility=visibility,
        status=NativeChannelStatus.ACTIVE,
        created_by_user_id=actor_user_id,
    )
    db.add_all([track, channel])

    if visibility == NativeChannelVisibility.RESTRICTED:
        membership = NativeChannelMembership(
            organization_id=organization_id,
            channel_id=channel_id,
            user_id=actor_user_id,
            access=ResourceAccessLevel.WRITE,
            granted_by_user_id=actor_user_id,
        )
        db.add(membership)
        _grant_node(
            db,
            organization_id=organization_id,
            user_id=actor_user_id,
            node_id=track_id,
            access=ResourceAccessLevel.WRITE,
            granted_by_user_id=actor_user_id,
        )

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise NativeChatConflictError(
            "channel_slug_conflict",
            "A Brain channel with this name already exists",
        ) from exc
    db.refresh(channel)

    append_audit_event(
        db,
        organization_id=organization_id,
        event_key=f"native_chat.channel.created:{channel.id}",
        event_type="native_chat.channel.created",
        outcome="succeeded",
        actor_user_id=actor_user_id,
        resource_type="native_channel",
        resource_id=channel.id,
        request_id=request_id,
        metadata={
            "visibility": visibility.value,
            "work_graph_node_id": str(track_id),
        },
    )
    return channel


def _can_manage_members(
    channel: NativeChannel,
    *,
    actor_user_id: uuid.UUID,
    actor_role: MembershipRole,
) -> bool:
    return channel.created_by_user_id == actor_user_id or actor_role in {
        MembershipRole.OWNER,
        MembershipRole.ADMIN,
    }


def upsert_channel_member(
    db: Session,
    *,
    organization_id: uuid.UUID,
    channel_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    actor_role: MembershipRole,
    user_id: uuid.UUID,
    access: ResourceAccessLevel,
    request_id: str | None = None,
) -> NativeChannelMembership:
    channel = db.scalar(
        select(NativeChannel).where(
            NativeChannel.id == channel_id,
            NativeChannel.organization_id == organization_id,
        )
    )
    if (
        channel is None
        or channel.visibility != NativeChannelVisibility.RESTRICTED
    ):
        raise NativeChatError("channel_not_found", "Channel not found")
    if not _can_manage_members(
        channel,
        actor_user_id=actor_user_id,
        actor_role=actor_role,
    ):
        raise NativeChatError("channel_not_found", "Channel not found")

    target = db.scalar(
        select(Membership).where(
            Membership.organization_id == organization_id,
            Membership.user_id == user_id,
        )
    )
    user = db.get(User, user_id)
    if target is None or user is None or user.status != "active":
        raise NativeChatError("member_not_found", "Organization member not found")
    if (
        access == ResourceAccessLevel.WRITE
        and not role_has_permission(target.role, Permission.NATIVE_CHAT_WRITE)
    ):
        raise NativeChatError(
            "member_cannot_write",
            "This organization role cannot receive native chat write access",
        )

    membership = db.scalar(
        select(NativeChannelMembership).where(
            NativeChannelMembership.organization_id == organization_id,
            NativeChannelMembership.channel_id == channel_id,
            NativeChannelMembership.user_id == user_id,
        )
    )
    if membership is None:
        membership = NativeChannelMembership(
            organization_id=organization_id,
            channel_id=channel_id,
            user_id=user_id,
            access=access,
            granted_by_user_id=actor_user_id,
        )
        db.add(membership)
    else:
        membership.access = access
        membership.granted_by_user_id = actor_user_id
        membership.revoked_at = None
    _grant_channel_history(
        db,
        channel=channel,
        user_id=user_id,
        access=access,
        granted_by_user_id=actor_user_id,
    )
    db.commit()
    db.refresh(membership)

    append_audit_event(
        db,
        organization_id=organization_id,
        event_key=(
            f"native_chat.member.granted:{channel.id}:{user_id}:{membership.id}"
        ),
        event_type="native_chat.member.granted",
        outcome="succeeded",
        actor_user_id=actor_user_id,
        resource_type="native_channel",
        resource_id=channel.id,
        request_id=request_id,
        metadata={"user_id": str(user_id), "access": access.value},
    )
    return membership


def revoke_channel_member(
    db: Session,
    *,
    organization_id: uuid.UUID,
    channel_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    actor_role: MembershipRole,
    user_id: uuid.UUID,
    request_id: str | None = None,
) -> None:
    channel = db.scalar(
        select(NativeChannel).where(
            NativeChannel.id == channel_id,
            NativeChannel.organization_id == organization_id,
        )
    )
    if (
        channel is None
        or channel.visibility != NativeChannelVisibility.RESTRICTED
    ):
        raise NativeChatError("channel_not_found", "Channel not found")
    if not _can_manage_members(
        channel,
        actor_user_id=actor_user_id,
        actor_role=actor_role,
    ):
        raise NativeChatError("channel_not_found", "Channel not found")
    if user_id == channel.created_by_user_id:
        raise NativeChatConflictError(
            "channel_owner_membership",
            "The channel creator cannot be revoked from a restricted channel",
        )

    membership = db.scalar(
        select(NativeChannelMembership).where(
            NativeChannelMembership.organization_id == organization_id,
            NativeChannelMembership.channel_id == channel_id,
            NativeChannelMembership.user_id == user_id,
            NativeChannelMembership.revoked_at.is_(None),
        )
    )
    if membership is None:
        raise NativeChatError("channel_not_found", "Channel not found")

    membership.revoked_at = datetime.now(UTC)
    _revoke_channel_grants(db, channel=channel, user_id=user_id)
    db.commit()
    append_audit_event(
        db,
        organization_id=organization_id,
        event_key=(
            f"native_chat.member.revoked:{channel.id}:{user_id}:{membership.id}"
        ),
        event_type="native_chat.member.revoked",
        outcome="succeeded",
        actor_user_id=actor_user_id,
        resource_type="native_channel",
        resource_id=channel.id,
        request_id=request_id,
        metadata={"user_id": str(user_id)},
    )


def _message_payload(
    message: NativeMessage,
    channel: NativeChannel,
) -> bytes:
    payload = {
        "native_message_id": str(message.id),
        "channel_id": str(channel.id),
        "thread_root_id": str(message.thread_root_id) if message.thread_root_id else None,
        "channel_name": channel.name,
        "channel_slug": channel.slug,
        "actor_kind": message.actor_kind.value,
        "author_user_id": (
            str(message.author_user_id) if message.author_user_id else None
        ),
        "agent_run_id": str(message.agent_run_id) if message.agent_run_id else None,
        "text": message.body,
        "body_sha256": message.body_sha256,
        "revision": message.revision,
        "edited_at": message.edited_at.isoformat() if message.edited_at else None,
        "deleted_at": message.deleted_at.isoformat() if message.deleted_at else None,
    }
    return json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode()


def _grant_message_evidence(
    db: Session,
    *,
    channel: NativeChannel,
    evidence_node_id: uuid.UUID,
    commit: bool = True,
) -> None:
    if channel.visibility != NativeChannelVisibility.RESTRICTED:
        return
    memberships = list(
        db.scalars(
            select(NativeChannelMembership).where(
                NativeChannelMembership.organization_id == channel.organization_id,
                NativeChannelMembership.channel_id == channel.id,
                NativeChannelMembership.revoked_at.is_(None),
            )
        )
    )
    for membership in memberships:
        _grant_node(
            db,
            organization_id=channel.organization_id,
            user_id=membership.user_id,
            node_id=evidence_node_id,
            access=membership.access,
            granted_by_user_id=membership.granted_by_user_id,
        )
    if commit:
        db.commit()
    else:
        db.flush()


def _project_message(
    db: Session,
    *,
    message: NativeMessage,
    channel: NativeChannel,
    actor_user_id_for_audit: uuid.UUID,
) -> NativeMessage:
    connection = _managed_connection(
        db,
        organization_id=channel.organization_id,
        actor_user_id=actor_user_id_for_audit,
    )
    visibility = _source_visibility(channel)

    raw = db.get(RawEvent, message.raw_event_id) if message.raw_event_id else None
    if raw is None:
        raw_result = persist_raw_event(
            db,
            organization_id=channel.organization_id,
            integration_connection_id=connection.id,
            provider=NATIVE_CHAT_PROVIDER,
            source_event_id=f"native-message:{message.id}",
            source_event_type="native.message.created",
            delivery_kind="native",
            raw_payload=_message_payload(message, channel),
            content_type="application/json",
            source_visibility=visibility,
            source_acl=[],
            source_timestamp=message.created_at,
        )
        raw = raw_result.event
        message = db.get(NativeMessage, message.id) or message
        message.raw_event_id = raw.id
        db.commit()
        db.refresh(message)

    canonical = (
        db.get(CanonicalEvent, message.canonical_event_id)
        if message.canonical_event_id
        else None
    )
    if canonical is None:
        actor_type = (
            "brain_user"
            if message.actor_kind == NativeMessageActorKind.USER
            else "brain_agent"
        )
        actor_external_id = (
            str(message.author_user_id)
            if message.author_user_id is not None
            else str(message.agent_run_id)
        )
        canonical = CanonicalEvent(
            organization_id=channel.organization_id,
            raw_event_id=raw.id,
            integration_connection_id=connection.id,
            resolved_user_id=message.author_user_id,
            schema_version=1,
            event_type="native.message.created",
            action="created",
            actor_type=actor_type,
            actor_external_id=actor_external_id,
            actor_display_name=None,
            object_type="native_message",
            object_external_id=str(message.id),
            object_display_name=channel.name,
            source_provider=NATIVE_CHAT_PROVIDER,
            source_event_id=raw.source_event_id,
            source_event_type=raw.source_event_type,
            occurred_at=message.created_at,
            source_visibility=visibility,
            source_acl=[],
            provenance={
                "raw_event_id": str(raw.id),
                "integration_connection_id": str(connection.id),
                "payload_sha256": raw.payload_sha256,
                "native_message_id": str(message.id),
                "channel_id": str(channel.id),
                "thread_root_id": (
                    str(message.thread_root_id) if message.thread_root_id else None
                ),
                "track_node_id": str(channel.work_graph_node_id),
            },
            event_metadata={
                "text": message.body,
                "channel_id": str(channel.id),
                "thread_root_id": (
                    str(message.thread_root_id) if message.thread_root_id else None
                ),
                "channel_name": channel.name,
                "track_node_id": str(channel.work_graph_node_id),
                "actor_kind": message.actor_kind.value,
                "agent_run_id": (
                    str(message.agent_run_id)
                    if message.agent_run_id
                    else None
                ),
            },
        )
        raw.processing_status = RawEventStatus.PROCESSED
        raw.last_error_code = None
        db.add(canonical)
        db.flush()
        message.canonical_event_id = canonical.id
        db.commit()
        db.refresh(message)

    evidence_node = project_canonical_event(db, canonical)
    if channel.work_graph_node_id is None:
        raise NativeChatConflictError(
            "channel_track_missing",
            "Native channel is missing its Work Graph track",
        )
    create_manual_edge(
        db,
        organization_id=channel.organization_id,
        source_node_id=channel.work_graph_node_id,
        target_node_id=evidence_node.id,
        edge_type=WorkGraphEdgeType.RELATED_TO,
        actor_user_id=actor_user_id_for_audit,
        reason="Brain native channel message evidence",
    )

    document = project_search_document(db, canonical)
    document.title = f"#{channel.name}"
    document.content = message.body
    document.channel_id = str(channel.id)
    document.source_visibility = visibility
    document.embedding = None
    document.embedding_model = None
    document.embedding_status = SearchEmbeddingStatus.PENDING
    document.embedding_attempts = 0
    document.next_retry_at = None
    document.claimed_at = None
    document.last_error_code = None
    db.commit()

    _grant_message_evidence(
        db,
        channel=channel,
        evidence_node_id=evidence_node.id,
    )
    message = db.get(NativeMessage, message.id) or message
    message.projection_status = NativeMessageProjectionStatus.READY
    message.last_error_code = None
    db.commit()
    db.refresh(message)
    return message


def _existing_idempotent_message(
    db: Session,
    *,
    channel_id: uuid.UUID,
    idempotency_key: str | None,
    body_sha256: str,
    actor_kind: NativeMessageActorKind,
    author_user_id: uuid.UUID | None,
    agent_run_id: uuid.UUID | None,
    thread_root_id: uuid.UUID | None,
) -> NativeMessage | None:
    if idempotency_key is None:
        return None
    existing = db.scalar(
        select(NativeMessage).where(
            NativeMessage.channel_id == channel_id,
            NativeMessage.idempotency_key == idempotency_key,
        )
    )
    if existing is None:
        return None
    if (
        existing.body_sha256 != body_sha256
        or existing.actor_kind != actor_kind
        or existing.author_user_id != author_user_id
        or existing.agent_run_id != agent_run_id
        or existing.thread_root_id != thread_root_id
    ):
        raise NativeChatConflictError(
            "idempotency_key_reused",
            "Idempotency key was already used for a different message",
        )
    return existing


def sync_exact_mentions(
    db: Session,
    *,
    channel: NativeChannel,
    message: NativeMessage,
    commit: bool = True,
) -> list[NativeMessageMention]:
    emails = {item.casefold() for item in _MENTION_EMAIL_RE.findall(message.body)}
    users = (
        list(
            db.scalars(
                select(User)
                .join(Membership, Membership.user_id == User.id)
                .where(
                    Membership.organization_id == channel.organization_id,
                    User.status == "active",
                    func.lower(User.email).in_(emails),
                )
            )
        )
        if emails
        else []
    )
    desired_user_ids = {
        user.id
        for user in users
        if can_read_channel(db, channel, user_id=user.id)
    }
    existing = {
        row.mentioned_user_id: row
        for row in db.scalars(
            select(NativeMessageMention).where(
                NativeMessageMention.message_id == message.id
            )
        )
    }

    for user_id, row in existing.items():
        if user_id not in desired_user_ids:
            db.delete(row)

    for user in users:
        if user.id not in desired_user_ids or user.id in existing:
            continue
        db.add(
            NativeMessageMention(
                organization_id=channel.organization_id,
                channel_id=channel.id,
                message_id=message.id,
                mentioned_user_id=user.id,
            )
        )

    if commit:
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
    else:
        db.flush()

    rows = list(
        db.scalars(
            select(NativeMessageMention)
            .where(NativeMessageMention.message_id == message.id)
            .order_by(NativeMessageMention.created_at, NativeMessageMention.id)
        )
    )
    actual_user_ids = {row.mentioned_user_id for row in rows}
    if actual_user_ids != desired_user_ids:
        raise NativeChatConflictError(
            "mention_sync_failed",
            "Message mentions could not be saved",
        )
    return rows

def _create_message_row(
    db: Session,
    *,
    organization_id: uuid.UUID,
    channel_id: uuid.UUID,
    actor_kind: NativeMessageActorKind,
    author_user_id: uuid.UUID | None,
    agent_run_id: uuid.UUID | None,
    thread_root_id: uuid.UUID | None,
    body: str,
    idempotency_key: str | None,
) -> NativeMessage:
    normalized_key = (
        " ".join(idempotency_key.strip().split())[:128]
        if idempotency_key
        else None
    )
    if idempotency_key and not normalized_key:
        raise NativeChatError(
            "invalid_idempotency_key",
            "Idempotency key is invalid",
        )
    body_sha256 = hashlib.sha256(body.encode()).hexdigest()
    existing = _existing_idempotent_message(
        db,
        channel_id=channel_id,
        idempotency_key=normalized_key,
        body_sha256=body_sha256,
        actor_kind=actor_kind,
        author_user_id=author_user_id,
        agent_run_id=agent_run_id,
        thread_root_id=thread_root_id,
    )
    if existing is not None:
        return existing

    message_sequence = db.scalar(
        update(NativeChannel)
        .where(
            NativeChannel.id == channel_id,
            NativeChannel.organization_id == organization_id,
        )
        .values(last_message_sequence=NativeChannel.last_message_sequence + 1)
        .returning(NativeChannel.last_message_sequence)
    )
    if message_sequence is None:
        raise NativeChatError("channel_not_found", "Channel not found")

    message = NativeMessage(
        organization_id=organization_id,
        channel_id=channel_id,
        actor_kind=actor_kind,
        author_user_id=author_user_id,
        agent_run_id=agent_run_id,
        thread_root_id=thread_root_id,
        message_sequence=message_sequence,
        body=body,
        body_sha256=body_sha256,
        body_char_count=len(body),
        idempotency_key=normalized_key,
        projection_status=NativeMessageProjectionStatus.PENDING,
    )
    db.add(message)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = _existing_idempotent_message(
            db,
            channel_id=channel_id,
            idempotency_key=normalized_key,
            body_sha256=body_sha256,
            actor_kind=actor_kind,
            author_user_id=author_user_id,
            agent_run_id=agent_run_id,
            thread_root_id=thread_root_id,
        )
        if existing is None:
            raise
        return existing
    db.refresh(message)
    return message


def _validated_message_attachments(
    db: Session,
    *,
    organization_id: uuid.UUID,
    channel: NativeChannel,
    user_id: uuid.UUID,
    source_ids: list[uuid.UUID],
) -> list[EvidenceSource]:
    unique_ids = list(dict.fromkeys(source_ids))
    if len(unique_ids) > 5:
        raise NativeChatError(
            "too_many_attachments",
            "A message can contain at most five attachments",
        )
    if not unique_ids:
        return []
    sources = list(
        db.scalars(
            select(EvidenceSource).where(
                EvidenceSource.organization_id == organization_id,
                EvidenceSource.id.in_(unique_ids),
            )
        )
    )
    by_id = {source.id: source for source in sources}
    if set(by_id) != set(unique_ids):
        raise NativeChatError("attachment_not_found", "Attachment source not found")

    ordered = [by_id[source_id] for source_id in unique_ids]
    for source in ordered:
        if source.status != EvidenceSourceStatus.ACTIVE:
            raise NativeChatError("attachment_not_found", "Attachment source not found")
        if source.source_visibility == EvidenceVisibility.ORGANIZATION:
            continue
        if (
            source.native_channel_id != channel.id
            or not evidence_source_visible_to_user(db, source, user_id)
        ):
            raise NativeChatError("attachment_not_found", "Attachment source not found")
    return ordered


def _sync_message_attachments(
    db: Session,
    *,
    message: NativeMessage,
    sources: list[EvidenceSource],
    actor_user_id: uuid.UUID,
) -> None:
    requested_ids = {source.id for source in sources}
    existing_rows = list(
        db.scalars(
            select(NativeMessageAttachment).where(
                NativeMessageAttachment.message_id == message.id
            )
        )
    )
    existing_ids = {row.evidence_source_id for row in existing_rows}
    if existing_ids and existing_ids != requested_ids:
        raise NativeChatConflictError(
            "idempotency_attachment_mismatch",
            "Idempotent message replay used a different attachment set",
        )
    if existing_ids == requested_ids:
        return
    for source in sources:
        db.add(
            NativeMessageAttachment(
                organization_id=message.organization_id,
                channel_id=message.channel_id,
                message_id=message.id,
                evidence_source_id=source.id,
                created_by_user_id=actor_user_id,
            )
        )
    db.commit()


def post_user_message(
    db: Session,
    *,
    organization_id: uuid.UUID,
    channel_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    body: str,
    idempotency_key: str | None,
    thread_root_id: uuid.UUID | None = None,
    request_id: str | None = None,
    attachment_source_ids: list[uuid.UUID] | None = None,
) -> NativeMessage:
    channel = get_visible_channel(
        db,
        organization_id=organization_id,
        channel_id=channel_id,
        user_id=actor_user_id,
    )
    if channel is None or not can_write_channel(
        db,
        channel,
        user_id=actor_user_id,
    ):
        raise NativeChatError("channel_not_found", "Channel not found")
    if thread_root_id is not None:
        root = db.get(NativeMessage, thread_root_id)
        if (
            root is None
            or root.organization_id != organization_id
            or root.channel_id != channel_id
            or root.thread_root_id is not None
            or root.deleted_at is not None
        ):
            raise NativeChatError("thread_root_not_found", "Thread root not found")
    sources = _validated_message_attachments(
        db,
        organization_id=organization_id,
        channel=channel,
        user_id=actor_user_id,
        source_ids=attachment_source_ids or [],
    )
    normalized_body = normalize_message_body(body, allow_empty=bool(sources))
    if not normalized_body and not sources:
        raise NativeChatError("empty_message", "Message must not be empty")
    message = _create_message_row(
        db,
        organization_id=organization_id,
        channel_id=channel_id,
        actor_kind=NativeMessageActorKind.USER,
        author_user_id=actor_user_id,
        agent_run_id=None,
        thread_root_id=thread_root_id,
        body=normalized_body,
        idempotency_key=idempotency_key,
    )
    _sync_message_attachments(
        db,
        message=message,
        sources=sources,
        actor_user_id=actor_user_id,
    )
    if message.projection_status != NativeMessageProjectionStatus.READY:
        try:
            message = _project_message(
                db,
                message=message,
                channel=channel,
                actor_user_id_for_audit=actor_user_id,
            )
        except Exception as exc:
            db.rollback()
            persisted = db.get(NativeMessage, message.id)
            if persisted is not None:
                persisted.projection_status = NativeMessageProjectionStatus.FAILED
                persisted.last_error_code = getattr(
                    exc,
                    "code",
                    "native_message_projection_failed",
                )[:128]
                db.commit()
            raise
    append_audit_event(
        db,
        organization_id=organization_id,
        event_key=f"native_chat.message.created:{message.id}",
        event_type="native_chat.message.created",
        outcome="succeeded",
        actor_user_id=actor_user_id,
        resource_type="native_channel",
        resource_id=channel.id,
        # This is one semantic creation event, even when a client retries with
        # a different HTTP request ID under the same idempotency key.
        request_id=None,
        metadata={
            "native_message_id": str(message.id),
            "projection_status": message.projection_status.value,
            "body_sha256": message.body_sha256,
            "attachment_count": len(sources),
        },
    )
    sync_exact_mentions(db, channel=channel, message=message)
    return message


def post_agent_message(
    db: Session,
    *,
    organization_id: uuid.UUID,
    channel_id: uuid.UUID,
    agent_run_id: uuid.UUID,
    body: str,
    idempotency_key: str | None,
) -> NativeMessage:
    run = db.scalar(
        select(AgentRun).where(
            AgentRun.id == agent_run_id,
            AgentRun.organization_id == organization_id,
        )
    )
    if run is None:
        raise NativeChatError("agent_run_not_found", "Agent run not found")
    channel = get_visible_channel(
        db,
        organization_id=organization_id,
        channel_id=channel_id,
        user_id=run.requested_by_user_id,
    )
    if channel is None or not can_write_channel(
        db,
        channel,
        user_id=run.requested_by_user_id,
    ):
        raise NativeChatError("channel_not_found", "Channel not found")
    normalized_body = normalize_message_body(body)
    message = _create_message_row(
        db,
        organization_id=organization_id,
        channel_id=channel_id,
        actor_kind=NativeMessageActorKind.AGENT,
        author_user_id=None,
        agent_run_id=agent_run_id,
        thread_root_id=None,
        body=normalized_body,
        idempotency_key=idempotency_key,
    )
    if message.projection_status != NativeMessageProjectionStatus.READY:
        message = _project_message(
            db,
            message=message,
            channel=channel,
            actor_user_id_for_audit=run.requested_by_user_id,
        )
    append_audit_event(
        db,
        organization_id=organization_id,
        event_key=f"native_chat.message.agent_created:{message.id}",
        event_type="native_chat.message.agent_created",
        outcome="succeeded",
        actor_user_id=run.requested_by_user_id,
        resource_type="native_channel",
        resource_id=channel.id,
        metadata={
            "native_message_id": str(message.id),
            "agent_run_id": str(run.id),
            "body_sha256": message.body_sha256,
        },
    )
    sync_exact_mentions(db, channel=channel, message=message)
    return message


def list_channel_messages(
    db: Session,
    *,
    organization_id: uuid.UUID,
    channel_id: uuid.UUID,
    user_id: uuid.UUID,
    limit: int,
    before: datetime | None,
) -> tuple[NativeChannel, list[NativeMessage]]:
    channel = get_visible_channel(
        db,
        organization_id=organization_id,
        channel_id=channel_id,
        user_id=user_id,
    )
    if channel is None:
        raise NativeChatError("channel_not_found", "Channel not found")
    query = select(NativeMessage).where(
        NativeMessage.organization_id == organization_id,
        NativeMessage.channel_id == channel_id,
        NativeMessage.thread_root_id.is_(None),
    )
    if before is not None:
        query = query.where(NativeMessage.created_at < before)
    rows = list(
        db.scalars(
            query.order_by(
                NativeMessage.message_sequence.desc(),
            ).limit(limit)
        )
    )
    rows.reverse()
    return channel, rows
