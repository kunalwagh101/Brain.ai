import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.activity import (
    list_activity,
    mark_activity_read,
    mark_all_activity_read,
    unread_activity_count,
)
from app.activity_models import ActivityKind
from app.database import get_db
from app.permissions import AuthorizationContext, Permission, require_organization_permission

router = APIRouter(
    prefix="/organizations/{organization_id}/activity",
    tags=["activity"],
)
_read = require_organization_permission(Permission.ORGANIZATION_READ)


class ActivityItemRead(BaseModel):
    id: uuid.UUID
    kind: ActivityKind
    actor_display_name: str | None
    label: str
    context_label: str | None
    href: str
    read: bool
    created_at: datetime


class ActivitySummaryRead(BaseModel):
    unread_count: int
    items: list[ActivityItemRead]


class ActivityMutationRead(BaseModel):
    updated: int


@router.get("", response_model=ActivitySummaryRead)
def read_activity(
    organization_id: uuid.UUID,
    authorization: Annotated[AuthorizationContext, Depends(_read)],
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    unread_only: bool = False,
) -> ActivitySummaryRead:
    items = list_activity(
        db,
        organization_id=organization_id,
        user_id=authorization.user_id,
        limit=limit,
        unread_only=unread_only,
    )
    return ActivitySummaryRead(
        unread_count=unread_activity_count(
            db,
            organization_id=organization_id,
            user_id=authorization.user_id,
            materialize=False,
        ),
        items=[
            ActivityItemRead(
                id=item.id,
                kind=item.kind,
                actor_display_name=item.actor_display_name,
                label=item.label,
                context_label=item.context_label,
                href=item.href,
                read=item.read,
                created_at=item.created_at,
            )
            for item in items
        ],
    )


# Keep the static route before /{notification_id}/read so "read-all" can never
# be interpreted as a UUID path parameter by Starlette/FastAPI route ordering.
@router.post("/read-all", response_model=ActivityMutationRead)
def mark_all_read(
    organization_id: uuid.UUID,
    authorization: Annotated[AuthorizationContext, Depends(_read)],
    db: Annotated[Session, Depends(get_db)],
) -> ActivityMutationRead:
    return ActivityMutationRead(
        updated=mark_all_activity_read(
            db,
            organization_id=organization_id,
            user_id=authorization.user_id,
        )
    )


@router.post("/{notification_id}/read", status_code=status.HTTP_204_NO_CONTENT)
def mark_one_read(
    organization_id: uuid.UUID,
    notification_id: uuid.UUID,
    authorization: Annotated[AuthorizationContext, Depends(_read)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    mark_activity_read(
        db,
        organization_id=organization_id,
        user_id=authorization.user_id,
        notification_id=notification_id,
    )
