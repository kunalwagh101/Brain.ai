import json
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.canonical_events import canonicalize_raw_event
from app.config import Settings, get_settings
from app.database import get_db
from app.integrations import connection_can_sync
from app.models import IntegrationConnection, IntegrationStatus, SlackChannelAuthorization
from app.raw_events import MAX_RAW_EVENT_BYTES, RawEventRejectedError, persist_raw_event
from app.routes.slack_common import event_timestamp
from app.slack import SlackConfigurationError, require_slack_signing_secret, verify_slack_request

router = APIRouter(tags=["slack"])
logger = logging.getLogger("brain.slack")


@router.post("/webhooks/slack/events")
async def slack_events(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, object]:
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > MAX_RAW_EVENT_BYTES:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail="Payload too large",
                )
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid Content-Length",
            ) from None

    raw_body = await request.body()
    if len(raw_body) > MAX_RAW_EVENT_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Payload too large",
        )
    timestamp = request.headers.get("x-slack-request-timestamp", "")
    signature = request.headers.get("x-slack-signature", "")
    try:
        signing_secret = require_slack_signing_secret(settings)
    except SlackConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Slack webhook is not configured",
        ) from exc
    if not verify_slack_request(
        raw_body,
        timestamp=timestamp,
        signature=signature,
        signing_secret=signing_secret,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Slack signature",
        )

    try:
        envelope = json.loads(raw_body)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Slack JSON",
        ) from exc
    if not isinstance(envelope, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Slack event",
        )

    envelope_type = envelope.get("type")
    if envelope_type == "url_verification":
        challenge = envelope.get("challenge")
        if not isinstance(challenge, str):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid Slack challenge",
            )
        return {"challenge": challenge}
    if envelope_type != "event_callback":
        return {"ok": True, "ignored": "unsupported_envelope"}

    team_id = envelope.get("team_id")
    source_event_id = envelope.get("event_id")
    event = envelope.get("event")
    if (
        not isinstance(team_id, str)
        or not isinstance(source_event_id, str)
        or not isinstance(event, dict)
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Slack event envelope",
        )

    connections = list(
        db.scalars(
            select(IntegrationConnection).where(
                IntegrationConnection.provider == "slack",
                IntegrationConnection.external_account_id == team_id,
                IntegrationConnection.status == IntegrationStatus.ACTIVE,
            )
        )
    )
    connections = [item for item in connections if connection_can_sync(item)]
    if not connections:
        return {"ok": True, "ignored": "workspace_not_connected"}
    if len(connections) != 1:
        logger.error(
            "Slack workspace has multiple active Brain connections",
            extra={"team_id": team_id},
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Slack workspace connection is ambiguous",
        )
    connection = connections[0]

    event_type = event.get("type")
    supported = {"message", "member_joined_channel", "member_left_channel"}
    if event_type not in supported:
        return {"ok": True, "ignored": "unsupported_event"}
    channel_id = event.get("channel")
    if not isinstance(channel_id, str):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Slack event has no channel",
        )
    channel_authorization = db.scalar(
        select(SlackChannelAuthorization).where(
            SlackChannelAuthorization.integration_connection_id == connection.id,
            SlackChannelAuthorization.channel_id == channel_id,
        )
    )
    if channel_authorization is None:
        return {"ok": True, "ignored": "channel_not_authorized"}

    visibility = (
        "private_channel" if channel_authorization.is_private else "public_channel"
    )
    source_acl = channel_authorization.member_ids if channel_authorization.is_private else []
    try:
        result = persist_raw_event(
            db,
            organization_id=connection.organization_id,
            integration_connection_id=connection.id,
            provider="slack",
            source_event_id=source_event_id,
            source_event_type=event_type,
            delivery_kind="webhook",
            raw_payload=raw_body,
            content_type=request.headers.get("content-type", "application/json"),
            source_visibility=visibility,
            source_acl=source_acl,
            source_timestamp=event_timestamp(envelope.get("event_time")),
        )
    except RawEventRejectedError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    canonical = canonicalize_raw_event(db, result.event)

    if channel_authorization.is_private and event_type in {
        "member_joined_channel",
        "member_left_channel",
    }:
        member_id = event.get("user")
        if isinstance(member_id, str):
            members = set(channel_authorization.member_ids)
            if event_type == "member_joined_channel":
                members.add(member_id)
            else:
                members.discard(member_id)
            channel_authorization.member_ids = sorted(members)
            db.commit()

    return {
        "ok": True,
        "created": result.created,
        "canonical_created": canonical.created,
        "quarantined": canonical.quarantined,
    }
