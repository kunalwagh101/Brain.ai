import uuid
from collections import defaultdict

from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import User
from app.native_chat import (
    NativeChatConflictError,
    NativeChatError,
    can_read_channel,
    can_write_channel,
    get_visible_channel,
)
from app.native_chat_models import NativeChannel, NativeMessage
from app.native_conversation_models import (
    NativeChannelReadState,
    NativeMessageMention,
    NativeMessageReaction,
)

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
    channel, _ = visible_message(
        db,
        organization_id=organization_id,
        channel_id=channel_id,
        message_id=message_id,
        user_id=user_id,
    )
    if not can_write_channel(db, channel, user_id=user_id):
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
    channel, _ = visible_message(
        db,
        organization_id=organization_id,
        channel_id=channel_id,
        message_id=message_id,
        user_id=user_id,
    )
    if not can_write_channel(db, channel, user_id=user_id):
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
