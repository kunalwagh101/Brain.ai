import json
import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.integrations import record_sync_failure, record_sync_success
from app.models import SlackChannelAuthorization
from app.permissions import AuthorizationContext, Permission, require_organization_permission
from app.raw_events import persist_raw_event
from app.routes.slack_common import (
    bot_token,
    event_timestamp,
    get_slack_connection,
    next_cursor,
    slack_failure,
)
from app.schemas import (
    SlackBackfillRead,
    SlackBackfillRequest,
    SlackChannelAuthorizationRead,
    SlackChannelPage,
    SlackChannelRead,
)
from app.secrets import SecretStore, get_secret_store
from app.slack import SlackAPIClient, SlackAPIError, SlackTransportError, get_slack_api_client

router = APIRouter(tags=["slack"])
_manage_integrations = require_organization_permission(Permission.INTEGRATION_MANAGE)


@router.get(
    "/organizations/{organization_id}/integrations/{connection_id}/slack/channels",
    response_model=SlackChannelPage,
)
def list_slack_channels(
    organization_id: uuid.UUID,
    connection_id: uuid.UUID,
    authorization: Annotated[AuthorizationContext, Depends(_manage_integrations)],
    db: Annotated[Session, Depends(get_db)],
    store: Annotated[SecretStore, Depends(get_secret_store)],
    slack_api: Annotated[SlackAPIClient, Depends(get_slack_api_client)],
    cursor: str | None = None,
) -> SlackChannelPage:
    del authorization
    connection = get_slack_connection(
        db,
        organization_id=organization_id,
        connection_id=connection_id,
    )
    token = bot_token(connection, store)
    try:
        payload = slack_api.list_channels(token, cursor=cursor)
    except (SlackAPIError, SlackTransportError) as exc:
        raise slack_failure(exc) from exc
    raw_channels = payload.get("channels")
    if not isinstance(raw_channels, list):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Slack returned invalid channels",
        )

    channels: list[SlackChannelRead] = []
    for item in raw_channels:
        if not isinstance(item, dict) or item.get("is_im") or item.get("is_mpim"):
            continue
        channel_id = item.get("id")
        name = item.get("name")
        if isinstance(channel_id, str) and isinstance(name, str):
            channels.append(
                SlackChannelRead(
                    id=channel_id,
                    name=name,
                    is_private=bool(item.get("is_private")),
                    is_member=bool(item.get("is_member")),
                )
            )
    return SlackChannelPage(channels=channels, next_cursor=next_cursor(payload))


@router.post(
    "/organizations/{organization_id}/integrations/{connection_id}/slack/channels/"
    "{channel_id}/authorize",
    response_model=SlackChannelAuthorizationRead,
)
def authorize_slack_channel(
    organization_id: uuid.UUID,
    connection_id: uuid.UUID,
    channel_id: str,
    authorization: Annotated[AuthorizationContext, Depends(_manage_integrations)],
    db: Annotated[Session, Depends(get_db)],
    store: Annotated[SecretStore, Depends(get_secret_store)],
    slack_api: Annotated[SlackAPIClient, Depends(get_slack_api_client)],
) -> SlackChannelAuthorization:
    connection = get_slack_connection(
        db,
        organization_id=organization_id,
        connection_id=connection_id,
    )
    token = bot_token(connection, store)
    try:
        payload = slack_api.conversation_info(token, channel_id)
    except (SlackAPIError, SlackTransportError) as exc:
        raise slack_failure(exc) from exc
    channel = payload.get("channel")
    if not isinstance(channel, dict):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Slack returned invalid channel data",
        )
    if channel.get("is_im") or channel.get("is_mpim"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Slack DMs are not supported",
        )
    if not channel.get("is_member"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Add the Brain Slack app to the channel before authorizing it",
        )
    name = channel.get("name")
    if not isinstance(name, str) or not name:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Slack returned no channel name",
        )
    is_private = bool(channel.get("is_private"))
    try:
        member_ids = slack_api.conversation_members(token, channel_id) if is_private else []
    except (SlackAPIError, SlackTransportError) as exc:
        raise slack_failure(exc) from exc

    channel_authorization = db.scalar(
        select(SlackChannelAuthorization).where(
            SlackChannelAuthorization.integration_connection_id == connection_id,
            SlackChannelAuthorization.channel_id == channel_id,
        )
    )
    if channel_authorization is None:
        channel_authorization = SlackChannelAuthorization(
            organization_id=organization_id,
            integration_connection_id=connection_id,
            channel_id=channel_id,
            channel_name=name,
            is_private=is_private,
            member_ids=member_ids,
            authorized_by_user_id=authorization.user_id,
        )
        db.add(channel_authorization)
    else:
        channel_authorization.channel_name = name
        channel_authorization.is_private = is_private
        channel_authorization.member_ids = member_ids
        channel_authorization.authorized_by_user_id = authorization.user_id
    db.commit()
    db.refresh(channel_authorization)
    return channel_authorization


