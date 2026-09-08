import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.data_governance import (
    DataGovernanceError,
    create_deletion_request,
    execute_deletion_request,
    run_retention_once,
    set_retention_policy,
)
from app.data_governance_models import (
    DataDeletionRequest,
    DeletionScope,
    DeletionStatus,
    OrganizationRetentionPolicy,
    RetentionRun,
    RetentionRunStatus,
    SecurityAuditEvent,
)
from app.database import get_db
from app.permissions import AuthorizationContext, Permission, require_organization_permission

router = APIRouter(
    prefix="/organizations/{organization_id}/data-governance",
    tags=["data-governance"],
)
_manage = require_organization_permission(Permission.DATA_GOVERNANCE_MANAGE)
_read_audit = require_organization_permission(Permission.AUDIT_READ)


class RetentionPolicyUpdate(BaseModel):
    raw_event_days: int | None = Field(default=None, ge=1, le=36_500)
    derived_content_days: int | None = Field(default=None, ge=1, le=36_500)
    audit_event_days: int | None = Field(default=None, ge=1, le=36_500)
    legal_hold: bool = False


class RetentionPolicyRead(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    raw_event_days: int | None
    derived_content_days: int | None
    audit_event_days: int | None
    legal_hold: bool
    updated_by_user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RetentionRunRead(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    status: RetentionRunStatus
    raw_event_days: int | None
    derived_content_days: int | None
    audit_event_days: int | None
    raw_events_deleted: int
    derived_events_deleted: int
    audit_events_deleted: int
    error_code: str | None
    started_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class DataDeletionCreate(BaseModel):
    request_key: str = Field(min_length=1, max_length=128)
    scope: DeletionScope
    reason: str = Field(min_length=1, max_length=512)
    integration_connection_id: uuid.UUID | None = None
    source_provider: str | None = Field(default=None, max_length=40)
    object_type: str | None = Field(default=None, max_length=64)
    object_external_id: str | None = Field(default=None, max_length=512)


class DataDeletionRead(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    request_key: str
    scope: DeletionScope
    target_reference: str
    integration_connection_id: uuid.UUID | None
    source_provider: str | None
    object_type: str | None
    object_external_id: str | None
    status: DeletionStatus
    requested_by_user_id: uuid.UUID
    reason: str
    raw_events_deleted: int
    canonical_events_deleted: int
    completion_digest: str | None
    error_code: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class AuditEventRead(BaseModel):
    id: uuid.UUID
    event_key: str
    event_type: str
    outcome: str
    actor_user_id: uuid.UUID | None
    resource_type: str | None
    resource_id: str | None
    request_id: str | None
    metadata_json: dict[str, object]
    payload_sha256: str
    created_at: datetime

    model_config = {"from_attributes": True}


def _request_id(request: Request) -> str | None:
    value = getattr(request.state, "request_id", None)
    return value if isinstance(value, str) else None


def _raise_governance_error(exc: DataGovernanceError) -> None:
    message = str(exc)
    if "not found" in message:
        code = status.HTTP_404_NOT_FOUND
    elif "legal hold" in message or "must be fully revoked" in message:
        code = status.HTTP_409_CONFLICT
    elif "reused" in message:
        code = status.HTTP_409_CONFLICT
    else:
        code = status.HTTP_400_BAD_REQUEST
    raise HTTPException(status_code=code, detail=message) from exc


@router.get("/retention-policy", response_model=RetentionPolicyRead | None)
def read_retention_policy(
    organization_id: uuid.UUID,
    authorization: Annotated[AuthorizationContext, Depends(_read_audit)],
    db: Annotated[Session, Depends(get_db)],
) -> OrganizationRetentionPolicy | None:
    del authorization
    return db.scalar(
        select(OrganizationRetentionPolicy).where(
            OrganizationRetentionPolicy.organization_id == organization_id
        )
    )


@router.put("/retention-policy", response_model=RetentionPolicyRead)
def update_retention_policy(
    organization_id: uuid.UUID,
    payload: RetentionPolicyUpdate,
    request: Request,
    authorization: Annotated[AuthorizationContext, Depends(_manage)],
    db: Annotated[Session, Depends(get_db)],
) -> OrganizationRetentionPolicy:
    try:
        return set_retention_policy(
            db,
            organization_id=organization_id,
            actor_user_id=authorization.user_id,
            raw_event_days=payload.raw_event_days,
            derived_content_days=payload.derived_content_days,
            audit_event_days=payload.audit_event_days,
            legal_hold=payload.legal_hold,
            request_id=_request_id(request),
        )
    except DataGovernanceError as exc:
        _raise_governance_error(exc)


@router.post("/retention/run", response_model=RetentionRunRead | None)
def execute_retention(
    organization_id: uuid.UUID,
    request: Request,
    authorization: Annotated[AuthorizationContext, Depends(_manage)],
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=500)] = 500,
) -> RetentionRun | None:
    try:
        return run_retention_once(
            db,
            organization_id=organization_id,
            limit=limit,
            actor_user_id=authorization.user_id,
            request_id=_request_id(request),
        )
    except DataGovernanceError as exc:
        _raise_governance_error(exc)


@router.get("/retention/runs", response_model=list[RetentionRunRead])
def list_retention_runs(
    organization_id: uuid.UUID,
    authorization: Annotated[AuthorizationContext, Depends(_read_audit)],
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[RetentionRun]:
    del authorization
    return list(
        db.scalars(
            select(RetentionRun)
            .where(RetentionRun.organization_id == organization_id)
            .order_by(RetentionRun.started_at.desc(), RetentionRun.id.desc())
            .limit(limit)
        )
    )


@router.post(
    "/deletions",
    response_model=DataDeletionRead,
    status_code=status.HTTP_201_CREATED,
)
def request_deletion(
    organization_id: uuid.UUID,
    payload: DataDeletionCreate,
    request: Request,
    authorization: Annotated[AuthorizationContext, Depends(_manage)],
    db: Annotated[Session, Depends(get_db)],
) -> DataDeletionRequest:
    try:
        return create_deletion_request(
            db,
            organization_id=organization_id,
            actor_user_id=authorization.user_id,
            request_key=payload.request_key,
            scope=payload.scope,
            reason=payload.reason,
            integration_connection_id=payload.integration_connection_id,
            source_provider=payload.source_provider,
            object_type=payload.object_type,
            object_external_id=payload.object_external_id,
            request_id=_request_id(request),
        )
    except DataGovernanceError as exc:
        _raise_governance_error(exc)


@router.post("/deletions/{deletion_request_id}/execute", response_model=DataDeletionRead)
def execute_deletion(
    organization_id: uuid.UUID,
    deletion_request_id: uuid.UUID,
    request: Request,
    authorization: Annotated[AuthorizationContext, Depends(_manage)],
    db: Annotated[Session, Depends(get_db)],
) -> DataDeletionRequest:
    del authorization
    try:
        return execute_deletion_request(
            db,
            organization_id=organization_id,
            deletion_request_id=deletion_request_id,
            request_id=_request_id(request),
        )
    except DataGovernanceError as exc:
        _raise_governance_error(exc)


@router.get("/deletions", response_model=list[DataDeletionRead])
def list_deletions(
    organization_id: uuid.UUID,
    authorization: Annotated[AuthorizationContext, Depends(_read_audit)],
    db: Annotated[Session, Depends(get_db)],
    deletion_status: DeletionStatus | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[DataDeletionRequest]:
    del authorization
    query = select(DataDeletionRequest).where(
        DataDeletionRequest.organization_id == organization_id
    )
    if deletion_status is not None:
        query = query.where(DataDeletionRequest.status == deletion_status)
    return list(
        db.scalars(
            query.order_by(DataDeletionRequest.created_at.desc()).limit(limit)
        )
    )


@router.get("/audit-events", response_model=list[AuditEventRead])
def list_audit_events(
    organization_id: uuid.UUID,
    authorization: Annotated[AuthorizationContext, Depends(_read_audit)],
    db: Annotated[Session, Depends(get_db)],
    event_type: Annotated[str | None, Query(max_length=128)] = None,
    outcome: Annotated[str | None, Query(max_length=32)] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[SecurityAuditEvent]:
    del authorization
    query = select(SecurityAuditEvent).where(
        SecurityAuditEvent.organization_id == organization_id
    )
    if event_type:
        query = query.where(SecurityAuditEvent.event_type == event_type)
    if outcome:
        query = query.where(SecurityAuditEvent.outcome == outcome)
    return list(
        db.scalars(
            query.order_by(SecurityAuditEvent.created_at.desc(), SecurityAuditEvent.id.desc())
            .limit(limit)
        )
    )
