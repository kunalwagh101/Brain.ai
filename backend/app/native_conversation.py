import hashlib
import uuid
from collections import defaultdict
from datetime import UTC, datetime

from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.data_governance import _audit_payload
from app.data_governance_models import SecurityAuditEvent
from app.models import CanonicalEvent, RawEvent, RawEventStatus, User
from app.native_chat import (
    NativeChatConflictError,
    NativeChatError,
    _grant_message_evidence,
    _message_payload,
    _source_visibility,
    can_read_channel,
    can_write_channel,
    get_visible_channel,
    normalize_message_body,
    sync_exact_mentions,
)
from app.native_chat_models import (
    NativeChannel,
    NativeMessage,
    NativeMessageActorKind,
    NativeMessageRevision,
    NativeMessageRevisionAction,
)
from app.native_conversation_models import (
    NativeChannelReadState,
    NativeMessageMention,
    NativeMessageReaction,
)
from app.search import project_search_document
from app.search_models import SearchDocument
from app.work_graph import create_manual_edge, project_canonical_event
from app.work_graph_models import WorkGraphEdgeType

ALLOWED_REACTIONS = ("👍", "❤️", "🎉", "👀", "✅")


def visible_message(
    db: Session,
    *,
    organization_id: uuid.UUID,
    channel_id: uuid.UUID,
    message_id: uuid.UUID,
    user_id: uuid.UUID,
) -> tuple[NativeChannel, NativeMessage]:
    channel = get_visible_channel(
        db,
        organization_id=organization_id,
        channel_id=channel_id,
        user_id=user_id,
    )
    message = db.get(NativeMessage, message_id)
    if (
        channel is None
        or message is None
        or message.organization_id != organization_id
        or message.channel_id != channel_id
    ):
        raise NativeChatError("message_not_found", "Message not found")
    return channel, message


def _mutable_author_message(
    db: Session,
    *,
    organization_id: uuid.UUID,
    channel_id: uuid.UUID,
    message_id: uuid.UUID,
    user_id: uuid.UUID,
) -> tuple[NativeChannel, NativeMessage]:
    channel = get_visible_channel(
        db,
        organization_id=organization_id,
        channel_id=channel_id,
        user_id=user_id,
    )
    if channel is None or not can_write_channel(db, channel, user_id=user_id):
        raise NativeChatError("message_not_found", "Message not found")

    statement = select(NativeMessage).where(
        NativeMessage.id == message_id,
        NativeMessage.organization_id == organization_id,
        NativeMessage.channel_id == channel_id,
    )
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        statement = statement.with_for_update()
    message = db.scalar(statement)
    if (
        message is None
        or message.actor_kind != NativeMessageActorKind.USER
        or message.author_user_id != user_id
        or message.deleted_at is not None
    ):
        raise NativeChatError("message_not_found", "Message not found")
    return channel, message


def _require_expected_revision(
    message: NativeMessage,
    expected_revision: int,
) -> None:
    if expected_revision < 1 or message.revision != expected_revision:
        raise NativeChatConflictError(
            "message_revision_conflict",
            "Message changed since it was loaded",
        )


def _snapshot_message_revision(
    db: Session,
    *,
    message: NativeMessage,
    actor_user_id: uuid.UUID,
    action: NativeMessageRevisionAction,
) -> None:
    db.add(
        NativeMessageRevision(
            organization_id=message.organization_id,
            channel_id=message.channel_id,
            message_id=message.id,
            revision=message.revision,
            action=action,
            body=message.body,
            body_sha256=message.body_sha256,
            body_char_count=message.body_char_count,
            raw_event_id=message.raw_event_id,
            canonical_event_id=message.canonical_event_id,
            changed_by_user_id=actor_user_id,
        )
    )


def _message_search_document(
    db: Session,
    *,
    message: NativeMessage,
) -> SearchDocument:
    if message.canonical_event_id is None:
        raise NativeChatConflictError(
            "message_projection_unavailable",
            "Message search projection is unavailable",
        )
    document = db.scalar(
        select(SearchDocument).where(
            SearchDocument.organization_id == message.organization_id,
            SearchDocument.canonical_event_id == message.canonical_event_id,
        )
    )
    if document is None:
        raise NativeChatConflictError(
            "message_projection_unavailable",
            "Message search projection is unavailable",
        )
    return document


