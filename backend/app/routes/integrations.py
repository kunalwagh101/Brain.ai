import logging
import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import IntegrationConnection, IntegrationHealth, IntegrationStatus
from app.permissions import AuthorizationContext, Permission, require_organization_permission
from app.schemas import IntegrationConnectionCreate, IntegrationConnectionRead
from app.secrets import SecretStore, SecretStoreError, get_secret_store

router = APIRouter(prefix="/organizations/{organization_id}/integrations", tags=["integrations"])
logger = logging.getLogger("brain.integrations")

_manage_integrations = require_organization_permission(Permission.INTEGRATION_MANAGE)


def _get_connection(
    db: Session,
    *,
    organization_id: uuid.UUID,
    connection_id: uuid.UUID,
) -> IntegrationConnection:
    connection = db.scalar(
        select(IntegrationConnection).where(
            IntegrationConnection.id == connection_id,
            IntegrationConnection.organization_id == organization_id,
        )
    )
    if connection is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")
    return connection


def _cleanup_secret(store: SecretStore, reference: str) -> None:
    try:
        store.schedule_delete(reference)
    except SecretStoreError:
        logger.exception("Failed to clean up orphaned integration secret")


@router.post("", response_model=IntegrationConnectionRead, status_code=status.HTTP_201_CREATED)
def create_integration(
    organization_id: uuid.UUID,
    payload: IntegrationConnectionCreate,
    authorization: Annotated[AuthorizationContext, Depends(_manage_integrations)],
    db: Annotated[Session, Depends(get_db)],
    secret_store: Annotated[SecretStore, Depends(get_secret_store)],
) -> IntegrationConnection:
    provider = payload.provider.strip().lower()
    if provider == "github":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Use the verified GitHub App installation flow",
        )
    external_account_id = payload.external_account_id.strip()
    duplicate = db.scalar(
        select(IntegrationConnection.id).where(
            IntegrationConnection.organization_id == organization_id,
            IntegrationConnection.provider == provider,
            IntegrationConnection.external_account_id == external_account_id,
        )
    )
    if duplicate is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Integration connection already exists",
        )

    connection_id = uuid.uuid4()
    try:
        secret_ref = secret_store.store_connection_secret(
            organization_id=organization_id,
            connection_id=connection_id,
            provider=provider,
            credentials=payload.credentials,
        )
    except SecretStoreError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Credential storage is temporarily unavailable",
        ) from exc

    connection = IntegrationConnection(
        id=connection_id,
        organization_id=organization_id,
        provider=provider,
        external_account_id=external_account_id,
        display_name=payload.display_name.strip(),
        status=IntegrationStatus.ACTIVE,
        health=IntegrationHealth.UNKNOWN,
        scopes=payload.scopes,
        provider_metadata={},
        secret_ref=secret_ref,
        created_by_user_id=authorization.user_id,
    )
    db.add(connection)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        _cleanup_secret(secret_store, secret_ref)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Integration connection already exists",
        ) from None
    except SQLAlchemyError as exc:
        db.rollback()
        _cleanup_secret(secret_store, secret_ref)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Integration could not be persisted",
        ) from exc

    db.refresh(connection)
    return connection


@router.get("", response_model=list[IntegrationConnectionRead])
def list_integrations(
    organization_id: uuid.UUID,
    authorization: Annotated[AuthorizationContext, Depends(_manage_integrations)],
    db: Annotated[Session, Depends(get_db)],
) -> list[IntegrationConnection]:
    del authorization
    return list(
        db.scalars(
            select(IntegrationConnection)
            .where(IntegrationConnection.organization_id == organization_id)
            .order_by(IntegrationConnection.created_at, IntegrationConnection.id)
        )
    )


@router.get("/{connection_id}", response_model=IntegrationConnectionRead)
def read_integration(
    organization_id: uuid.UUID,
    connection_id: uuid.UUID,
    authorization: Annotated[AuthorizationContext, Depends(_manage_integrations)],
    db: Annotated[Session, Depends(get_db)],
) -> IntegrationConnection:
    del authorization
    return _get_connection(db, organization_id=organization_id, connection_id=connection_id)


@router.post("/{connection_id}/revoke", response_model=IntegrationConnectionRead)
def revoke_integration(
    organization_id: uuid.UUID,
    connection_id: uuid.UUID,
    authorization: Annotated[AuthorizationContext, Depends(_manage_integrations)],
    db: Annotated[Session, Depends(get_db)],
    secret_store: Annotated[SecretStore, Depends(get_secret_store)],
) -> IntegrationConnection:
    del authorization
    connection = _get_connection(db, organization_id=organization_id, connection_id=connection_id)
    if connection.status == IntegrationStatus.REVOKED:
        return connection

    reference = connection.secret_ref
    connection.status = IntegrationStatus.REVOKING
    db.commit()
    db.refresh(connection)

    if reference:
        try:
            secret_store.schedule_delete(reference)
        except SecretStoreError as exc:
            connection.status = IntegrationStatus.REVOKE_FAILED
            connection.health = IntegrationHealth.ERROR
            connection.last_error_code = "secret_delete_failed"
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Integration revocation is incomplete",
            ) from exc

    connection.status = IntegrationStatus.REVOKED
    connection.health = IntegrationHealth.UNKNOWN
    connection.secret_ref = None
    connection.revoked_at = datetime.now(UTC)
    connection.last_error_code = None
    db.commit()
    db.refresh(connection)
    return connection
