import hashlib
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.direct_message_models import (
    DirectConversation,
    DirectMessage,
    DirectMessageReaction,
    DirectMessageRevision,
)
from app.models import Membership, User
from app.permissions import Permission, role_has_permission

MAX_DIRECT_MESSAGE_CHARS = 20_000
ALLOWED_DIRECT_MESSAGE_REACTIONS = ("👍", "❤️", "🎉", "👀", "✅")


class DirectMessageError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code[:128]


class DirectMessageConflictError(DirectMessageError):
    pass


@dataclass(frozen=True, slots=True)
class DirectConversationView:
    conversation: DirectConversation
    other_user: User
    can_send: bool
    unread_count: int = 0
    latest_message_id: uuid.UUID | None = None
    first_unread_message_id: uuid.UUID | None = None


def _ordered_pair(first: uuid.UUID, second: uuid.UUID) -> tuple[uuid.UUID, uuid.UUID]:
    lower, upper = sorted((first, second), key=lambda value: value.int)
    return lower, upper


def _normalize_body(body: str) -> str:
    value = body.strip()
    if not value:
        raise DirectMessageError("message_required", "Direct message body is required")
    if len(value) > MAX_DIRECT_MESSAGE_CHARS:
        raise DirectMessageError("message_too_long", "Direct message exceeds 20000 characters")
    return value


