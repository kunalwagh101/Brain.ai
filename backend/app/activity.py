import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.activity_models import ActivityKind, ActivityNotification, ActivityResourceType
from app.direct_message_models import DirectConversation, DirectMessage
from app.models import Membership, User
from app.native_chat_models import NativeChannel, NativeMessage
from app.native_conversation_models import NativeMessageMention, NativeMessageReaction
from app.permissions import Permission, role_has_permission


@dataclass(frozen=True, slots=True)
class ActivityItem:
    id: uuid.UUID
    kind: ActivityKind
    actor_display_name: str | None
    label: str
    context_label: str | None
    href: str
    read: bool
    created_at: datetime


def emit_activity(
    db: Session,
    *,
    organization_id: uuid.UUID,
    recipient_user_id: uuid.UUID,
    actor_user_id: uuid.UUID | None,
    kind: ActivityKind,
    resource_type: ActivityResourceType,
    resource_id: uuid.UUID,
    context_id: uuid.UUID | None,
    dedupe_key: str,
) -> ActivityNotification | None:
    if actor_user_id == recipient_user_id:
        return None
    normalized_key = " ".join(dedupe_key.strip().split())[:192]
    if not normalized_key:
        return None
    existing = db.scalar(
        select(ActivityNotification).where(
            ActivityNotification.organization_id == organization_id,
            ActivityNotification.recipient_user_id == recipient_user_id,
            ActivityNotification.dedupe_key == normalized_key,
        )
    )
    if existing is not None:
        return existing
    row = ActivityNotification(
        organization_id=organization_id,
        recipient_user_id=recipient_user_id,
        actor_user_id=actor_user_id,
        kind=kind,
        resource_type=resource_type,
        resource_id=resource_id,
        context_id=context_id,
        dedupe_key=normalized_key,
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return db.scalar(
            select(ActivityNotification).where(
                ActivityNotification.organization_id == organization_id,
                ActivityNotification.recipient_user_id == recipient_user_id,
                ActivityNotification.dedupe_key == normalized_key,
            )
        )
    db.refresh(row)
    return row


def notify_native_message_created(db: Session, *, message: NativeMessage) -> None:
    mention_rows = list(
        db.scalars(
            select(NativeMessageMention).where(
                NativeMessageMention.message_id == message.id
            )
        )
    )
    mentioned_user_ids = {row.mentioned_user_id for row in mention_rows}
    for mentioned_user_id in mentioned_user_ids:
        emit_activity(
            db,
            organization_id=message.organization_id,
            recipient_user_id=mentioned_user_id,
            actor_user_id=message.author_user_id,
            kind=ActivityKind.MENTION,
            resource_type=ActivityResourceType.NATIVE_MESSAGE,
            resource_id=message.id,
            context_id=message.channel_id,
            dedupe_key=f"mention:{message.id}:{mentioned_user_id}",
        )

    if message.thread_root_id is None:
        return
    root = db.get(NativeMessage, message.thread_root_id)
    if (
        root is None
        or root.author_user_id is None
        or root.author_user_id in mentioned_user_ids
    ):
        return
    emit_activity(
        db,
        organization_id=message.organization_id,
        recipient_user_id=root.author_user_id,
        actor_user_id=message.author_user_id,
        kind=ActivityKind.THREAD_REPLY,
        resource_type=ActivityResourceType.NATIVE_MESSAGE,
        resource_id=message.id,
        context_id=message.channel_id,
        dedupe_key=f"thread-reply:{message.id}:{root.author_user_id}",
    )


def notify_reaction_added(
    db: Session,
    *,
    message: NativeMessage,
    actor_user_id: uuid.UUID,
    reaction: str,
) -> None:
    if message.author_user_id is None:
        return
    emit_activity(
        db,
        organization_id=message.organization_id,
        recipient_user_id=message.author_user_id,
        actor_user_id=actor_user_id,
        kind=ActivityKind.REACTION,
        resource_type=ActivityResourceType.NATIVE_MESSAGE,
        resource_id=message.id,
        context_id=message.channel_id,
        dedupe_key=f"reaction:{message.id}:{actor_user_id}:{reaction}",
    )


def notify_direct_message_sent(db: Session, *, message: DirectMessage) -> None:
    conversation = db.get(DirectConversation, message.conversation_id)
    if conversation is None:
        return
    if conversation.participant_a_user_id == message.author_user_id:
        recipient_user_id = conversation.participant_b_user_id
    elif conversation.participant_b_user_id == message.author_user_id:
        recipient_user_id = conversation.participant_a_user_id
    else:
        return
    emit_activity(
        db,
        organization_id=message.organization_id,
        recipient_user_id=recipient_user_id,
        actor_user_id=message.author_user_id,
        kind=ActivityKind.DIRECT_MESSAGE,
        resource_type=ActivityResourceType.DIRECT_MESSAGE,
        resource_id=message.id,
        context_id=conversation.id,
        dedupe_key=f"direct-message:{message.id}:{recipient_user_id}",
    )


def _materialize_recent_activity(
    db: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    mention_rows = db.execute(
        select(NativeMessageMention, NativeMessage)
        .join(NativeMessage, NativeMessage.id == NativeMessageMention.message_id)
        .where(
            NativeMessageMention.organization_id == organization_id,
            NativeMessageMention.mentioned_user_id == user_id,
        )
        .order_by(NativeMessageMention.created_at.desc())
        .limit(50)
    ).all()
    for _, message in mention_rows:
        emit_activity(
            db,
            organization_id=organization_id,
            recipient_user_id=user_id,
            actor_user_id=message.author_user_id,
            kind=ActivityKind.MENTION,
            resource_type=ActivityResourceType.NATIVE_MESSAGE,
            resource_id=message.id,
            context_id=message.channel_id,
            dedupe_key=f"mention:{message.id}:{user_id}",
        )

    root_ids = select(NativeMessage.id).where(
        NativeMessage.organization_id == organization_id,
        NativeMessage.author_user_id == user_id,
        NativeMessage.thread_root_id.is_(None),
    )
    replies = list(
        db.scalars(
            select(NativeMessage)
            .where(
                NativeMessage.organization_id == organization_id,
                NativeMessage.thread_root_id.in_(root_ids),
                NativeMessage.deleted_at.is_(None),
                or_(
                    NativeMessage.author_user_id.is_(None),
                    NativeMessage.author_user_id != user_id,
                ),
            )
            .order_by(NativeMessage.created_at.desc())
            .limit(50)
        )
    )
    mentioned_message_ids = {message.id for _, message in mention_rows}
    for message in replies:
        if message.id in mentioned_message_ids:
            continue
        emit_activity(
            db,
            organization_id=organization_id,
            recipient_user_id=user_id,
            actor_user_id=message.author_user_id,
            kind=ActivityKind.THREAD_REPLY,
            resource_type=ActivityResourceType.NATIVE_MESSAGE,
            resource_id=message.id,
            context_id=message.channel_id,
            dedupe_key=f"thread-reply:{message.id}:{user_id}",
        )

    reaction_rows = db.execute(
        select(NativeMessageReaction, NativeMessage)
        .join(NativeMessage, NativeMessage.id == NativeMessageReaction.message_id)
        .where(
            NativeMessageReaction.organization_id == organization_id,
            NativeMessage.author_user_id == user_id,
            NativeMessageReaction.user_id != user_id,
        )
        .order_by(NativeMessageReaction.created_at.desc())
        .limit(50)
    ).all()
    for reaction, message in reaction_rows:
        emit_activity(
            db,
            organization_id=organization_id,
            recipient_user_id=user_id,
            actor_user_id=reaction.user_id,
            kind=ActivityKind.REACTION,
            resource_type=ActivityResourceType.NATIVE_MESSAGE,
            resource_id=message.id,
            context_id=message.channel_id,
            dedupe_key=(
                f"reaction:{message.id}:{reaction.user_id}:{reaction.reaction}"
            ),
        )

    conversation_ids = select(DirectConversation.id).where(
        DirectConversation.organization_id == organization_id,
        or_(
            DirectConversation.participant_a_user_id == user_id,
            DirectConversation.participant_b_user_id == user_id,
        ),
    )
    direct_messages = list(
        db.scalars(
            select(DirectMessage)
            .where(
                DirectMessage.organization_id == organization_id,
                DirectMessage.conversation_id.in_(conversation_ids),
                DirectMessage.author_user_id != user_id,
            )
            .order_by(DirectMessage.created_at.desc())
            .limit(50)
        )
    )
    for message in direct_messages:
        emit_activity(
            db,
            organization_id=organization_id,
            recipient_user_id=user_id,
            actor_user_id=message.author_user_id,
            kind=ActivityKind.DIRECT_MESSAGE,
            resource_type=ActivityResourceType.DIRECT_MESSAGE,
            resource_id=message.id,
            context_id=message.conversation_id,
            dedupe_key=f"direct-message:{message.id}:{user_id}",
        )


def _actor_name(db: Session, actor_user_id: uuid.UUID | None) -> str | None:
    if actor_user_id is None:
        return None
    actor = db.get(User, actor_user_id)
    if actor is None:
        return "Former Brain member"
    return actor.display_name or actor.email


def _channel_visible(
    db: Session,
    *,
    channel: NativeChannel,
    user_id: uuid.UUID,
) -> bool:
    from app.native_chat import can_read_channel

    return can_read_channel(db, channel, user_id=user_id)


def _native_item(
    db: Session,
    row: ActivityNotification,
    *,
    user_id: uuid.UUID,
) -> ActivityItem | None:
    message = db.get(NativeMessage, row.resource_id)
    if (
        message is None
        or message.organization_id != row.organization_id
        or message.deleted_at is not None
    ):
        return None
    channel = db.get(NativeChannel, message.channel_id)
    if channel is None or not _channel_visible(db, channel=channel, user_id=user_id):
        return None
    actor = _actor_name(db, row.actor_user_id)
    if row.kind == ActivityKind.MENTION:
        still_mentioned = db.scalar(
            select(NativeMessageMention.id).where(
                NativeMessageMention.message_id == message.id,
                NativeMessageMention.mentioned_user_id == user_id,
            )
        )
        if still_mentioned is None:
            return None
        label = f"{actor or 'An agent'} mentioned you"
    elif row.kind == ActivityKind.THREAD_REPLY:
        label = f"{actor or 'An agent'} replied in a thread"
    elif row.kind == ActivityKind.REACTION:
        label = f"{actor or 'Someone'} reacted to your message"
    else:
        return None
    return ActivityItem(
        id=row.id,
        kind=row.kind,
        actor_display_name=actor,
        label=label,
        context_label=f"#{channel.name}",
        href=f"?channelId={channel.id}#native-chat",
        read=row.read_at is not None,
        created_at=row.created_at,
    )


def _dm_item(
    db: Session,
    row: ActivityNotification,
    *,
    user_id: uuid.UUID,
) -> ActivityItem | None:
    message = db.get(DirectMessage, row.resource_id)
    if message is None or message.organization_id != row.organization_id:
        return None
    conversation = db.get(DirectConversation, message.conversation_id)
    if conversation is None or conversation.organization_id != row.organization_id:
        return None

    if conversation.participant_a_user_id == user_id:
        revoked_at = conversation.participant_a_revoked_at
        visible_from = conversation.participant_a_visible_from_sequence
        other_id = conversation.participant_b_user_id
    elif conversation.participant_b_user_id == user_id:
        revoked_at = conversation.participant_b_revoked_at
        visible_from = conversation.participant_b_visible_from_sequence
        other_id = conversation.participant_a_user_id
    else:
        return None
    if revoked_at is not None or message.sequence < visible_from:
        return None

    membership = db.scalar(
        select(Membership).where(
            Membership.organization_id == row.organization_id,
            Membership.user_id == user_id,
        )
    )
    if membership is None or not role_has_permission(
        membership.role,
        Permission.NATIVE_CHAT_WRITE,
    ):
        return None

    other = db.get(User, other_id)
    actor = _actor_name(db, row.actor_user_id)
    other_name = (other.display_name or other.email) if other is not None else "Former Brain member"
    return ActivityItem(
        id=row.id,
        kind=row.kind,
        actor_display_name=actor,
        label=f"{actor or other_name} sent you a direct message",
        context_label=other_name,
        href=f"?dmId={conversation.id}#direct-messages",
        read=row.read_at is not None,
        created_at=row.created_at,
    )


def _visible_item(
    db: Session,
    row: ActivityNotification,
    *,
    user_id: uuid.UUID,
) -> ActivityItem | None:
    if row.resource_type == ActivityResourceType.NATIVE_MESSAGE:
        return _native_item(db, row, user_id=user_id)
    if row.resource_type == ActivityResourceType.DIRECT_MESSAGE:
        return _dm_item(db, row, user_id=user_id)
    return None


def list_activity(
    db: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    limit: int,
    unread_only: bool = False,
    materialize: bool = True,
) -> list[ActivityItem]:
    if materialize:
        _materialize_recent_activity(
            db,
            organization_id=organization_id,
            user_id=user_id,
        )
    visible: list[ActivityItem] = []
    offset = 0
    chunk_size = min(max(limit * 2, 50), 200)
    while len(visible) < limit:
        query = (
            select(ActivityNotification)
            .where(
                ActivityNotification.organization_id == organization_id,
                ActivityNotification.recipient_user_id == user_id,
            )
            .order_by(ActivityNotification.created_at.desc(), ActivityNotification.id.desc())
            .offset(offset)
            .limit(chunk_size)
        )
        if unread_only:
            query = query.where(ActivityNotification.read_at.is_(None))
        rows = list(db.scalars(query))
        if not rows:
            break
        offset += len(rows)
        for row in rows:
            item = _visible_item(db, row, user_id=user_id)
            if item is not None:
                visible.append(item)
                if len(visible) >= limit:
                    break
        if len(rows) < chunk_size:
            break
    return visible


def unread_activity_count(
    db: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    materialize: bool = True,
) -> int:
    if materialize:
        _materialize_recent_activity(
            db,
            organization_id=organization_id,
            user_id=user_id,
        )
    count = 0
    offset = 0
    chunk_size = 200
    while True:
        rows = list(
            db.scalars(
                select(ActivityNotification)
                .where(
                    ActivityNotification.organization_id == organization_id,
                    ActivityNotification.recipient_user_id == user_id,
                    ActivityNotification.read_at.is_(None),
                )
                .order_by(ActivityNotification.created_at.desc(), ActivityNotification.id.desc())
                .offset(offset)
                .limit(chunk_size)
            )
        )
        if not rows:
            break
        offset += len(rows)
        count += sum(
            1 for row in rows if _visible_item(db, row, user_id=user_id) is not None
        )
        if len(rows) < chunk_size:
            break
    return count


def mark_activity_read(
    db: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    notification_id: uuid.UUID,
) -> None:
    row = db.scalar(
        select(ActivityNotification).where(
            ActivityNotification.id == notification_id,
            ActivityNotification.organization_id == organization_id,
            ActivityNotification.recipient_user_id == user_id,
        )
    )
    if row is None or _visible_item(db, row, user_id=user_id) is None:
        return
    if row.read_at is None:
        row.read_at = datetime.now(UTC)
        db.commit()


def mark_all_activity_read(
    db: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
) -> int:
    _materialize_recent_activity(db, organization_id=organization_id, user_id=user_id)
    visible = list_activity(
        db,
        organization_id=organization_id,
        user_id=user_id,
        limit=500,
        unread_only=True,
        materialize=False,
    )
    ids = [item.id for item in visible]
    if not ids:
        return 0
    result = db.execute(
        update(ActivityNotification)
        .where(
            ActivityNotification.organization_id == organization_id,
            ActivityNotification.recipient_user_id == user_id,
            ActivityNotification.id.in_(ids),
            ActivityNotification.read_at.is_(None),
        )
        .values(read_at=datetime.now(UTC))
    )
    db.commit()
    return int(result.rowcount or 0)
