import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Membership, User
from app.notification_models import NotificationKind, WorkspaceNotification

MAX_NOTIFICATION_METADATA_FIELDS = 8
MAX_NOTIFICATION_METADATA_KEY = 64
MAX_NOTIFICATION_METADATA_STRING = 256


def _safe_metadata(value: dict | None) -> dict:
    if not value:
        return {}
    if len(value) > MAX_NOTIFICATION_METADATA_FIELDS:
        raise ValueError("Notification metadata has too many fields")
    result: dict[str, str | int | bool | None] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not key or len(key) > MAX_NOTIFICATION_METADATA_KEY:
            raise ValueError("Notification metadata key is invalid")
        if isinstance(item, str):
            if len(item) > MAX_NOTIFICATION_METADATA_STRING:
                raise ValueError("Notification metadata value is too long")
            result[key] = item
        elif item is None or isinstance(item, (int, bool)):
            result[key] = item
        else:
            raise ValueError("Notification metadata value is invalid")
    return result


def create_workspace_notification(
    db: Session,
    *,
    organization_id: uuid.UUID,
    recipient_user_id: uuid.UUID,
    kind: NotificationKind,
    dedupe_key: str,
    actor_user_id: uuid.UUID | None = None,
    channel_id: uuid.UUID | None = None,
    native_message_id: uuid.UUID | None = None,
    direct_conversation_id: uuid.UUID | None = None,
    direct_message_id: uuid.UUID | None = None,
    event_metadata: dict | None = None,
) -> WorkspaceNotification | None:
    if actor_user_id == recipient_user_id:
        return None
    key = dedupe_key.strip()
    if not key or len(key) > 255:
        raise ValueError("Notification dedupe key is invalid")

    active_member = db.scalar(
        select(Membership.user_id)
        .join(User, User.id == Membership.user_id)
        .where(
            Membership.organization_id == organization_id,
            Membership.user_id == recipient_user_id,
            User.status == "active",
        )
    )
    if active_member is None:
        return None

    existing = db.scalar(
        select(WorkspaceNotification).where(
            WorkspaceNotification.organization_id == organization_id,
            WorkspaceNotification.recipient_user_id == recipient_user_id,
            WorkspaceNotification.dedupe_key == key,
        )
    )
    if existing is not None:
        return existing

    row = WorkspaceNotification(
        organization_id=organization_id,
        recipient_user_id=recipient_user_id,
        kind=kind,
        dedupe_key=key,
        actor_user_id=actor_user_id,
        channel_id=channel_id,
        native_message_id=native_message_id,
        direct_conversation_id=direct_conversation_id,
        direct_message_id=direct_message_id,
        event_metadata=_safe_metadata(event_metadata),
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return db.scalar(
            select(WorkspaceNotification).where(
                WorkspaceNotification.organization_id == organization_id,
                WorkspaceNotification.recipient_user_id == recipient_user_id,
                WorkspaceNotification.dedupe_key == key,
            )
        )
    db.refresh(row)
    return row