def _normalize_idempotency_key(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    if len(normalized) > 128:
        raise DirectMessageError("idempotency_key_invalid", "Idempotency key is too long")
    return normalized


def _message_capable_member(
    db: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
) -> bool:
    row = db.execute(
        select(Membership.role, User.status)
        .join(User, User.id == Membership.user_id)
        .where(
            Membership.organization_id == organization_id,
            Membership.user_id == user_id,
        )
    ).first()
    if row is None or str(row[1]).lower() != "active":
        return False
    return role_has_permission(row[0], Permission.NATIVE_CHAT_WRITE)


def _participant_visible_from_sequence(
    conversation: DirectConversation,
    user_id: uuid.UUID,
) -> int:
    if conversation.participant_a_user_id == user_id:
        return conversation.participant_a_visible_from_sequence
    if conversation.participant_b_user_id == user_id:
        return conversation.participant_b_visible_from_sequence
    raise DirectMessageError("conversation_not_found", "Direct conversation not found")


def _participant_last_read_sequence(
    conversation: DirectConversation,
    user_id: uuid.UUID,
) -> int:
    if conversation.participant_a_user_id == user_id:
        return conversation.participant_a_last_read_sequence
    if conversation.participant_b_user_id == user_id:
        return conversation.participant_b_last_read_sequence
    raise DirectMessageError("conversation_not_found", "Direct conversation not found")


def _set_participant_last_read_sequence(
    conversation: DirectConversation,
    user_id: uuid.UUID,
    sequence: int,
) -> None:
    if conversation.participant_a_user_id == user_id:
        conversation.participant_a_last_read_sequence = sequence
        return
    if conversation.participant_b_user_id == user_id:
        conversation.participant_b_last_read_sequence = sequence
        return
    raise DirectMessageError("conversation_not_found", "Direct conversation not found")


def _other_participant_state(
    conversation: DirectConversation,
    user_id: uuid.UUID,
) -> tuple[uuid.UUID, datetime | None]:
    if conversation.participant_a_user_id == user_id:
        return conversation.participant_b_user_id, conversation.participant_b_revoked_at
    if conversation.participant_b_user_id == user_id:
        return conversation.participant_a_user_id, conversation.participant_a_revoked_at
    raise DirectMessageError("conversation_not_found", "Direct conversation not found")


def _pair_conversation(
    db: Session,
    *,
    organization_id: uuid.UUID,
    participant_a_user_id: uuid.UUID,
    participant_b_user_id: uuid.UUID,
    for_update: bool = False,
) -> DirectConversation | None:
    query = select(DirectConversation).where(
        DirectConversation.organization_id == organization_id,
        DirectConversation.participant_a_user_id == participant_a_user_id,
        DirectConversation.participant_b_user_id == participant_b_user_id,
    )
    if for_update:
        query = query.with_for_update()
    return db.scalar(query)


def _participant_conversation(
    db: Session,
    *,
    organization_id: uuid.UUID,
    conversation_id: uuid.UUID,
    user_id: uuid.UUID,
    for_update: bool = False,
) -> DirectConversation:
    query = select(DirectConversation).where(
        DirectConversation.id == conversation_id,
        DirectConversation.organization_id == organization_id,
        or_(
            and_(
                DirectConversation.participant_a_user_id == user_id,
                DirectConversation.participant_a_revoked_at.is_(None),
            ),
            and_(
                DirectConversation.participant_b_user_id == user_id,
                DirectConversation.participant_b_revoked_at.is_(None),
            ),
        ),
    )
    if for_update:
        query = query.with_for_update()
    conversation = db.scalar(query)
    if conversation is None:
        raise DirectMessageError("conversation_not_found", "Direct conversation not found")
    return conversation


def _reactivate_current_pair(
    db: Session,
    *,
    conversation: DirectConversation,
    actor_user_id: uuid.UUID,
    target_user_id: uuid.UUID,
) -> DirectConversation:
    now = datetime.now(UTC)
    changed = False
    for user_id in (actor_user_id, target_user_id):
        if (
            conversation.participant_a_user_id == user_id
            and conversation.participant_a_revoked_at is not None
        ):
            conversation.participant_a_revoked_at = None
            conversation.participant_a_visible_from_sequence = conversation.next_message_sequence
            conversation.participant_a_last_read_sequence = conversation.next_message_sequence - 1
            changed = True
        elif (
            conversation.participant_b_user_id == user_id
            and conversation.participant_b_revoked_at is not None
        ):
            conversation.participant_b_revoked_at = None
            conversation.participant_b_visible_from_sequence = conversation.next_message_sequence
            conversation.participant_b_last_read_sequence = conversation.next_message_sequence - 1
            changed = True
    if changed:
        conversation.updated_at = now
        db.commit()
        db.refresh(conversation)
    return conversation


def _idempotent_message_for_epoch(
    db: Session,
    *,
    conversation_id: uuid.UUID,
    idempotency_key: str,
    visible_from_sequence: int,
) -> DirectMessage | None:
    existing = db.scalar(
        select(DirectMessage).where(
            DirectMessage.conversation_id == conversation_id,
            DirectMessage.idempotency_key == idempotency_key,
        )
    )
    if existing is None:
        return None
    if existing.sequence < visible_from_sequence:
        raise DirectMessageConflictError(
            "idempotency_key_reused",
            "Idempotency key belongs to an earlier private-message visibility epoch",
        )
    return existing


def create_or_get_direct_conversation(
    db: Session,
    *,
    organization_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    target_email: str,
) -> DirectConversation:
    normalized_email = target_email.strip().lower()
    if not normalized_email or len(normalized_email) > 320:
        raise DirectMessageError("target_invalid", "Target member email is invalid")
    if not _message_capable_member(
        db,
        organization_id=organization_id,
        user_id=actor_user_id,
    ):
        raise DirectMessageError(
            "actor_not_available",
            "Current member is not available for direct messages",
        )

    target_row = db.execute(
        select(Membership, User)
        .join(User, User.id == Membership.user_id)
        .where(
            Membership.organization_id == organization_id,
            User.email == normalized_email,
            User.status == "active",
        )
    ).first()
    if target_row is None:
        raise DirectMessageError("target_not_found", "Organization member not found")
    target_membership, target_user = target_row
    if target_user.id == actor_user_id:
        raise DirectMessageError(
            "self_dm_not_allowed",
            "Cannot create a direct conversation with yourself",
        )
    if not role_has_permission(target_membership.role, Permission.NATIVE_CHAT_WRITE):
        raise DirectMessageError(
            "target_not_available",
            "Organization member is not available for direct messages",
        )

    participant_a, participant_b = _ordered_pair(actor_user_id, target_user.id)
    existing = _pair_conversation(
        db,
        organization_id=organization_id,
        participant_a_user_id=participant_a,
        participant_b_user_id=participant_b,
        for_update=True,
    )
    if existing is not None:
        return _reactivate_current_pair(
            db,
            conversation=existing,
            actor_user_id=actor_user_id,
            target_user_id=target_user.id,
        )

    conversation = DirectConversation(
        organization_id=organization_id,
        participant_a_user_id=participant_a,
        participant_b_user_id=participant_b,
        created_by_user_id=actor_user_id,
    )
    db.add(conversation)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = _pair_conversation(
            db,
            organization_id=organization_id,
            participant_a_user_id=participant_a,
            participant_b_user_id=participant_b,
            for_update=True,
        )
        if existing is None:
            raise
        return _reactivate_current_pair(
            db,
            conversation=existing,
            actor_user_id=actor_user_id,
            target_user_id=target_user.id,
        )
    db.refresh(conversation)
    return conversation


def _direct_unread_summaries(
    db: Session,
    *,
    organization_id: uuid.UUID,
    conversations: list[DirectConversation],
    user_id: uuid.UUID,
) -> dict[uuid.UUID, tuple[int, uuid.UUID | None, uuid.UUID | None]]:
    conversation_ids = [conversation.id for conversation in conversations]
    if not conversation_ids:
        return {}

    visible_from = case(
        (
            DirectConversation.participant_a_user_id == user_id,
            DirectConversation.participant_a_visible_from_sequence,
        ),
        else_=DirectConversation.participant_b_visible_from_sequence,
    )
    last_read = case(
        (
            DirectConversation.participant_a_user_id == user_id,
            DirectConversation.participant_a_last_read_sequence,
        ),
        else_=DirectConversation.participant_b_last_read_sequence,
    )
    unread_ranked = (
        select(
            DirectMessage.conversation_id.label("conversation_id"),
            DirectMessage.id.label("message_id"),
            func.count()
            .over(partition_by=DirectMessage.conversation_id)
            .label("unread_count"),
            func.row_number()
            .over(
                partition_by=DirectMessage.conversation_id,
                order_by=DirectMessage.sequence,
            )
            .label("unread_rank"),
        )
        .join(
            DirectConversation,
            and_(
                DirectConversation.organization_id == DirectMessage.organization_id,
                DirectConversation.id == DirectMessage.conversation_id,
            ),
        )
        .where(
            DirectMessage.organization_id == organization_id,
            DirectMessage.conversation_id.in_(conversation_ids),
            DirectMessage.sequence >= visible_from,
            DirectMessage.sequence > last_read,
            DirectMessage.author_user_id != user_id,
            DirectMessage.deleted_at.is_(None),
        )
        .subquery()
    )
    unread = {
        conversation_id: (int(count), message_id)
        for conversation_id, count, message_id in db.execute(
            select(
                unread_ranked.c.conversation_id,
                unread_ranked.c.unread_count,
                unread_ranked.c.message_id,
            ).where(unread_ranked.c.unread_rank == 1)
        )
    }

    latest_ranked = (
        select(
            DirectMessage.conversation_id.label("conversation_id"),
            DirectMessage.id.label("message_id"),
            func.row_number()
            .over(
                partition_by=DirectMessage.conversation_id,
                order_by=DirectMessage.sequence.desc(),
            )
            .label("latest_rank"),
        )
        .join(
            DirectConversation,
            and_(
                DirectConversation.organization_id == DirectMessage.organization_id,
                DirectConversation.id == DirectMessage.conversation_id,
            ),
        )
        .where(
            DirectMessage.organization_id == organization_id,
            DirectMessage.conversation_id.in_(conversation_ids),
            DirectMessage.sequence >= visible_from,
            DirectMessage.deleted_at.is_(None),
        )
        .subquery()
    )
    latest = {
        conversation_id: message_id
        for conversation_id, message_id in db.execute(
            select(
                latest_ranked.c.conversation_id,
                latest_ranked.c.message_id,
            ).where(latest_ranked.c.latest_rank == 1)
        )
    }
    return {
        conversation_id: (
            unread.get(conversation_id, (0, None))[0],
            latest.get(conversation_id),
            unread.get(conversation_id, (0, None))[1],
        )
        for conversation_id in conversation_ids
    }


def list_direct_conversations(
    db: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
) -> list[DirectConversationView]:
    conversations = list(
        db.scalars(
            select(DirectConversation)
            .where(
                DirectConversation.organization_id == organization_id,
                or_(
                    and_(
                        DirectConversation.participant_a_user_id == user_id,
                        DirectConversation.participant_a_revoked_at.is_(None),
                    ),
                    and_(
                        DirectConversation.participant_b_user_id == user_id,
                        DirectConversation.participant_b_revoked_at.is_(None),
                    ),
                ),
            )
            .order_by(DirectConversation.updated_at.desc(), DirectConversation.id.desc())
        )
    )
    summaries = _direct_unread_summaries(
        db,
        organization_id=organization_id,
        conversations=conversations,
        user_id=user_id,
    )
    views: list[DirectConversationView] = []
    for conversation in conversations:
        other_id, other_revoked_at = _other_participant_state(conversation, user_id)
        other_user = db.get(User, other_id)
        if other_user is not None:
            can_send = other_revoked_at is None and _message_capable_member(
                db,
                organization_id=organization_id,
                user_id=other_id,
            )
            unread_count, latest_message_id, first_unread_message_id = summaries[
                conversation.id
            ]
            views.append(
                DirectConversationView(
                    conversation=conversation,
                    other_user=other_user,
                    can_send=can_send,
                    unread_count=unread_count,
                    latest_message_id=latest_message_id,
                    first_unread_message_id=first_unread_message_id,
                )
            )
    return views


def list_direct_messages(
    db: Session,
    *,
    organization_id: uuid.UUID,
    conversation_id: uuid.UUID,
    user_id: uuid.UUID,
    limit: int,
    before_sequence: int | None = None,
) -> list[DirectMessage]:
    conversation = _participant_conversation(
        db,
        organization_id=organization_id,
        conversation_id=conversation_id,
        user_id=user_id,
    )
    visible_from_sequence = _participant_visible_from_sequence(conversation, user_id)
    query = select(DirectMessage).where(
        DirectMessage.organization_id == organization_id,
        DirectMessage.conversation_id == conversation_id,
        DirectMessage.sequence >= visible_from_sequence,
    )
    if before_sequence is not None:
        query = query.where(DirectMessage.sequence < before_sequence)
    latest = list(
        db.scalars(
            query.order_by(DirectMessage.sequence.desc()).limit(limit)
        )
    )
    latest.reverse()
    return latest


def get_direct_message(
    db: Session,
    *,
    organization_id: uuid.UUID,
    conversation_id: uuid.UUID,
    message_id: uuid.UUID,
    user_id: uuid.UUID,
) -> DirectMessage:
    conversation = _participant_conversation(
        db,
        organization_id=organization_id,
        conversation_id=conversation_id,
        user_id=user_id,
    )
    visible_from_sequence = _participant_visible_from_sequence(conversation, user_id)
    message = db.scalar(
        select(DirectMessage).where(
            DirectMessage.organization_id == organization_id,
            DirectMessage.conversation_id == conversation_id,
            DirectMessage.id == message_id,
            DirectMessage.sequence >= visible_from_sequence,
        )
    )
    if message is None:
        raise DirectMessageError("message_not_found", "Direct message not found")
    return message


def direct_message_reaction_summaries(
    db: Session,
    *,
    messages: list[DirectMessage],
    user_id: uuid.UUID,
) -> dict[uuid.UUID, list[dict[str, object]]]:
    message_ids = [message.id for message in messages]
    result = {message_id: [] for message_id in message_ids}
    if not message_ids:
        return result

    rows = db.execute(
        select(
            DirectMessageReaction.message_id,
            DirectMessageReaction.reaction,
            func.count(),
        )
        .where(DirectMessageReaction.message_id.in_(message_ids))
        .group_by(
            DirectMessageReaction.message_id,
            DirectMessageReaction.reaction,
        )
    ).all()
    mine = set(
        db.execute(
            select(
                DirectMessageReaction.message_id,
                DirectMessageReaction.reaction,
            ).where(
                DirectMessageReaction.message_id.in_(message_ids),
                DirectMessageReaction.user_id == user_id,
            )
        ).all()
    )
    for message_id, reaction, count in rows:
        result[message_id].append(
            {
                "reaction": reaction,
                "count": int(count),
                "reacted_by_me": (message_id, reaction) in mine,
            }
        )
    for items in result.values():
        items.sort(
            key=lambda item: ALLOWED_DIRECT_MESSAGE_REACTIONS.index(
                str(item["reaction"])
            )
        )
    return result


def _normalize_direct_reaction(reaction: str) -> str:
    value = reaction.strip()
    if value not in ALLOWED_DIRECT_MESSAGE_REACTIONS:
        raise DirectMessageError("reaction_invalid", "Direct-message reaction is invalid")
    return value


def add_direct_message_reaction(
    db: Session,
    *,
    organization_id: uuid.UUID,
    conversation_id: uuid.UUID,
    message_id: uuid.UUID,
    user_id: uuid.UUID,
    reaction: str,
) -> DirectMessageReaction:
    value = _normalize_direct_reaction(reaction)
    message = get_direct_message(
        db,
        organization_id=organization_id,
        conversation_id=conversation_id,
        message_id=message_id,
        user_id=user_id,
    )
    if message.deleted_at is not None:
        raise DirectMessageError("message_not_found", "Direct message not found")

    existing = db.scalar(
        select(DirectMessageReaction).where(
            DirectMessageReaction.message_id == message_id,
            DirectMessageReaction.user_id == user_id,
            DirectMessageReaction.reaction == value,
        )
    )
    if existing is not None:
        return existing

    row = DirectMessageReaction(
        organization_id=organization_id,
        conversation_id=conversation_id,
        message_id=message_id,
        user_id=user_id,
        reaction=value,
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(
            select(DirectMessageReaction).where(
                DirectMessageReaction.message_id == message_id,
                DirectMessageReaction.user_id == user_id,
                DirectMessageReaction.reaction == value,
            )
        )
        if existing is None:
            raise
        return existing
    db.refresh(row)
    return row


def remove_direct_message_reaction(
    db: Session,
    *,
    organization_id: uuid.UUID,
    conversation_id: uuid.UUID,
    message_id: uuid.UUID,
    user_id: uuid.UUID,
    reaction: str,
) -> None:
    value = _normalize_direct_reaction(reaction)
    message = get_direct_message(
        db,
        organization_id=organization_id,
        conversation_id=conversation_id,
        message_id=message_id,
        user_id=user_id,
    )
    if message.deleted_at is not None:
        raise DirectMessageError("message_not_found", "Direct message not found")

    row = db.scalar(
        select(DirectMessageReaction).where(
            DirectMessageReaction.organization_id == organization_id,
            DirectMessageReaction.conversation_id == conversation_id,
            DirectMessageReaction.message_id == message_id,
            DirectMessageReaction.user_id == user_id,
            DirectMessageReaction.reaction == value,
        )
    )
    if row is not None:
        db.delete(row)
        db.commit()


def mark_direct_conversation_read(
    db: Session,
    *,
    organization_id: uuid.UUID,
    conversation_id: uuid.UUID,
    user_id: uuid.UUID,
    through_message_id: uuid.UUID,
) -> DirectConversation:
    conversation = _participant_conversation(
        db,
        organization_id=organization_id,
        conversation_id=conversation_id,
        user_id=user_id,
        for_update=True,
    )
    visible_from_sequence = _participant_visible_from_sequence(conversation, user_id)
    message = db.scalar(
        select(DirectMessage).where(
            DirectMessage.organization_id == organization_id,
            DirectMessage.conversation_id == conversation_id,
            DirectMessage.id == through_message_id,
            DirectMessage.sequence >= visible_from_sequence,
        )
    )
    if message is None:
        raise DirectMessageError("message_not_found", "Direct message not found")

    current = _participant_last_read_sequence(conversation, user_id)
    if message.sequence > current:
        _set_participant_last_read_sequence(conversation, user_id, message.sequence)
        db.commit()
        db.refresh(conversation)
    return conversation


def _visible_direct_message_for_update(
    db: Session,
    *,
    organization_id: uuid.UUID,
    conversation_id: uuid.UUID,
    message_id: uuid.UUID,
    user_id: uuid.UUID,
) -> tuple[DirectConversation, DirectMessage]:
    conversation = _participant_conversation(
        db,
        organization_id=organization_id,
        conversation_id=conversation_id,
        user_id=user_id,
        for_update=True,
    )
    visible_from_sequence = _participant_visible_from_sequence(conversation, user_id)
    message = db.scalar(
        select(DirectMessage)
        .where(
            DirectMessage.organization_id == organization_id,
            DirectMessage.conversation_id == conversation_id,
            DirectMessage.id == message_id,
            DirectMessage.sequence >= visible_from_sequence,
        )
        .with_for_update()
    )
    if message is None or message.author_user_id != user_id or message.deleted_at is not None:
        raise DirectMessageError("message_not_found", "Direct message not found")
    return conversation, message


def _snapshot_direct_message(
    db: Session,
    *,
    message: DirectMessage,
    action: str,
) -> None:
    db.add(
        DirectMessageRevision(
            organization_id=message.organization_id,
            conversation_id=message.conversation_id,
            message_id=message.id,
            revision=message.revision,
            action=action,
            body=message.body,
            body_sha256=message.body_sha256,
            body_char_count=message.body_char_count,
        )
    )


def edit_direct_message(
    db: Session,
    *,
    organization_id: uuid.UUID,
    conversation_id: uuid.UUID,
    message_id: uuid.UUID,
    user_id: uuid.UUID,
    body: str,
    expected_revision: int,
) -> DirectMessage:
    normalized_body = _normalize_body(body)
    conversation, message = _visible_direct_message_for_update(
        db,
        organization_id=organization_id,
        conversation_id=conversation_id,
        message_id=message_id,
        user_id=user_id,
    )
    if expected_revision != message.revision:
        raise DirectMessageConflictError(
            "message_revision_conflict",
            "Direct message revision changed",
        )
    _snapshot_direct_message(db, message=message, action="edit")
    now = datetime.now(UTC)
    message.body = normalized_body
    message.body_sha256 = hashlib.sha256(normalized_body.encode()).hexdigest()
    message.body_char_count = len(normalized_body)
    message.revision += 1
    message.edited_at = now
    conversation.updated_at = now
    db.commit()
    db.refresh(message)
    return message


def retract_direct_message(
    db: Session,
    *,
    organization_id: uuid.UUID,
    conversation_id: uuid.UUID,
    message_id: uuid.UUID,
    user_id: uuid.UUID,
    expected_revision: int,
) -> DirectMessage:
    conversation, message = _visible_direct_message_for_update(
        db,
        organization_id=organization_id,
        conversation_id=conversation_id,
        message_id=message_id,
        user_id=user_id,
    )
    if expected_revision != message.revision:
        raise DirectMessageConflictError(
            "message_revision_conflict",
            "Direct message revision changed",
        )
    _snapshot_direct_message(db, message=message, action="retract")
    now = datetime.now(UTC)
    message.revision += 1
    message.deleted_at = now
    conversation.updated_at = now
    db.commit()
    db.refresh(message)
    return message


def send_direct_message(
    db: Session,
    *,
    organization_id: uuid.UUID,
    conversation_id: uuid.UUID,
    author_user_id: uuid.UUID,
    body: str,
    idempotency_key: str | None,
) -> DirectMessage:
    normalized_body = _normalize_body(body)
    normalized_key = _normalize_idempotency_key(idempotency_key)
    conversation = _participant_conversation(
        db,
        organization_id=organization_id,
        conversation_id=conversation_id,
        user_id=author_user_id,
        for_update=True,
    )
    visible_from_sequence = _participant_visible_from_sequence(
        conversation,
        author_user_id,
    )
    other_user_id, other_revoked_at = _other_participant_state(
        conversation,
        author_user_id,
    )
    if other_revoked_at is not None or not _message_capable_member(
        db,
        organization_id=organization_id,
        user_id=other_user_id,
    ):
        raise DirectMessageConflictError(
            "recipient_unavailable",
            "The other participant is not currently available for direct messages",
        )

    if normalized_key is not None:
        existing = _idempotent_message_for_epoch(
            db,
            conversation_id=conversation_id,
            idempotency_key=normalized_key,
            visible_from_sequence=visible_from_sequence,
        )
        if existing is not None:
            return existing

    sequence = conversation.next_message_sequence
    conversation.next_message_sequence = sequence + 1
    conversation.updated_at = datetime.now(UTC)
    digest = hashlib.sha256(normalized_body.encode()).hexdigest()
    message = DirectMessage(
        organization_id=organization_id,
        conversation_id=conversation_id,
        sequence=sequence,
        author_user_id=author_user_id,
        body=normalized_body,
        body_sha256=digest,
        body_char_count=len(normalized_body),
        idempotency_key=normalized_key,
    )
    db.add(message)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        if normalized_key is None:
            raise
        current = _participant_conversation(
            db,
            organization_id=organization_id,
            conversation_id=conversation_id,
            user_id=author_user_id,
        )
        existing = _idempotent_message_for_epoch(
            db,
            conversation_id=conversation_id,
            idempotency_key=normalized_key,
            visible_from_sequence=_participant_visible_from_sequence(
                current,
                author_user_id,
            ),
        )
        if existing is None:
            raise
        return existing
    db.refresh(message)
    return message


def direct_message_author_name(db: Session, user_id: uuid.UUID) -> str:
    user = db.get(User, user_id)
    if user is None:
        return "Former Brain member"
    return user.display_name or user.email
