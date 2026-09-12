import re
import uuid
from collections import defaultdict

from sqlalchemy import String, and_, cast, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Membership, User
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
_MENTION_EMAIL_RE = re.compile(
    r"(?<![A-Za-z0-9._%+\-])@([A-Za-z0-9.!#$%&'*+/=?^_`{|}~\-]+"
    r"@[A-Za-z0-9.-]+\.[A-Za-z]{2,63})",
    re.IGNORECASE,
)


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
            .order_by(NativeMessage.created_at, NativeMessage.id)
            .limit(limit)
        )
    )
    return root, replies


def sync_exact_mentions(
    db: Session,
    *,
    channel: NativeChannel,
    message: NativeMessage,
) -> list[NativeMessageMention]:
    emails = {item.casefold() for item in _MENTION_EMAIL_RE.findall(message.body)}
    if not emails:
        return []
    users = list(
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
    existing = {
        row.mentioned_user_id: row
        for row in db.scalars(
            select(NativeMessageMention).where(
                NativeMessageMention.message_id == message.id
            )
        )
    }
    for user in users:
        if user.id in existing:
            continue
        if not can_read_channel(db, channel, user_id=user.id):
            continue
        row = NativeMessageMention(
            organization_id=channel.organization_id,
            channel_id=channel.id,
            message_id=message.id,
            mentioned_user_id=user.id,
        )
        db.add(row)
        existing[user.id] = row
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
    return list(
        db.scalars(
            select(NativeMessageMention)
            .where(NativeMessageMention.message_id == message.id)
            .order_by(NativeMessageMention.created_at, NativeMessageMention.id)
        )
    )


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
        conditions.append(
            or_(
                NativeMessage.created_at > state.last_read_at,
                and_(
                    NativeMessage.created_at == state.last_read_at,
                    cast(NativeMessage.id, String)
                    > str(state.last_read_message_id),
                ),
            )
        )
    count = int(
        db.scalar(select(func.count()).select_from(NativeMessage).where(*conditions))
        or 0
    )
    return count, state


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
    cursor = (message.created_at, str(message.id))
    if state is None:
        state = NativeChannelReadState(
            organization_id=organization_id,
            channel_id=channel_id,
            user_id=user_id,
            last_read_message_id=message.id,
            last_read_at=message.created_at,
        )
        db.add(state)
    elif cursor > (state.last_read_at, str(state.last_read_message_id)):
        state.last_read_message_id = message.id
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
        if cursor > (state.last_read_at, str(state.last_read_message_id)):
            state.last_read_message_id = message.id
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
