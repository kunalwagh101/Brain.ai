import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.activity import list_activity, mark_activity_read, mark_all_activity_read
from app.activity_inbox import (
    get_activity_preferences,
    kind_enabled,
    list_system_activity,
    mark_all_system_activity_read,
    mark_system_activity_read,
    materialize_system_activity,
    precise_chat_href,
    preference_payload,
    update_activity_preferences,
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


class ActivityPreferencesRead(BaseModel):
    mentions: bool
    thread_replies: bool
    direct_messages: bool
    channel_activity: bool
    agent_approvals: bool
    agent_run_events: bool
    project_updates: bool
    integration_failures: bool


class ActivityPreferencesUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mentions: bool | None = None
    thread_replies: bool | None = None
    direct_messages: bool | None = None
    channel_activity: bool | None = None
    agent_approvals: bool | None = None
    agent_run_events: bool | None = None
    project_updates: bool | None = None
    integration_failures: bool | None = None


def _item(item, *, db: Session) -> ActivityItemRead:
    return ActivityItemRead(
        id=item.id,
        kind=item.kind,
        actor_display_name=item.actor_display_name,
        label=item.label,
        context_label=item.context_label,
        href=precise_chat_href(db, item),
        read=item.read,
        created_at=item.created_at,
    )


def _deduplicate_channel_summaries(db: Session, chat_items, system_items):
    precise_chat_links = [precise_chat_href(db, item).split("#", 1)[0] for item in chat_items]
    result = []
    for item in system_items:
        if item.kind == ActivityKind.CHANNEL_ACTIVITY:
            target = item.href.split("#", 1)[0]
            if any(link == target or link.startswith(f"{target}&") for link in precise_chat_links):
                continue
        result.append(item)
    return result


@router.get("", response_model=ActivitySummaryRead)
def read_activity(
    organization_id: uuid.UUID,
    authorization: Annotated[AuthorizationContext, Depends(_read)],
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    unread_only: bool = False,
) -> ActivitySummaryRead:
    materialize_system_activity(
        db,
        organization_id=organization_id,
        user_id=authorization.user_id,
    )
    preferences = get_activity_preferences(
        db,
        organization_id=organization_id,
        user_id=authorization.user_id,
    )
    chat_items = [
        item
        for item in list_activity(
            db,
            organization_id=organization_id,
            user_id=authorization.user_id,
            limit=limit,
            unread_only=unread_only,
        )
        if kind_enabled(preferences, item.kind)
    ]
    system_items = _deduplicate_channel_summaries(
        db,
        chat_items,
        list_system_activity(
            db,
            organization_id=organization_id,
            user_id=authorization.user_id,
            limit=limit,
            unread_only=unread_only,
        ),
    )
    items = sorted(
        [*chat_items, *system_items],
        key=lambda item: (item.created_at, item.id.int),
        reverse=True,
    )[:limit]

    unread_chat_items = [
        item
        for item in list_activity(
            db,
            organization_id=organization_id,
            user_id=authorization.user_id,
            limit=500,
            unread_only=True,
            materialize=False,
        )
        if kind_enabled(preferences, item.kind)
    ]
    dedup_chat_items = [
        item
        for item in list_activity(
            db,
            organization_id=organization_id,
            user_id=authorization.user_id,
            limit=500,
            unread_only=False,
            materialize=False,
        )
        if kind_enabled(preferences, item.kind)
    ]
    unread_system_items = _deduplicate_channel_summaries(
        db,
        dedup_chat_items,
        list_system_activity(
            db,
            organization_id=organization_id,
            user_id=authorization.user_id,
            limit=500,
            unread_only=True,
        ),
    )
    return ActivitySummaryRead(
        unread_count=len(unread_chat_items) + len(unread_system_items),
        items=[_item(item, db=db) for item in items],
    )


@router.get("/preferences", response_model=ActivityPreferencesRead)
def read_preferences(
    organization_id: uuid.UUID,
    authorization: Annotated[AuthorizationContext, Depends(_read)],
    db: Annotated[Session, Depends(get_db)],
) -> ActivityPreferencesRead:
    row = get_activity_preferences(
        db,
        organization_id=organization_id,
        user_id=authorization.user_id,
    )
    return ActivityPreferencesRead(**preference_payload(row))


@router.put("/preferences", response_model=ActivityPreferencesRead)
def write_preferences(
    organization_id: uuid.UUID,
    payload: ActivityPreferencesUpdate,
    authorization: Annotated[AuthorizationContext, Depends(_read)],
    db: Annotated[Session, Depends(get_db)],
) -> ActivityPreferencesRead:
    values = payload.model_dump(exclude_none=True)
    if not values:
        raise HTTPException(status_code=422, detail="At least one preference is required")
    row = update_activity_preferences(
        db,
        organization_id=organization_id,
        user_id=authorization.user_id,
        values=values,
    )
    return ActivityPreferencesRead(**preference_payload(row))


# Keep the static route before /{notification_id}/read so "read-all" can never
# be interpreted as a UUID path parameter by Starlette/FastAPI route ordering.
@router.post("/read-all", response_model=ActivityMutationRead)
def mark_all_read(
    organization_id: uuid.UUID,
    authorization: Annotated[AuthorizationContext, Depends(_read)],
    db: Annotated[Session, Depends(get_db)],
) -> ActivityMutationRead:
    materialize_system_activity(
        db,
        organization_id=organization_id,
        user_id=authorization.user_id,
    )
    return ActivityMutationRead(
        updated=mark_all_activity_read(
            db,
            organization_id=organization_id,
            user_id=authorization.user_id,
        )
        + mark_all_system_activity_read(
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
    if mark_system_activity_read(
        db,
        organization_id=organization_id,
        user_id=authorization.user_id,
        notification_id=notification_id,
    ):
        return
    mark_activity_read(
        db,
        organization_id=organization_id,
        user_id=authorization.user_id,
        notification_id=notification_id,
    )