def _project_lifecycle_revision(
    db: Session,
    *,
    channel: NativeChannel,
    message: NativeMessage,
    actor_user_id: uuid.UUID,
    event_type: str,
    action: str,
    occurred_at: datetime,
    supersedes_canonical_event_id: uuid.UUID,
) -> None:
    previous_canonical = db.get(CanonicalEvent, supersedes_canonical_event_id)
    if previous_canonical is None:
        raise NativeChatConflictError(
            "message_projection_unavailable",
            "Message canonical evidence is unavailable",
        )
    if channel.work_graph_node_id is None:
        raise NativeChatConflictError(
            "channel_track_missing",
            "Native channel is missing its Work Graph track",
        )

    visibility = _source_visibility(channel)
    raw_payload = _message_payload(message, channel)
    raw = RawEvent(
        organization_id=message.organization_id,
        integration_connection_id=previous_canonical.integration_connection_id,
        provider="brain_native",
        source_event_id=f"native-message:{message.id}:revision:{message.revision}",
        source_event_type=event_type,
        delivery_kind="native",
        source_timestamp=occurred_at,
        content_type="application/json",
        payload_sha256=hashlib.sha256(raw_payload).hexdigest(),
        raw_payload=raw_payload,
        source_visibility=visibility,
        source_acl=[],
        processing_status=RawEventStatus.PROCESSED,
        processing_attempts=0,
        last_error_code=None,
    )
    db.add(raw)
    db.flush()

    canonical = CanonicalEvent(
        organization_id=message.organization_id,
        raw_event_id=raw.id,
        integration_connection_id=previous_canonical.integration_connection_id,
        resolved_user_id=message.author_user_id,
        schema_version=1,
        event_type=event_type,
        action=action,
        actor_type="brain_user",
        actor_external_id=str(actor_user_id),
        actor_display_name=None,
        object_type="native_message",
        object_external_id=str(message.id),
        object_display_name=f"#{channel.name}",
        source_provider="brain_native",
        source_event_id=raw.source_event_id,
        source_event_type=raw.source_event_type,
        occurred_at=occurred_at,
        source_visibility=visibility,
        source_acl=[],
        provenance={
            "raw_event_id": str(raw.id),
            "integration_connection_id": str(previous_canonical.integration_connection_id),
            "payload_sha256": raw.payload_sha256,
            "native_message_id": str(message.id),
            "native_message_revision": message.revision,
            "channel_id": str(channel.id),
            "thread_root_id": (
                str(message.thread_root_id) if message.thread_root_id else None
            ),
            "track_node_id": str(channel.work_graph_node_id),
            "supersedes_canonical_event_id": str(supersedes_canonical_event_id),
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
            "native_message_revision": message.revision,
            "edited_at": message.edited_at.isoformat() if message.edited_at else None,
            "deleted_at": message.deleted_at.isoformat() if message.deleted_at else None,
        },
    )
    db.add(canonical)
    db.flush()

    message.raw_event_id = raw.id
    message.canonical_event_id = canonical.id

    evidence_node = project_canonical_event(db, canonical, commit=False)
    create_manual_edge(
        db,
        organization_id=message.organization_id,
        source_node_id=channel.work_graph_node_id,
        target_node_id=evidence_node.id,
        edge_type=WorkGraphEdgeType.RELATED_TO,
        actor_user_id=actor_user_id,
        reason=f"Brain native message lifecycle revision {message.revision}",
        commit=False,
    )
    project_search_document(db, canonical, commit=False)
    _grant_message_evidence(
        db,
        channel=channel,
        evidence_node_id=evidence_node.id,
        commit=False,
    )


