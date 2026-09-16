import hashlib
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.direct_message_models import DirectConversation, DirectMessage
from app.models import Membership, User
from app.permissions import Permission, role_has_permission

MAX_DIRECT_MESSAGE_CHARS = 20_000


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


def _participant_visible_from(
    conversation: DirectConversation,
    user_id: uuid.UUID,
) -> datetime:
    if conversation.participant_a_user_id == user_id:
        return conversation.participant_a_visible_from
    if conversation.participant_b_user_id == user_id:
        return conversation.participant_b_visible_from
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


def _participant_conversation(
    db: Session,
    *,
    organization_id: uuid.UUID,
    conversation_id: uuid.UUID,
    user_id: uuid.UUID,
) -> DirectConversation:
    conversation = db.scalar(
        select(DirectConversation).where(
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
    )
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
        if conversation.participant_a_user_id == user_id and conversation.participant_a_revoked_at is not None:
            conversation.participant_a_revoked_at = None
            conversation.participant_a_visible_from = now
            changed = True
        elif conversation.participant_b_user_id == user_id and conversation.participant_b_revoked_at is not None:
            conversation.participant_b_revoked_at = None
            conversation.participant_b_visible_from = now
            changed = True
    if changed:
        conversation.updated_at = now
        db.commit()
        db.refresh(conversation)
    return conversation


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
        raise DirectMessageError("actor_not_available", "Current member is not available for direct messages")

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
        raise DirectMessageError("self_dm_not_allowed", "Cannot create a direct conversation with yourself")
    if not role_has_permission(target_membership.role, Permission.NATIVE_CHAT_WRITE):
        raise DirectMessageError("target_not_available", "Organization member is not available for direct messages")

    participant_a, participant_b = _ordered_pair(actor_user_id, target_user.id)
    existing = db.scalar(
        select(DirectConversation).where(
            DirectConversation.organization_id == organization_id,
            DirectConversation.participant_a_user_id == participant_a,
            DirectConversation.participant_b_user_id == participant_b,
        )
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
        existing = db.scalar(
            select(DirectConversation).where(
                DirectConversation.organization_id == organization_id,
                DirectConversation.participant_a_user_id == participant_a,
                DirectConversation.participant_b_user_id == participant_b,
            )
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
            views.append(
                DirectConversationView(
                    conversation=conversation,
                    other_user=other_user,
                    can_send=can_send,
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
) -> list[DirectMessage]:
    conversation = _participant_conversation(
        db,
        organization_id=organization_id,
        conversation_id=conversation_id,
        user_id=user_id,
    )
    visible_from = _participant_visible_from(conversation, user_id)
    latest = list(
        db.scalars(
            select(DirectMessage)
            .where(
                DirectMessage.organization_id == organization_id,
                DirectMessage.conversation_id == conversation_id,
                DirectMessage.created_at >= visible_from,
            )
            .order_by(DirectMessage.created_at.desc(), DirectMessage.id.desc())
            .limit(limit)
        )
    )
    latest.reverse()
    return latest


def send_direct_message(
    db: Session,
    *,
    organization_id: uuid.UUID,
    conversation_id: uuid.UUID,
    author_user_id: uuid.UUID,
    body: str,
    idempotency_key: str | None,
) -> DirectMessage:
    conversation = _participant_conversation(
        db,
        organization_id=organization_id,
        conversation_id=conversation_id,
        user_id=author_user_id,
    )
    visible_from = _participant_visible_from(conversation, author_user_id)
    other_user_id, other_revoked_at = _other_participant_state(conversation, author_user_id)
    if other_revoked_at is not None or not _message_capable_member(
        db,
        organization_id=organization_id,
        user_id=other_user_id,
    ):
        raise DirectMessageConflictError(
            "recipient_unavailable",
            "The other participant is not currently available for direct messages",
        )

    normalized_body = _normalize_body(body)
    normalized_key = _normalize_idempotency_key(idempotency_key)
    if normalized_key is not None:
        existing = db.scalar(
            select(DirectMessage).where(
                DirectMessage.conversation_id == conversation_id,
                DirectMessage.idempotency_key == normalized_key,
            )
        )
        if existing is not None:
            if existing.created_at >= visible_from:
                return existing
            raise DirectMessageConflictError(
                "idempotency_key_reused",
                "Idempotency key belongs to an earlier private-message visibility epoch",
            )

    digest = hashlib.sha256(normalized_body.encode()).hexdigest()
    message = DirectMessage(
        organization_id=organization_id,
        conversation_id=conversation_id,
        author_user_id=author_user_id,
        body=normalized_body,
        body_sha256=digest,
        body_char_count=len(normalized_body),
        idempotency_key=normalized_key,
    )
    conversation.updated_at = datetime.now(UTC)
    db.add(message)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        if normalized_key is None:
            raise
        existing = db.scalar(
            select(DirectMessage).where(
                DirectMessage.conversation_id == conversation_id,
                DirectMessage.idempotency_key == normalized_key,
            )
        )
        if existing is None:
            raise
        if existing.created_at >= visible_from:
            return existing
        raise DirectMessageConflictError(
            "idempotency_key_reused",
            "Idempotency key belongs to an earlier private-message visibility epoch",
        )
    db.refresh(message)
    return message


def direct_message_author_name(db: Session, user_id: uuid.UUID) -> str:
    user = db.get(User, user_id)
    if user is None:
        return "Former Brain member"
    return user.display_name or user.email
