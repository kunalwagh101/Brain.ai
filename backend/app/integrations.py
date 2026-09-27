import logging
from datetime import UTC, datetime

from opentelemetry import trace
from sqlalchemy.orm import Session

from app.models import IntegrationConnection, IntegrationHealth, IntegrationStatus
from app.observability import log_event, record_connector_sync

logger = logging.getLogger("brain.connector")


class IntegrationNotSyncableError(RuntimeError):
    """Raised when a connector attempts to use an inactive connection."""


def connection_can_sync(connection: IntegrationConnection) -> bool:
    if connection.status != IntegrationStatus.ACTIVE:
        return False
    if connection.provider == "github":
        return bool(connection.external_account_id)
    return bool(connection.secret_ref)


def ensure_connection_can_sync(connection: IntegrationConnection) -> None:
    if not connection_can_sync(connection):
        raise IntegrationNotSyncableError("Integration connection is not active")


def _emit_sync_telemetry(
    connection: IntegrationConnection,
    *,
    succeeded: bool,
    error_code: str | None,
) -> None:
    record_connector_sync(provider=connection.provider, succeeded=succeeded)
    log_event(
        logger,
        logging.INFO if succeeded else logging.ERROR,
        "connector.sync.succeeded" if succeeded else "connector.sync.failed",
        organization_id=connection.organization_id,
        integration_id=connection.id,
        provider=connection.provider,
        error_code=error_code,
    )
    span = trace.get_current_span()
    if span.get_span_context().is_valid:
        span.add_event(
            "connector.sync.succeeded" if succeeded else "connector.sync.failed",
            {
                "brain.integration_id": str(connection.id),
                "brain.provider": connection.provider,
                "brain.error_code": error_code or "",
            },
        )


def record_sync_success(
    db: Session,
    connection: IntegrationConnection,
    *,
    cursor: str | None,
) -> IntegrationConnection:
    ensure_connection_can_sync(connection)
    connection.health = IntegrationHealth.HEALTHY
    connection.sync_cursor = cursor
    connection.last_synced_at = datetime.now(UTC)
    connection.last_error_code = None
    db.commit()
    db.refresh(connection)
    _emit_sync_telemetry(connection, succeeded=True, error_code=None)
    return connection


def record_sync_failure(
    db: Session,
    connection: IntegrationConnection,
    *,
    error_code: str,
) -> IntegrationConnection:
    ensure_connection_can_sync(connection)
    normalized = error_code.strip()
    if not normalized or len(normalized) > 128:
        raise ValueError("error_code must be 1-128 characters")
    connection.health = IntegrationHealth.ERROR
    connection.last_error_code = normalized
    db.commit()
    db.refresh(connection)
    _emit_sync_telemetry(connection, succeeded=False, error_code=normalized)
    return connection
