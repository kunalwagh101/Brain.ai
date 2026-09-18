import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from sqlalchemy import and_, delete, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.collaboration_presence_models import (
    CollaborationPresenceLease,
    CollaborationTypingLease,
)
from app.direct_message_models import DirectConversation
from app.models import Membership, User
from app.native_chat import can_read_channel, can_write_channel, get_visible_channel
from app.permissions import Permission, role_has_permission

PRESENCE_TTL_SECONDS = 75
TYPING_TTL_SECONDS = 8


class CollaborationContextKind(StrEnum):
    CHANNEL = "channel"
    DM = "dm"


class CollaborationPresenceError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code[:128]


@dataclass(frozen=True, slots=True)
class CollaborationUserView:
    user_id: uuid.UUID
    display_name: str


@dataclass(frozen=True, slots=True)
class CollaborationContextView:
    online_users: list[CollaborationUserView]
    typing_users: list[CollaborationUserView]


def _now(value: datetime | None = None) -> datetime:
    return value or datetime.now(UTC)


def _chat_capable_member(
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
    return (
        row is not None
        and str(row[1]).lower() == "active"
        and role_has_permission(row[0], Permission.NATIVE_CHAT_WRITE)
    )


def _purge_expired(
    db: Session,
    *,
    organization_id: uuid.UUID,
    at: datetime,
) -> None:
    db.execute(
        delete(CollaborationPresenceLease).where(
            CollaborationPresenceLease.organization_id == organization_id,
            CollaborationPresenceLease.expires_at <= at,
        )
    )
    db.execute(
        delete(CollaborationTypingLease).where(
            CollaborationTypingLease.organization_id == organization_id,
            CollaborationTypingLease.expires_at <= at,
        )
    )


def _display_name(user: User) -> str:
    return user.display_name or user.email


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
        raise CollaborationPresenceError(
            "context_not_found",
            "Collaboration context not found",
        )
    return conversation


def _other_participant(
    conversation: DirectConversation,
    user_id: uuid.UUID,
) -> tuple[uuid.UUID, datetime | None]:
    if conversation.participant_a_user_id == user_id:
        return (
            conversation.participant_b_user_id,
            conversation.participant_b_revoked_at,
        )
    if conversation.participant_b_user_id == user_id:
        return (
            conversation.participant_a_user_id,
            conversation.participant_a_revoked_at,
        )
    raise CollaborationPresenceError(
        "context_not_found",
        "Collaboration context not found",
    )


def _upsert_presence(
    db: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    expires_at: datetime,
) -> None:
    lease = db.scalar(
        select(CollaborationPresenceLease).where(
            CollaborationPresenceLease.organization_id == organization_id,
            CollaborationPresenceLease.user_id == user_id,
        )
    )
    if lease is None:
        db.add(
            CollaborationPresenceLease(
                organization_id=organization_id,
                user_id=user_id,
                expires_at=expires_at,
            )
        )
        try:
            db.commit()
            return
        except IntegrityError:
            db.rollback()
            lease = db.scalar(
                select(CollaborationPresenceLease).where(
                    CollaborationPresenceLease.organization_id == organization_id,
                    CollaborationPresenceLease.user_id == user_id,
                )
            )
            if lease is None:
                raise
    lease.expires_at = expires_at
    db.commit()


def heartbeat_presence(
    db: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    at: datetime | None = None,
) -> None:
    current = _now(at)
    if not _chat_capable_member(
        db,
        organization_id=organization_id,
        user_id=user_id,
    ):
        raise CollaborationPresenceError(
            "presence_not_available",
            "Presence is not available for this account",
        )
    _purge_expired(db, organization_id=organization_id, at=current)
    db.flush()
    _upsert_presence(
        db,
        organization_id=organization_id,
        user_id=user_id,
        expires_at=current + timedelta(seconds=PRESENCE_TTL_SECONDS),
    )


def _typing_lookup(
    db: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    context_kind: CollaborationContextKind,
    context_id: uuid.UUID,
) -> CollaborationTypingLease | None:
    query = select(CollaborationTypingLease).where(
        CollaborationTypingLease.organization_id == organization_id,
        CollaborationTypingLease.user_id == user_id,
    )
    if context_kind == CollaborationContextKind.CHANNEL:
        query = query.where(
            CollaborationTypingLease.native_channel_id == context_id,
            CollaborationTypingLease.direct_conversation_id.is_(None),
        )
    else:
        query = query.where(
            CollaborationTypingLease.direct_conversation_id == context_id,
            CollaborationTypingLease.native_channel_id.is_(None),
        )
    return db.scalar(query)


def _typing_context_values(
    context_kind: CollaborationContextKind,
    context_id: uuid.UUID,
) -> dict[str, uuid.UUID | None]:
    if context_kind == CollaborationContextKind.CHANNEL:
        return {
            "native_channel_id": context_id,
            "direct_conversation_id": None,
        }
    return {
        "native_channel_id": None,
        "direct_conversation_id": context_id,
    }


def _assert_typing_allowed(
    db: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    context_kind: CollaborationContextKind,
    context_id: uuid.UUID,
) -> None:
    if context_kind == CollaborationContextKind.CHANNEL:
        channel = get_visible_channel(
            db,
            organization_id=organization_id,
            channel_id=context_id,
            user_id=user_id,
        )
        if channel is None or not can_write_channel(db, channel, user_id=user_id):
            raise CollaborationPresenceError(
                "context_not_found",
                "Collaboration context not found",
            )
        return

    conversation = _participant_conversation(
        db,
        organization_id=organization_id,
        conversation_id=context_id,
        user_id=user_id,
    )
    other_user_id, other_revoked_at = _other_participant(conversation, user_id)
    if (
        other_revoked_at is not None
        or not _chat_capable_member(
            db,
            organization_id=organization_id,
            user_id=other_user_id,
        )
    ):
        raise CollaborationPresenceError(
            "context_not_found",
            "Collaboration context not found",
        )


def set_typing(
    db: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    context_kind: CollaborationContextKind,
    context_id: uuid.UUID,
    at: datetime | None = None,
) -> None:
    current = _now(at)
    _assert_typing_allowed(
        db,
        organization_id=organization_id,
        user_id=user_id,
        context_kind=context_kind,
        context_id=context_id,
    )
    _purge_expired(db, organization_id=organization_id, at=current)
    db.flush()

    lease = _typing_lookup(
        db,
        organization_id=organization_id,
        user_id=user_id,
        context_kind=context_kind,
        context_id=context_id,
    )
    expires_at = current + timedelta(seconds=TYPING_TTL_SECONDS)
    if lease is None:
        db.add(
            CollaborationTypingLease(
                organization_id=organization_id,
                user_id=user_id,
                expires_at=expires_at,
                **_typing_context_values(context_kind, context_id),
            )
        )
        try:
            db.commit()
            return
        except IntegrityError:
            db.rollback()
            lease = _typing_lookup(
                db,
                organization_id=organization_id,
                user_id=user_id,
                context_kind=context_kind,
                context_id=context_id,
            )
            if lease is None:
                raise
    lease.expires_at = expires_at
    db.commit()


def clear_typing(
    db: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    context_kind: CollaborationContextKind,
    context_id: uuid.UUID,
) -> None:
    query = delete(CollaborationTypingLease).where(
        CollaborationTypingLease.organization_id == organization_id,
        CollaborationTypingLease.user_id == user_id,
    )
    if context_kind == CollaborationContextKind.CHANNEL:
        query = query.where(
            CollaborationTypingLease.native_channel_id == context_id,
            CollaborationTypingLease.direct_conversation_id.is_(None),
        )
    else:
        query = query.where(
            CollaborationTypingLease.direct_conversation_id == context_id,
            CollaborationTypingLease.native_channel_id.is_(None),
        )
    db.execute(query)
    db.commit()


def _active_presence_users(
    db: Session,
    *,
    organization_id: uuid.UUID,
    at: datetime,
) -> list[tuple[CollaborationPresenceLease, Membership, User]]:
    return list(
        db.execute(
            select(CollaborationPresenceLease, Membership, User)
            .join(
                Membership,
                and_(
                    Membership.organization_id
                    == CollaborationPresenceLease.organization_id,
                    Membership.user_id == CollaborationPresenceLease.user_id,
                ),
            )
            .join(User, User.id == CollaborationPresenceLease.user_id)
            .where(
                CollaborationPresenceLease.organization_id == organization_id,
                CollaborationPresenceLease.expires_at > at,
                User.status == "active",
            )
        ).all()
    )


def _presence_user(
    db: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    at: datetime,
) -> CollaborationUserView | None:
    row = db.execute(
        select(CollaborationPresenceLease, Membership, User)
        .join(
            Membership,
            and_(
                Membership.organization_id
                == CollaborationPresenceLease.organization_id,
                Membership.user_id == CollaborationPresenceLease.user_id,
            ),
        )
        .join(User, User.id == CollaborationPresenceLease.user_id)
        .where(
            CollaborationPresenceLease.organization_id == organization_id,
            CollaborationPresenceLease.user_id == user_id,
            CollaborationPresenceLease.expires_at > at,
            User.status == "active",
        )
    ).first()
    if row is None or not role_has_permission(row[1].role, Permission.NATIVE_CHAT_WRITE):
        return None
    return CollaborationUserView(
        user_id=row[2].id,
        display_name=_display_name(row[2]),
    )


def _typing_users_for_channel(
    db: Session,
    *,
    organization_id: uuid.UUID,
    channel_id: uuid.UUID,
    current_user_id: uuid.UUID,
    at: datetime,
) -> list[CollaborationUserView]:
    channel = get_visible_channel(
        db,
        organization_id=organization_id,
        channel_id=channel_id,
        user_id=current_user_id,
    )
    if channel is None:
        raise CollaborationPresenceError(
            "context_not_found",
            "Collaboration context not found",
        )
    rows = db.execute(
        select(CollaborationTypingLease, User)
        .join(User, User.id == CollaborationTypingLease.user_id)
        .where(
            CollaborationTypingLease.organization_id == organization_id,
            CollaborationTypingLease.native_channel_id == channel_id,
            CollaborationTypingLease.direct_conversation_id.is_(None),
            CollaborationTypingLease.expires_at > at,
            CollaborationTypingLease.user_id != current_user_id,
            User.status == "active",
        )
    ).all()
    return [
        CollaborationUserView(user_id=user.id, display_name=_display_name(user))
        for lease, user in rows
        if can_write_channel(db, channel, user_id=lease.user_id)
    ]


def _channel_context(
    db: Session,
    *,
    organization_id: uuid.UUID,
    channel_id: uuid.UUID,
    current_user_id: uuid.UUID,
    at: datetime,
) -> CollaborationContextView:
    channel = get_visible_channel(
        db,
        organization_id=organization_id,
        channel_id=channel_id,
        user_id=current_user_id,
    )
    if channel is None:
        raise CollaborationPresenceError(
            "context_not_found",
            "Collaboration context not found",
        )

    online: list[CollaborationUserView] = []
    for lease, membership, user in _active_presence_users(
        db,
        organization_id=organization_id,
        at=at,
    ):
        if not role_has_permission(membership.role, Permission.NATIVE_CHAT_WRITE):
            continue
        if can_read_channel(db, channel, user_id=lease.user_id):
            online.append(
                CollaborationUserView(
                    user_id=user.id,
                    display_name=_display_name(user),
                )
            )
    online.sort(key=lambda item: (item.display_name.casefold(), item.user_id.hex))
    typing = _typing_users_for_channel(
        db,
        organization_id=organization_id,
        channel_id=channel_id,
        current_user_id=current_user_id,
        at=at,
    )
    typing.sort(key=lambda item: (item.display_name.casefold(), item.user_id.hex))
    return CollaborationContextView(online_users=online, typing_users=typing)


def _dm_context(
    db: Session,
    *,
    organization_id: uuid.UUID,
    conversation_id: uuid.UUID,
    current_user_id: uuid.UUID,
    at: datetime,
) -> CollaborationContextView:
    conversation = _participant_conversation(
        db,
        organization_id=organization_id,
        conversation_id=conversation_id,
        user_id=current_user_id,
    )
    other_user_id, other_revoked_at = _other_participant(
        conversation,
        current_user_id,
    )
    online: list[CollaborationUserView] = []
    if (
        other_revoked_at is None
        and _chat_capable_member(
            db,
            organization_id=organization_id,
            user_id=other_user_id,
        )
    ):
        visible = _presence_user(
            db,
            organization_id=organization_id,
            user_id=other_user_id,
            at=at,
        )
        if visible is not None:
            online.append(visible)

    typing: list[CollaborationUserView] = []
    if other_revoked_at is None:
        row = db.execute(
            select(CollaborationTypingLease, User)
            .join(User, User.id == CollaborationTypingLease.user_id)
            .where(
                CollaborationTypingLease.organization_id == organization_id,
                CollaborationTypingLease.direct_conversation_id == conversation_id,
                CollaborationTypingLease.native_channel_id.is_(None),
                CollaborationTypingLease.user_id == other_user_id,
                CollaborationTypingLease.expires_at > at,
                User.status == "active",
            )
        ).first()
        if row is not None and _chat_capable_member(
            db,
            organization_id=organization_id,
            user_id=other_user_id,
        ):
            typing.append(
                CollaborationUserView(
                    user_id=row[1].id,
                    display_name=_display_name(row[1]),
                )
            )
    return CollaborationContextView(online_users=online, typing_users=typing)


def get_context_presence(
    db: Session,
    *,
    organization_id: uuid.UUID,
    current_user_id: uuid.UUID,
    context_kind: CollaborationContextKind,
    context_id: uuid.UUID,
    at: datetime | None = None,
) -> CollaborationContextView:
    current = _now(at)
    _purge_expired(db, organization_id=organization_id, at=current)
    db.commit()
    if context_kind == CollaborationContextKind.CHANNEL:
        return _channel_context(
            db,
            organization_id=organization_id,
            channel_id=context_id,
            current_user_id=current_user_id,
            at=current,
        )
    return _dm_context(
        db,
        organization_id=organization_id,
        conversation_id=context_id,
        current_user_id=current_user_id,
        at=current,
    )