@router.delete(
    "/organizations/{organization_id}/integrations/{connection_id}/slack/channels/"
    "{channel_id}/authorize",
    status_code=status.HTTP_204_NO_CONTENT,
)
def revoke_slack_channel_authorization(
    organization_id: uuid.UUID,
    connection_id: uuid.UUID,
    channel_id: str,
    authorization: Annotated[AuthorizationContext, Depends(_manage_integrations)],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    del authorization
    get_slack_connection(
        db,
        organization_id=organization_id,
        connection_id=connection_id,
    )
    channel_authorization = db.scalar(
        select(SlackChannelAuthorization).where(
            SlackChannelAuthorization.integration_connection_id == connection_id,
            SlackChannelAuthorization.channel_id == channel_id,
        )
    )
    if channel_authorization is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Slack channel authorization not found",
        )
    db.delete(channel_authorization)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/organizations/{organization_id}/integrations/{connection_id}/slack/channels/"
    "{channel_id}/backfill",
    response_model=SlackBackfillRead,
)
def backfill_slack_channel(
    organization_id: uuid.UUID,
    connection_id: uuid.UUID,
    channel_id: str,
    payload: SlackBackfillRequest,
    authorization: Annotated[AuthorizationContext, Depends(_manage_integrations)],
    db: Annotated[Session, Depends(get_db)],
    store: Annotated[SecretStore, Depends(get_secret_store)],
    slack_api: Annotated[SlackAPIClient, Depends(get_slack_api_client)],
) -> SlackBackfillRead:
    del authorization
    connection = get_slack_connection(
        db,
        organization_id=organization_id,
        connection_id=connection_id,
    )
    channel_authorization = db.scalar(
        select(SlackChannelAuthorization).where(
            SlackChannelAuthorization.integration_connection_id == connection_id,
            SlackChannelAuthorization.channel_id == channel_id,
        )
    )
    if channel_authorization is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Slack channel is not authorized",
        )
    if (
        channel_authorization.backfill_complete
        and not payload.reset
        and payload.cursor is None
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Slack channel backfill is already complete",
        )

    token = bot_token(connection, store)
    cursor = payload.cursor if payload.cursor is not None else channel_authorization.backfill_cursor
    if payload.reset:
        cursor = None
        channel_authorization.backfill_complete = False
        channel_authorization.backfill_cursor = None

    try:
        if channel_authorization.is_private:
            channel_authorization.member_ids = slack_api.conversation_members(
                token,
                channel_id,
            )
        history = slack_api.history(
            token,
            channel_id,
            cursor=cursor,
            limit=payload.limit,
        )
    except SlackAPIError as exc:
        record_sync_failure(
            db,
            connection,
            error_code=f"slack_{exc.code}"[:128],
        )
        raise slack_failure(exc) from exc
    except SlackTransportError as exc:
        record_sync_failure(db, connection, error_code="slack_transport_error")
        raise slack_failure(exc) from exc

    messages = history.get("messages")
    if not isinstance(messages, list):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Slack returned invalid history",
        )

    prepared: list[tuple[str, bytes, datetime | None]] = []
    for message in messages:
        if not isinstance(message, dict):
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Slack returned invalid history",
            )
        timestamp = message.get("ts")
        if not isinstance(timestamp, str) or not timestamp:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Slack message has no timestamp",
            )
        raw = json.dumps(
            {
                "team_id": connection.external_account_id,
                "channel_id": channel_id,
                "message": message,
            },
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
        prepared.append((timestamp, raw, event_timestamp(timestamp)))

    inserted = 0
    duplicates = 0
    source_visibility = (
        "private_channel" if channel_authorization.is_private else "public_channel"
    )
    source_acl = channel_authorization.member_ids if channel_authorization.is_private else []
    for timestamp, raw, source_timestamp in prepared:
        result = persist_raw_event(
            db,
            organization_id=organization_id,
            integration_connection_id=connection_id,
            provider="slack",
            source_event_id=f"history:{channel_id}:{timestamp}",
            source_event_type="message",
            delivery_kind="backfill",
            raw_payload=raw,
            content_type="application/json",
            source_visibility=source_visibility,
            source_acl=source_acl,
            source_timestamp=source_timestamp,
        )
        if result.created:
            inserted += 1
        else:
            duplicates += 1

    cursor_after = next_cursor(history)
    channel_authorization.backfill_cursor = cursor_after
    channel_authorization.backfill_complete = cursor_after is None
    channel_authorization.last_backfilled_at = datetime.now(UTC)
    db.commit()
    record_sync_success(db, connection, cursor=connection.sync_cursor)
    return SlackBackfillRead(
        inserted=inserted,
        duplicates=duplicates,
        next_cursor=cursor_after,
        complete=cursor_after is None,
    )