def _stage_lifecycle_audit(
    db: Session,
    *,
    message: NativeMessage,
    actor_user_id: uuid.UUID,
    event_type: str,
    previous_revision: int,
    previous_body_sha256: str,
    request_id: str | None,
) -> None:
    event_key = f"{event_type}:{message.id}:{message.revision}"
    payload, digest = _audit_payload(
        organization_id=message.organization_id,
        event_key=event_key,
        event_type=event_type,
        outcome="succeeded",
        actor_user_id=actor_user_id,
        resource_type="native_message",
        resource_id=message.id,
        request_id=request_id,
        metadata={
            "channel_id": str(message.channel_id),
            "previous_revision": previous_revision,
            "current_revision": message.revision,
            "previous_body_sha256": previous_body_sha256,
            "current_body_sha256": message.body_sha256,
        },
    )
    db.add(
        SecurityAuditEvent(
            organization_id=message.organization_id,
            event_key=str(payload["event_key"]),
            event_type=str(payload["event_type"]),
            outcome=str(payload["outcome"]),
            actor_user_id=actor_user_id,
            resource_type=payload["resource_type"],
            resource_id=payload["resource_id"],
            request_id=payload["request_id"],
            metadata_json=payload["metadata"],
            payload_sha256=digest,
        )
    )


