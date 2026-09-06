import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.integrations import connection_can_sync
from app.models import IntegrationConnection
from app.secrets import SecretStore, SecretStoreError
from app.slack import SlackAPIError, SlackConfigurationError


def slack_failure(exc: Exception) -> HTTPException:
    if isinstance(exc, SlackAPIError):
        detail = f"Slack API request failed: {exc.code}"
    elif isinstance(exc, SlackConfigurationError):
        detail = "Slack integration is not configured"
    else:
        detail = "Slack is temporarily unavailable"
    return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=detail)


def get_slack_connection(
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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Slack integration not found",
        )
    if not connection_can_sync(connection):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Slack integration is not active",
        )
    return connection


def bot_token(connection: IntegrationConnection, store: SecretStore) -> str:
    if not connection.secret_ref:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Slack integration is not active",
        )
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


def next_cursor(payload: dict[str, object]) -> str | None:
    metadata = payload.get("response_metadata")
    if not isinstance(metadata, dict):
        return None
    cursor = metadata.get("next_cursor")
    return cursor if isinstance(cursor, str) and cursor else None


def event_timestamp(value: object) -> datetime | None:
    try:
        return datetime.fromtimestamp(float(value), UTC)
    except (TypeError, ValueError, OSError):
        return None
