import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.notification_models import NotificationKind
from app.notifications import (
    NotificationError,
    list_notifications,
    mark_all_visible_read,
    mark_notification_read,
    visible_unread_count,
)
from app.permissions import AuthorizationContext, Permission, require_organization_permission

router = APIRouter(
    prefix="/organizations/{organization_id}/notifications",
    tags=["notifications"],
)
_read = require_organization_permission(Permission.ORGANIZATION_READ)


class NotificationItemRead(BaseModel):
    id: uuid.UUID
    kind: NotificationKind
    actor_label: str
    title: str
    channel_name: str | None
    target_type: str
    target_id: uuid.UUID
    created_at: datetime
    read_at: datetime | None


class NotificationListRead(BaseModel):
    unread_count: int
    items: list[NotificationItemRead]


class NotificationReadState(BaseModel):
    id: uuid.UUID
    read_at: datetime


class NotificationBulkReadState(BaseModel):
    marked_read: int


def _item(view) -> NotificationItemRead:
    row = view.notification
    return NotificationItemRead(
        id=row.id,
        kind=row.kind,
        actor_label=view.actor_label,
        title=view.title,
        channel_name=view.channel_name,
        target_type=view.target_type,
        target_id=view.target_id,
        created_at=row.created_at,
        read_at=row.read_at,
    )


@router.get("", response_model=NotificationListRead)
def read_notifications(
    organization_id: uuid.UUID,
    authorization: Annotated[AuthorizationContext, Depends(_read)],
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    unread_only: bool = False,
) -> NotificationListRead:
    views = list_notifications(
        db,
        organization_id=organization_id,
        recipient_user_id=authorization.user_id,
        limit=limit,
        unread_only=unread_only,
    )
    return NotificationListRead(
        unread_count=visible_unread_count(
            db,
            organization_id=organization_id,
            recipient_user_id=authorization.user_id,
        ),
        items=[_item(view) for view in views],
    )


@router.post("/read-all", response_model=NotificationBulkReadState)
def read_all_notifications(
    organization_id: uuid.UUID,
    authorization: Annotated[AuthorizationContext, Depends(_read)],
    db: Annotated[Session, Depends(get_db)],
) -> NotificationBulkReadState:
    return NotificationBulkReadState(
        marked_read=mark_all_visible_read(
            db,
            organization_id=organization_id,
            recipient_user_id=authorization.user_id,
        )
    )


@router.post("/{notification_id}/read", response_model=NotificationReadState)
def read_notification(
    organization_id: uuid.UUID,
    notification_id: uuid.UUID,
    authorization: Annotated[AuthorizationContext, Depends(_read)],
    db: Annotated[Session, Depends(get_db)],
) -> NotificationReadState:
    try:
        row = mark_notification_read(
            db,
            organization_id=organization_id,
            recipient_user_id=authorization.user_id,
            notification_id=notification_id,
        )
    except NotificationError as exc:
        raise HTTPException(status_code=404, detail="Notification not found") from exc
    if row.read_at is None:
        raise HTTPException(status_code=500, detail="Notification read state unavailable")
    return NotificationReadState(id=row.id, read_at=row.read_at)
