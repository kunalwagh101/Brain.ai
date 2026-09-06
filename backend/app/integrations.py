from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models import IntegrationConnection, IntegrationHealth, IntegrationStatus


class IntegrationNotSyncableError(RuntimeError):
    pass


def connection_can_sync(connection: IntegrationConnection) -> bool:
    return connection.status == IntegrationStatus.ACTIVE and bool(connection.secret_ref)


def ensure_connection_can_sync(connection: IntegrationConnection) -> None:
    if not connection_can_sync(connection):
        raise IntegrationNotSyncableError("Integration connection is not active")


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
    return connection