def edit_message(
    db: Session,
    *,
    organization_id: uuid.UUID,
    channel_id: uuid.UUID,
    message_id: uuid.UUID,
    user_id: uuid.UUID,
    body: str,
    expected_revision: int,
    request_id: str | None = None,
) -> NativeMessage:
    channel, message = _mutable_author_message(
        db,
        organization_id=organization_id,
        channel_id=channel_id,
        message_id=message_id,
        user_id=user_id,
    )
    _require_expected_revision(message, expected_revision)
    normalized_body = normalize_message_body(body)
    next_sha256 = hashlib.sha256(normalized_body.encode()).hexdigest()
    if next_sha256 == message.body_sha256:
        return message

    _message_search_document(db, message=message)
    if message.canonical_event_id is None:
        raise NativeChatConflictError(
            "message_projection_unavailable",
            "Message canonical evidence is unavailable",
        )
    previous_canonical_event_id = message.canonical_event_id
    previous_revision = message.revision
    previous_sha256 = message.body_sha256

    try:
        _snapshot_message_revision(
            db,
            message=message,
            actor_user_id=user_id,
            action=NativeMessageRevisionAction.EDIT,
        )

        now = datetime.now(UTC)
        message.body = normalized_body
        message.body_sha256 = next_sha256
        message.body_char_count = len(normalized_body)
        message.revision += 1
        message.edited_at = now

        _project_lifecycle_revision(
            db,
            channel=channel,
            message=message,
            actor_user_id=user_id,
            event_type="native.message.edited",
            action="updated",
            occurred_at=now,
            supersedes_canonical_event_id=previous_canonical_event_id,
        )
        sync_exact_mentions(db, channel=channel, message=message, commit=False)
        _stage_lifecycle_audit(
            db,
            message=message,
            actor_user_id=user_id,
            event_type="native_chat.message.edited",
            previous_revision=previous_revision,
            previous_body_sha256=previous_sha256,
            request_id=request_id,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(message)
    return message


def retract_message(
    db: Session,
    *,
    organization_id: uuid.UUID,
    channel_id: uuid.UUID,
    message_id: uuid.UUID,
    user_id: uuid.UUID,
    expected_revision: int,
    request_id: str | None = None,
) -> NativeMessage:
    channel, message = _mutable_author_message(
        db,
        organization_id=organization_id,
        channel_id=channel_id,
        message_id=message_id,
        user_id=user_id,
    )
    _require_expected_revision(message, expected_revision)
    _message_search_document(db, message=message)
    if message.canonical_event_id is None:
        raise NativeChatConflictError(
            "message_projection_unavailable",
            "Message canonical evidence is unavailable",
        )
    previous_canonical_event_id = message.canonical_event_id
    previous_revision = message.revision
    previous_sha256 = message.body_sha256

    try:
        _snapshot_message_revision(
            db,
            message=message,
            actor_user_id=user_id,
            action=NativeMessageRevisionAction.RETRACT,
        )

        now = datetime.now(UTC)
        message.revision += 1
        message.deleted_at = now

        _project_lifecycle_revision(
            db,
            channel=channel,
            message=message,
            actor_user_id=user_id,
            event_type="native.message.retracted",
            action="deleted",
            occurred_at=now,
            supersedes_canonical_event_id=previous_canonical_event_id,
        )
        db.execute(
            delete(NativeMessageMention).where(
                NativeMessageMention.message_id == message.id
            )
        )
        db.execute(
            delete(NativeMessageReaction).where(
                NativeMessageReaction.message_id == message.id
            )
        )
        _stage_lifecycle_audit(
            db,
            message=message,
            actor_user_id=user_id,
            event_type="native_chat.message.retracted",
            previous_revision=previous_revision,
            previous_body_sha256=previous_sha256,
            request_id=request_id,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(message)
    return message

def list_thread_replies(
    db: Session,
    *,
    organization_id: uuid.UUID,
    channel_id: uuid.UUID,
    root_message_id: uuid.UUID,
    user_id: uuid.UUID,
    limit: int,
) -> tuple[NativeMessage, list[NativeMessage]]:
    _, root = visible_message(
        db,
        organization_id=organization_id,
        channel_id=channel_id,
        message_id=root_message_id,
        user_id=user_id,
    )
    if root.thread_root_id is not None:
        raise NativeChatError("thread_root_not_found", "Thread root not found")
    replies = list(
        db.scalars(
            select(NativeMessage)
            .where(
                NativeMessage.organization_id == organization_id,
                NativeMessage.channel_id == channel_id,
                NativeMessage.thread_root_id == root_message_id,
            )
            .order_by(NativeMessage.message_sequence)
            .limit(limit)
        )
    )
    return root, replies


def add_reaction(
    db: Session,
    *,
    organization_id: uuid.UUID,
    channel_id: uuid.UUID,
    message_id: uuid.UUID,
    user_id: uuid.UUID,
    reaction: str,
) -> NativeMessageReaction:
    if reaction not in ALLOWED_REACTIONS:
        raise NativeChatError("reaction_not_allowed", "Reaction is not allowed")
    channel, message = visible_message(
        db,
        organization_id=organization_id,
        channel_id=channel_id,
        message_id=message_id,
        user_id=user_id,
    )
    if message.deleted_at is not None or not can_write_channel(db, channel, user_id=user_id):
        raise NativeChatError("message_not_found", "Message not found")
    existing = db.scalar(
        select(NativeMessageReaction).where(
            NativeMessageReaction.message_id == message_id,
            NativeMessageReaction.user_id == user_id,
            NativeMessageReaction.reaction == reaction,
        )
    )
    if existing is not None:
        return existing
    row = NativeMessageReaction(
        organization_id=organization_id,
        channel_id=channel_id,
        message_id=message_id,
        user_id=user_id,
        reaction=reaction,
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(
            select(NativeMessageReaction).where(
                NativeMessageReaction.message_id == message_id,
                NativeMessageReaction.user_id == user_id,
                NativeMessageReaction.reaction == reaction,
            )
        )
        if existing is None:
            raise
        return existing
    db.refresh(row)
    return row


def remove_reaction(
    db: Session,
    *,
    organization_id: uuid.UUID,
    channel_id: uuid.UUID,
    message_id: uuid.UUID,
    user_id: uuid.UUID,
    reaction: str,
) -> None:
    if reaction not in ALLOWED_REACTIONS:
        raise NativeChatError("reaction_not_allowed", "Reaction is not allowed")
    channel, message = visible_message(
        db,
        organization_id=organization_id,
        channel_id=channel_id,
        message_id=message_id,
        user_id=user_id,
    )
    if message.deleted_at is not None or not can_write_channel(db, channel, user_id=user_id):
        raise NativeChatError("message_not_found", "Message not found")
    row = db.scalar(
        select(NativeMessageReaction).where(
            NativeMessageReaction.message_id == message_id,
            NativeMessageReaction.user_id == user_id,
            NativeMessageReaction.reaction == reaction,
        )
    )
    if row is not None:
        db.delete(row)
        db.commit()


def unread_count(
    db: Session,
    *,
    organization_id: uuid.UUID,
    channel: NativeChannel,
    user_id: uuid.UUID,
) -> tuple[int, NativeChannelReadState | None]:
    if not can_read_channel(db, channel, user_id=user_id):
        raise NativeChatError("channel_not_found", "Channel not found")
    state = db.scalar(
        select(NativeChannelReadState).where(
            NativeChannelReadState.organization_id == organization_id,
            NativeChannelReadState.channel_id == channel.id,
            NativeChannelReadState.user_id == user_id,
        )
    )
    conditions = [
        NativeMessage.organization_id == organization_id,
        NativeMessage.channel_id == channel.id,
        NativeMessage.deleted_at.is_(None),
        or_(
            NativeMessage.author_user_id.is_(None),
            NativeMessage.author_user_id != user_id,
        ),
    ]
    if state is not None:
        conditions.append(NativeMessage.message_sequence > state.last_read_sequence)
    count = int(
        db.scalar(select(func.count()).select_from(NativeMessage).where(*conditions))
        or 0
    )
    return count, state


def channel_unread_summaries(
    db: Session,
    *,
    organization_id: uuid.UUID,
    channels: list[NativeChannel],
    user_id: uuid.UUID,
) -> dict[
    uuid.UUID,
    tuple[int, NativeChannelReadState | None, uuid.UUID | None],
]:
    """Return personal unread counts and latest cursors in three bounded queries."""
    channel_ids = [channel.id for channel in channels]
    if not channel_ids:
        return {}

    states = {
        state.channel_id: state
        for state in db.scalars(
            select(NativeChannelReadState).where(
                NativeChannelReadState.organization_id == organization_id,
                NativeChannelReadState.channel_id.in_(channel_ids),
                NativeChannelReadState.user_id == user_id,
            )
        )
    }
    unread_by_channel = {
        channel_id: int(count)
        for channel_id, count in db.execute(
            select(NativeMessage.channel_id, func.count())
            .outerjoin(
                NativeChannelReadState,
                and_(
                    NativeChannelReadState.organization_id
                    == NativeMessage.organization_id,
                    NativeChannelReadState.channel_id == NativeMessage.channel_id,
                    NativeChannelReadState.user_id == user_id,
                ),
            )
            .where(
                NativeMessage.organization_id == organization_id,
                NativeMessage.channel_id.in_(channel_ids),
                NativeMessage.deleted_at.is_(None),
                or_(
                    NativeMessage.author_user_id.is_(None),
                    NativeMessage.author_user_id != user_id,
                ),
                or_(
                    NativeChannelReadState.id.is_(None),
                    NativeMessage.message_sequence
                    > NativeChannelReadState.last_read_sequence,
                ),
            )
            .group_by(NativeMessage.channel_id)
        )
    }
    latest_sequences = (
        select(
            NativeMessage.channel_id.label("channel_id"),
            func.max(NativeMessage.message_sequence).label("message_sequence"),
        )
        .where(
            NativeMessage.organization_id == organization_id,
            NativeMessage.channel_id.in_(channel_ids),
            NativeMessage.deleted_at.is_(None),
        )
        .group_by(NativeMessage.channel_id)
        .subquery()
    )
    latest_by_channel = {
        channel_id: message_id
        for channel_id, message_id in db.execute(
            select(NativeMessage.channel_id, NativeMessage.id).join(
                latest_sequences,
                and_(
                    latest_sequences.c.channel_id == NativeMessage.channel_id,
                    latest_sequences.c.message_sequence
                    == NativeMessage.message_sequence,
                ),
            )
        )
    }
    return {
        channel_id: (
            unread_by_channel.get(channel_id, 0),
            states.get(channel_id),
            latest_by_channel.get(channel_id),
        )
        for channel_id in channel_ids
    }


def mark_read(
    db: Session,
    *,
    organization_id: uuid.UUID,
    channel_id: uuid.UUID,
    user_id: uuid.UUID,
    through_message_id: uuid.UUID,
) -> NativeChannelReadState:
    _, message = visible_message(
        db,
        organization_id=organization_id,
        channel_id=channel_id,
        message_id=through_message_id,
        user_id=user_id,
    )
    state = db.scalar(
        select(NativeChannelReadState)
        .where(
            NativeChannelReadState.organization_id == organization_id,
            NativeChannelReadState.channel_id == channel_id,
            NativeChannelReadState.user_id == user_id,
        )
        .with_for_update()
    )
    cursor = message.message_sequence
    if state is None:
        state = NativeChannelReadState(
            organization_id=organization_id,
            channel_id=channel_id,
            user_id=user_id,
            last_read_message_id=message.id,
            last_read_sequence=message.message_sequence,
            last_read_at=message.created_at,
        )
        db.add(state)
    elif cursor > state.last_read_sequence:
        state.last_read_message_id = message.id
        state.last_read_sequence = message.message_sequence
        state.last_read_at = message.created_at
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        state = db.scalar(
            select(NativeChannelReadState).where(
                NativeChannelReadState.organization_id == organization_id,
                NativeChannelReadState.channel_id == channel_id,
                NativeChannelReadState.user_id == user_id,
            )
        )
        if state is None:
            raise NativeChatConflictError(
                "read_state_conflict",
                "Read state could not be updated",
            ) from None
        if cursor > state.last_read_sequence:
            state.last_read_message_id = message.id
            state.last_read_sequence = message.message_sequence
            state.last_read_at = message.created_at
            db.commit()
    db.refresh(state)
    return state


def message_affordances(
    db: Session,
    *,
    messages: list[NativeMessage],
    user_id: uuid.UUID,
) -> dict[uuid.UUID, dict[str, object]]:
    message_ids = [message.id for message in messages]
    result = {
        message_id: {"reply_count": 0, "mentions": [], "reactions": []}
        for message_id in message_ids
    }
    if not message_ids:
        return result

    for root_id, count in db.execute(
        select(NativeMessage.thread_root_id, func.count())
        .where(NativeMessage.thread_root_id.in_(message_ids))
        .group_by(NativeMessage.thread_root_id)
    ):
        if root_id in result:
            result[root_id]["reply_count"] = int(count)

    for message_id, mentioned_user_id, email, display_name in db.execute(
        select(
            NativeMessageMention.message_id,
            User.id,
            User.email,
            User.display_name,
        )
        .join(User, User.id == NativeMessageMention.mentioned_user_id)
        .where(NativeMessageMention.message_id.in_(message_ids))
        .order_by(NativeMessageMention.created_at, NativeMessageMention.id)
    ):
        result[message_id]["mentions"].append(
            {
                "user_id": mentioned_user_id,
                "email": email,
                "display_name": display_name,
            }
        )

    reaction_rows = db.execute(
        select(
            NativeMessageReaction.message_id,
            NativeMessageReaction.reaction,
            func.count(),
        )
        .where(NativeMessageReaction.message_id.in_(message_ids))
        .group_by(
            NativeMessageReaction.message_id,
            NativeMessageReaction.reaction,
        )
    ).all()
    mine = set(
        db.execute(
            select(
                NativeMessageReaction.message_id,
                NativeMessageReaction.reaction,
            ).where(
                NativeMessageReaction.message_id.in_(message_ids),
                NativeMessageReaction.user_id == user_id,
            )
        ).all()
    )
    grouped: dict[uuid.UUID, list[dict[str, object]]] = defaultdict(list)
    for message_id, reaction, count in reaction_rows:
        grouped[message_id].append(
            {
                "reaction": reaction,
                "count": int(count),
                "reacted_by_me": (message_id, reaction) in mine,
            }
        )
    for message_id, items in grouped.items():
        items.sort(key=lambda item: ALLOWED_REACTIONS.index(str(item["reaction"])))
        result[message_id]["reactions"] = items
    return result
