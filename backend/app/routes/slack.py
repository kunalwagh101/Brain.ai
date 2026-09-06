import json
import logging
import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import get_db
from app.integrations import connection_can_sync, record_sync_failure, record_sync_success
from app.models import (
    IntegrationConnection,
    IntegrationHealth,
    IntegrationStatus,
    SlackChannelAuthorization,
    User,
)
from app.permissions import (
    AuthorizationContext,
    Permission,
    authorize_organization,
    require_organization_permission,
)
from app.raw_events import MAX_RAW_EVENT_BYTES, RawEventRejectedError, persist_raw_event
from app.schemas import (
    IntegrationConnectionRead,
    SlackBackfillRead,
    SlackBackfillRequest,
    SlackChannelAuthorizationRead,
    SlackChannelPage,
    SlackChannelRead,
    SlackInstallRead,
)
from app.secrets import SecretStore, SecretStoreError, get_secret_store
from app.slack import (
    SLACK_OAUTH_SCOPES,
    SlackAPIClient,
    SlackAPIError,
    SlackConfigurationError,
    SlackTransportError,
    create_oauth_state,
    get_slack_api_client,
    require_slack_signing_secret,
    verify_oauth_state,
    verify_slack_request,
)

router = APIRouter(tags=["slack"])
logger = logging.getLogger("brain.slack")
_manage_integrations = require_organization_permission(Permission.INTEGRATION_MANAGE)


def _slack_failure(exc: Exception) -> HTTPException:
    if isinstance(exc, SlackAPIError):
        detail = f"Slack API request failed: {exc.code}"
    elif isinstance(exc, SlackConfigurationError):
        detail = "Slack integration is not configured"
    else:
        detail = "Slack is temporarily unavailable"
    return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=detail)


def _get_slack_connection(
    db: Session,
    *,
    organization_id: uuid.UUID,
    connection_id: uuid.UUID,
) -> IntegrationConnection:
    connection = db.scalar(
        select(IntegrationConnection).where(
            IntegrationConnection.id == connection_id,
            IntegrationConnection.organization_id == organization_id,
            IntegrationConnection.provider == "slack",
        )
    )
    if connection is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Slack integration not found")
    if not connection_can_sync(connection):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Slack integration is not active")
    return connection


def _bot_token(connection: IntegrationConnection, store: SecretStore) -> str:
    if not connection.secret_ref:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Slack integration is not active")
    try:
        credentials = store.load_connection_secret(connection.secret_ref)
    except SecretStoreError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Slack credentials are temporarily unavailable",
        ) from exc
    token = credentials.get("bot_token") or credentials.get("access_token")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Slack integration credentials are incomplete",
        )
    return token


def _next_cursor(payload: dict[str, object]) -> str | None:
    metadata = payload.get("response_metadata")
    if not isinstance(metadata, dict):
        return None
    cursor = metadata.get("next_cursor")
    return cursor if isinstance(cursor, str) and cursor else None


def _event_timestamp(value: object) -> datetime | None:
    try:
        return datetime.fromtimestamp(float(value), UTC)
    except (TypeError, ValueError, OSError):
        return None


@router.get(
    "/organizations/{organization_id}/integrations/slack/install",
    response_model=SlackInstallRead,
)
def slack_install(
    organization_id: uuid.UUID,
    authorization: Annotated[AuthorizationContext, Depends(_manage_integrations)],
    settings: Annotated[Settings, Depends(get_settings)],
    slack_api: Annotated[SlackAPIClient, Depends(get_slack_api_client)],
) -> SlackInstallRead:
    state_value = create_oauth_state(
        organization_id=organization_id,
        user_id=authorization.user_id,
        secret=settings.app_secret,
    )
    try:
        authorization_url = slack_api.build_authorization_url(state_value)
    except SlackConfigurationError as exc:
        raise _slack_failure(exc) from exc
    return SlackInstallRead(
        authorization_url=authorization_url,
        scopes=list(SLACK_OAUTH_SCOPES),
    )


