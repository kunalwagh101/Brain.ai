import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.direct_message_models import DirectConversation, DirectMessage
from app.models import Membership, User
from app.native_chat import get_visible_channel
from app.native_chat_models import NativeMessage
from app.notification_models import NotificationKind, WorkspaceNotification
from app.permissions import Permission, role_has_permission


class NotificationError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code[:128]


@dataclass(frozen=True, slots=True)
class NotificationView:
    notification: WorkspaceNotification
    actor_label: str
    title: str
    channel_name: str | None
    target_type: str
    target_id: uuid.UUID


def _actor_label(db: Session, notification: WorkspaceNotification) -> str:
    if notification.actor_user_id is None:
        if notification.event_metadata.get("agent_run_id"):
            return "Brain agent"
        return "Brain"
    user = db.get(User, notification.actor_user_id)
    if user is None:
        return "Former Brain member"
    return user.display_name or user.email


def _dm_accessible(
    db: Session,
    *,
    notification: WorkspaceNotification,
) -> tuple[DirectConversation, DirectMessage] | None:
    if notification.direct_conversation_id is None or notification.direct_message_id is None:
        return None
    membership = db.scalar(
        select(Membership).where(
            Membership.organization_id == notification.organization_id,
            Membership.user_id == notification.recipient_user_id,
        )
    )
    user = db.get(User, notification.recipient_user_id)
    if (
        membership is None
        or user is None
        or user.status != "active"
        or not role_has_permission(membership.role, Permission.NATIVE_CHAT_WRITE)
    ):
        return None

    conversation = db.scalar(
        select(DirectConversation).where(
            DirectConversation.id == notification.direct_conversation_id,
            DirectConversation.organization_id == notification.organization_id,
        )
    )
    if conversation is None:
        return None
    if conversation.participant_a_user_id == notification.recipient_user_id:
        if conversation.participant_a_revoked_at is not None:
            return None
        visible_from = conversation.participant_a_visible_from_sequence
    elif conversation.participant_b_user_id == notification.recipient_user_id:
        if conversation.participant_b_revoked_at is not None:
            return None
        visible_from = conversation.participant_b_visible_from_sequence
    else:
        return None

    message = db.scalar(
        select(DirectMessage).where(
            DirectMessage.id == notification.direct_message_id,
            DirectMessage.organization_id == notification.organization_id,
            DirectMessage.conversation_id == conversation.id,
        )
    )
    if message is None or message.sequence < visible_from:
        return None
    return conversation, message


def notification_view(
    db: Session,
    *,
    notification: WorkspaceNotification,
) -> NotificationView | None:
    actor = _actor_label(db, notification)
    if notification.kind == NotificationKind.DIRECT_MESSAGE:
        dm = _dm_accessible(db, notification=notification)
        if dm is None:
            return None
        conversation, _ = dm
        return NotificationView(
            notification=notification,
            actor_label=actor,
            title=f"{actor} sent you a direct message",
            channel_name=None,
            target_type="direct_message",
            target_id=conversation.id,
        )

    if notification.channel_id is None or notification.native_message_id is None:
        return None
    channel = get_visible_channel(
        db,
        organization_id=notification.organization_id,
        channel_id=notification.channel_id,
        user_id=notification.recipient_user_id,
    )
    message = db.scalar(
        select(NativeMessage).where(
            NativeMessage.id == notification.native_message_id,
            NativeMessage.organization_id == notification.organization_id,
            NativeMessage.channel_id == notification.channel_id,
        )
    )
    if channel is None or message is None:
        return None

    if notification.kind == NotificationKind.MENTION:
        title = f"{actor} mentioned you in #{channel.name}"
    elif notification.kind == NotificationKind.THREAD_REPLY:
        title = f"{actor} replied in a thread in #{channel.name}"
    elif notification.kind == NotificationKind.REACTION:
        reaction = str(notification.event_metadata.get("reaction") or "")
        title = f"{actor} reacted {reaction} to your message in #{channel.name}".replace("  ", " ")
    else:
        return None
    return NotificationView(
        notification=notification,
        actor_label=actor,
        title=title,
        channel_name=channel.name,
        target_type="channel",
        target_id=channel.id,
    )


def list_notifications(
    db: Session,
    *,
    organization_id: uuid.UUID,
    recipient_user_id: uuid.UUID,
    limit: int,
    unread_only: bool = False,
) -> list[NotificationView]:
    query = select(WorkspaceNotification).where(
        WorkspaceNotification.organization_id == organization_id,
        WorkspaceNotification.recipient_user_id == recipient_user_id,
    )
    if unread_only:
        query = query.where(WorkspaceNotification.read_at.is_(None))
    rows = list(
        db.scalars(
            query.order_by(
                WorkspaceNotification.created_at.desc(),
                WorkspaceNotification.id.desc(),
            )
        )
    )
    visible: list[NotificationView] = []
    for row in rows:
        view = notification_view(db, notification=row)
        if view is not None:
            visible.append(view)
            if len(visible) >= limit:
                break
    return visible


def visible_unread_count(
    db: Session,
    *,
    organization_id: uuid.UUID,
    recipient_user_id: uuid.UUID,
) -> int:
    rows = list(
        db.scalars(
            select(WorkspaceNotification).where(
                WorkspaceNotification.organization_id == organization_id,
                WorkspaceNotification.recipient_user_id == recipient_user_id,
                WorkspaceNotification.read_at.is_(None),
            )
        )
    )
    return sum(1 for row in rows if notification_view(db, notification=row) is not None)


def mark_notification_read(
    db: Session,
    *,
    organization_id: uuid.UUID,
    recipient_user_id: uuid.UUID,
    notification_id: uuid.UUID,
) -> WorkspaceNotification:
    row = db.scalar(
        select(WorkspaceNotification).where(
            WorkspaceNotification.id == notification_id,
            WorkspaceNotification.organization_id == organization_id,
            WorkspaceNotification.recipient_user_id == recipient_user_id,
        )
    )
    if row is None or notification_view(db, notification=row) is None:
        raise NotificationError("notification_not_found", "Notification not found")
    if row.read_at is None:
        row.read_at = datetime.now(UTC)
        db.commit()
        db.refresh(row)
    return row


def mark_all_visible_read(
    db: Session,
    *,
    organization_id: uuid.UUID,
    recipient_user_id: uuid.UUID,
) -> int:
    rows = list(
        db.scalars(
            select(WorkspaceNotification).where(
                WorkspaceNotification.organization_id == organization_id,
                WorkspaceNotification.recipient_user_id == recipient_user_id,
                WorkspaceNotification.read_at.is_(None),
            )
        )
    )
    now = datetime.now(UTC)
    changed = 0
    for row in rows:
        if notification_view(db, notification=row) is None:
            continue
        row.read_at = now
        changed += 1
    if changed:
        db.commit()
    return changed