@router.get(
    "/integrations/slack/oauth/callback",
    response_model=IntegrationConnectionRead,
)
def slack_oauth_callback(
    code: str | None,
    state: str | None,
    error: str | None,
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[Session, Depends(get_db)],
    store: Annotated[SecretStore, Depends(get_secret_store)],
    slack_api: Annotated[SlackAPIClient, Depends(get_slack_api_client)],
) -> IntegrationConnection:
    if error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Slack authorization denied")
    if not code or not state:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid Slack OAuth callback")
    try:
        organization_id, user_id = verify_oauth_state(
            state,
            secret=settings.app_secret,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")
    authorization = authorize_organization(
        db=db,
        organization_id=organization_id,
        user=user,
        permission=Permission.INTEGRATION_MANAGE,
    )

    try:
        installation = slack_api.exchange_code(code)
    except (SlackAPIError, SlackTransportError, SlackConfigurationError) as exc:
        raise _slack_failure(exc) from exc

    team = installation.get("team")
    token = installation.get("access_token")
    scope_value = installation.get("scope")
    if not isinstance(team, dict) or not isinstance(token, str) or not token:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Slack returned invalid OAuth data")
    team_id = team.get("id")
    team_name = team.get("name")
    if not isinstance(team_id, str) or not team_id:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Slack returned no workspace ID")
    if not isinstance(team_name, str) or not team_name:
        team_name = team_id
    granted_scopes = {
        item.strip() for item in scope_value.split(",") if item.strip()
    } if isinstance(scope_value, str) else set()
    missing_scopes = set(SLACK_OAUTH_SCOPES) - granted_scopes
    if missing_scopes:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Slack did not grant all required scopes",
        )

    connections = list(
        db.scalars(
            select(IntegrationConnection).where(
                IntegrationConnection.provider == "slack",
                IntegrationConnection.external_account_id == team_id,
            )
        )
    )
    for existing in connections:
        if (
            existing.organization_id != organization_id
            and existing.status != IntegrationStatus.REVOKED
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Slack workspace is already connected to another organization",
            )

    connection = next(
        (item for item in connections if item.organization_id == organization_id),
        None,
    )
    secret_slot = uuid.uuid4()
    try:
        new_secret_ref = store.store_connection_secret(
            organization_id=organization_id,
            connection_id=secret_slot,
            provider="slack",
            credentials={"bot_token": token},
        )
    except SecretStoreError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Slack credentials could not be stored",
        ) from exc

    old_secret_ref: str | None = None
    if connection is None:
        connection = IntegrationConnection(
            id=uuid.uuid4(),
            organization_id=organization_id,
            provider="slack",
            external_account_id=team_id,
            display_name=team_name,
            status=IntegrationStatus.ACTIVE,
            health=IntegrationHealth.UNKNOWN,
            scopes=sorted(granted_scopes),
            secret_ref=new_secret_ref,
            created_by_user_id=authorization.user_id,
        )
        db.add(connection)
    else:
        if connection.status == IntegrationStatus.REVOKE_FAILED:
            try:
                store.schedule_delete(new_secret_ref)
            except SecretStoreError:
                logger.exception("Failed to retire unused Slack OAuth secret")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Complete the failed revocation before reconnecting Slack",
            )
        old_secret_ref = connection.secret_ref
        connection.display_name = team_name
        connection.status = IntegrationStatus.ACTIVE
        connection.health = IntegrationHealth.UNKNOWN
        connection.scopes = sorted(granted_scopes)
        connection.secret_ref = new_secret_ref
        connection.revoked_at = None
        connection.last_error_code = None

    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        try:
            store.schedule_delete(new_secret_ref)
        except SecretStoreError:
            logger.exception("Failed to retire Slack secret after database failure")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Slack connection could not be persisted",
        ) from exc
    db.refresh(connection)

    if old_secret_ref and old_secret_ref != new_secret_ref:
        try:
            store.schedule_delete(old_secret_ref)
        except SecretStoreError:
            connection.health = IntegrationHealth.DEGRADED
            connection.last_error_code = "old_secret_retirement_failed"
            db.commit()
            db.refresh(connection)
    return connection


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
    connection = _get_slack_connection(
        db,
        organization_id=organization_id,
        connection_id=connection_id,
    )
    token = _bot_token(connection, store)
    try:
        payload = slack_api.list_channels(token, cursor=cursor)
    except (SlackAPIError, SlackTransportError) as exc:
        raise _slack_failure(exc) from exc
    raw_channels = payload.get("channels")
    if not isinstance(raw_channels, list):
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Slack returned invalid channels")

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
    return SlackChannelPage(channels=channels, next_cursor=_next_cursor(payload))


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
    connection = _get_slack_connection(
        db,
        organization_id=organization_id,
        connection_id=connection_id,
    )
    token = _bot_token(connection, store)
    try:
        payload = slack_api.conversation_info(token, channel_id)
    except (SlackAPIError, SlackTransportError) as exc:
        raise _slack_failure(exc) from exc
    channel = payload.get("channel")
    if not isinstance(channel, dict):
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Slack returned invalid channel data")
    if channel.get("is_im") or channel.get("is_mpim"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Slack DMs are not supported")
    if not channel.get("is_member"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Add the Brain Slack app to the channel before authorizing it",
        )
    name = channel.get("name")
    if not isinstance(name, str) or not name:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Slack returned no channel name")
    is_private = bool(channel.get("is_private"))
    try:
        member_ids = slack_api.conversation_members(token, channel_id) if is_private else []
    except (SlackAPIError, SlackTransportError) as exc:
        raise _slack_failure(exc) from exc

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
    _get_slack_connection(db, organization_id=organization_id, connection_id=connection_id)
    channel_authorization = db.scalar(
        select(SlackChannelAuthorization).where(
            SlackChannelAuthorization.integration_connection_id == connection_id,
            SlackChannelAuthorization.channel_id == channel_id,
        )
    )
    if channel_authorization is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Slack channel authorization not found")
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
    connection = _get_slack_connection(
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Slack channel is not authorized")
    if channel_authorization.backfill_complete and not payload.reset and payload.cursor is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Slack channel backfill is already complete")

    token = _bot_token(connection, store)
    cursor = payload.cursor if payload.cursor is not None else channel_authorization.backfill_cursor
    if payload.reset:
        cursor = None
        channel_authorization.backfill_complete = False
        channel_authorization.backfill_cursor = None

    try:
        if channel_authorization.is_private:
            channel_authorization.member_ids = slack_api.conversation_members(token, channel_id)
        history = slack_api.history(token, channel_id, cursor=cursor, limit=payload.limit)
    except SlackAPIError as exc:
        record_sync_failure(db, connection, error_code=f"slack_{exc.code}")
        raise _slack_failure(exc) from exc
    except SlackTransportError as exc:
        record_sync_failure(db, connection, error_code="slack_transport_error")
        raise _slack_failure(exc) from exc

    messages = history.get("messages")
    if not isinstance(messages, list):
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Slack returned invalid history")
    prepared: list[tuple[str, bytes, datetime | None]] = []
    for message in messages:
        if not isinstance(message, dict):
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Slack returned invalid history")
        timestamp = message.get("ts")
        if not isinstance(timestamp, str) or not timestamp:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Slack message has no timestamp")
        raw = json.dumps(
            {
                "team_id": connection.external_account_id,
                "channel_id": channel_id,
                "message": message,
            },
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
        prepared.append((timestamp, raw, _event_timestamp(timestamp)))

    inserted = 0
    duplicates = 0
    source_visibility = "private_channel" if channel_authorization.is_private else "public_channel"
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

    next_cursor = _next_cursor(history)
    channel_authorization.backfill_cursor = next_cursor
    channel_authorization.backfill_complete = next_cursor is None
    channel_authorization.last_backfilled_at = datetime.now(UTC)
    db.commit()
    record_sync_success(db, connection, cursor=connection.sync_cursor)
    return SlackBackfillRead(
        inserted=inserted,
        duplicates=duplicates,
        next_cursor=next_cursor,
        complete=next_cursor is None,
    )


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
                raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Payload too large")
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid Content-Length") from None

    raw_body = await request.body()
    if len(raw_body) > MAX_RAW_EVENT_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Payload too large")
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
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Slack signature")

    try:
        envelope = json.loads(raw_body)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid Slack JSON") from exc
    if not isinstance(envelope, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid Slack event")

    envelope_type = envelope.get("type")
    if envelope_type == "url_verification":
        challenge = envelope.get("challenge")
        if not isinstance(challenge, str):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid Slack challenge")
        return {"challenge": challenge}
    if envelope_type != "event_callback":
        return {"ok": True, "ignored": "unsupported_envelope"}

    team_id = envelope.get("team_id")
    source_event_id = envelope.get("event_id")
    event = envelope.get("event")
    if not isinstance(team_id, str) or not isinstance(source_event_id, str) or not isinstance(event, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid Slack event envelope")

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
        logger.error("Slack workspace has multiple active Brain connections", extra={"team_id": team_id})
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Slack workspace connection is ambiguous",
        )
    connection = connections[0]

    event_type = event.get("type")
    if event_type not in {"message", "member_joined_channel", "member_left_channel"}:
        return {"ok": True, "ignored": "unsupported_event"}
    channel_id = event.get("channel")
    if not isinstance(channel_id, str):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Slack event has no channel")
    channel_authorization = db.scalar(
        select(SlackChannelAuthorization).where(
            SlackChannelAuthorization.integration_connection_id == connection.id,
            SlackChannelAuthorization.channel_id == channel_id,
        )
    )
    if channel_authorization is None:
        return {"ok": True, "ignored": "channel_not_authorized"}

    source_visibility = "private_channel" if channel_authorization.is_private else "public_channel"
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
            source_visibility=source_visibility,
            source_acl=source_acl,
            source_timestamp=_event_timestamp(envelope.get("event_time")),
        )
    except RawEventRejectedError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

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

    return {"ok": True, "created": result.created}
