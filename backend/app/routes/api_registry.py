import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api_registry import (
    APIRegistryError,
    change_api_grant_environment,
    change_api_grant_owner,
    change_api_grant_scopes,
    create_api_grant,
    create_api_service,
    revoke_api_grant,
    rotate_api_grant_credentials,
    set_api_grant_enabled,
)
from app.api_registry_models import (
    APICredentialGrant,
    APIGrantHistory,
    APIGrantHistoryAction,
    APIGrantStatus,
    APIService,
    APIUsageObservation,
)
from app.database import get_db
from app.permissions import AuthorizationContext, Permission, require_organization_permission
from app.secrets import SecretStore, get_secret_store

router = APIRouter(
    prefix="/organizations/{organization_id}/api-registry",
    tags=["api-registry"],
)
_manage = require_organization_permission(Permission.API_MANAGE)
_read = require_organization_permission(Permission.AUDIT_READ)


class APIServiceCreate(BaseModel):
    service_key: str = Field(min_length=1, max_length=64)
    display_name: str = Field(min_length=1, max_length=160)
    provider_name: str = Field(min_length=1, max_length=160)
    base_url: str | None = Field(default=None, max_length=2048)


class APIServiceRead(BaseModel):
    id: uuid.UUID
    service_key: str
    display_name: str
    provider_name: str
    base_url: str | None
    created_by_user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class APIGrantCreate(BaseModel):
    service_id: uuid.UUID
    grant_key: str = Field(min_length=1, max_length=96)
    display_name: str = Field(min_length=1, max_length=160)
    owner_user_id: uuid.UUID
    environment: str = Field(min_length=1, max_length=64)
    scopes: list[str] = Field(min_length=1, max_length=128)
    expires_at: datetime | None = None
    credentials: dict[str, str]


class APIGrantRead(BaseModel):
    id: uuid.UUID
    service_id: uuid.UUID
    grant_key: str
    display_name: str
    owner_user_id: uuid.UUID
    environment: str
    scopes: list[str]
    status: APIGrantStatus
    expires_at: datetime | None
    credential_present: bool
    credential_rotated_at: datetime | None
    last_used_at: datetime | None
    usage_count: int
    last_usage_success: bool | None
    last_usage_latency_ms: int | None
    created_by_user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    revoked_at: datetime | None
    expired_at: datetime | None


class APIGrantOwnerUpdate(BaseModel):
    owner_user_id: uuid.UUID
    reason: str | None = Field(default=None, max_length=512)


class APIGrantScopesUpdate(BaseModel):
    scopes: list[str] = Field(min_length=1, max_length=128)
    reason: str | None = Field(default=None, max_length=512)


class APIGrantEnvironmentUpdate(BaseModel):
    environment: str = Field(min_length=1, max_length=64)
    reason: str | None = Field(default=None, max_length=512)


class APIGrantStatusUpdate(BaseModel):
    enabled: bool
    reason: str | None = Field(default=None, max_length=512)


class APIGrantCredentialRotate(BaseModel):
    credentials: dict[str, str]
    reason: str | None = Field(default=None, max_length=512)


class APIGrantRevoke(BaseModel):
    reason: str | None = Field(default=None, max_length=512)


class APIGrantHistoryRead(BaseModel):
    id: uuid.UUID
    action: APIGrantHistoryAction
    actor_user_id: uuid.UUID | None
    previous_status: str | None
    new_status: str | None
    previous_owner_user_id: uuid.UUID | None
    new_owner_user_id: uuid.UUID | None
    previous_scopes: list[str] | None
    new_scopes: list[str] | None
    previous_environment: str | None
    new_environment: str | None
    reason: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class APIUsageObservationRead(BaseModel):
    id: uuid.UUID
    observation_key: str
    caller_component: str
    operation_label: str | None
    success: bool
    latency_ms: int | None
    observed_at: datetime

    model_config = {"from_attributes": True}


def _grant_read(grant: APICredentialGrant) -> APIGrantRead:
    return APIGrantRead(
        id=grant.id,
        service_id=grant.service_id,
        grant_key=grant.grant_key,
        display_name=grant.display_name,
        owner_user_id=grant.owner_user_id,
        environment=grant.environment,
        scopes=list(grant.scopes),
        status=grant.status,
        expires_at=grant.expires_at,
        credential_present=bool(grant.secret_ref),
        credential_rotated_at=grant.credential_rotated_at,
        last_used_at=grant.last_used_at,
        usage_count=grant.usage_count,
        last_usage_success=grant.last_usage_success,
        last_usage_latency_ms=grant.last_usage_latency_ms,
        created_by_user_id=grant.created_by_user_id,
        created_at=grant.created_at,
        updated_at=grant.updated_at,
        revoked_at=grant.revoked_at,
        expired_at=grant.expired_at,
    )


def _raise_registry_error(exc: APIRegistryError) -> None:
    message = str(exc)
    if "already exists" in message:
        code = status.HTTP_409_CONFLICT
    elif "not found" in message:
        code = status.HTTP_404_NOT_FOUND
    elif "storage failed" in message or "revocation is incomplete" in message:
        code = status.HTTP_503_SERVICE_UNAVAILABLE
    else:
        code = status.HTTP_400_BAD_REQUEST
    raise HTTPException(status_code=code, detail=message) from exc


@router.post("/services", response_model=APIServiceRead, status_code=status.HTTP_201_CREATED)
def create_service(
    organization_id: uuid.UUID,
    payload: APIServiceCreate,
    authorization: Annotated[AuthorizationContext, Depends(_manage)],
    db: Annotated[Session, Depends(get_db)],
) -> APIService:
    try:
        return create_api_service(
            db,
            organization_id=organization_id,
            actor_user_id=authorization.user_id,
            service_key=payload.service_key,
            display_name=payload.display_name,
            provider_name=payload.provider_name,
            base_url=payload.base_url,
        )
    except APIRegistryError as exc:
        _raise_registry_error(exc)


@router.get("/services", response_model=list[APIServiceRead])
def list_services(
    organization_id: uuid.UUID,
    authorization: Annotated[AuthorizationContext, Depends(_read)],
    db: Annotated[Session, Depends(get_db)],
) -> list[APIService]:
    del authorization
    return list(
        db.scalars(
            select(APIService)
            .where(APIService.organization_id == organization_id)
            .order_by(APIService.display_name, APIService.id)
        )
    )


@router.post("/grants", response_model=APIGrantRead, status_code=status.HTTP_201_CREATED)
def create_grant(
    organization_id: uuid.UUID,
    payload: APIGrantCreate,
    authorization: Annotated[AuthorizationContext, Depends(_manage)],
    db: Annotated[Session, Depends(get_db)],
    secret_store: Annotated[SecretStore, Depends(get_secret_store)],
) -> APIGrantRead:
    try:
        grant = create_api_grant(
            db,
            secret_store=secret_store,
            organization_id=organization_id,
            actor_user_id=authorization.user_id,
            service_id=payload.service_id,
            grant_key=payload.grant_key,
            display_name=payload.display_name,
            owner_user_id=payload.owner_user_id,
            environment=payload.environment,
            scopes=payload.scopes,
            expires_at=payload.expires_at,
            credentials=payload.credentials,
        )
    except APIRegistryError as exc:
        _raise_registry_error(exc)
    return _grant_read(grant)


@router.get("/grants", response_model=list[APIGrantRead])
def list_grants(
    organization_id: uuid.UUID,
    authorization: Annotated[AuthorizationContext, Depends(_read)],
    db: Annotated[Session, Depends(get_db)],
    service_id: uuid.UUID | None = None,
    owner_user_id: uuid.UUID | None = None,
    grant_status: APIGrantStatus | None = None,
) -> list[APIGrantRead]:
    del authorization
    query = select(APICredentialGrant).where(
        APICredentialGrant.organization_id == organization_id
    )
    if service_id is not None:
        query = query.where(APICredentialGrant.service_id == service_id)
    if owner_user_id is not None:
        query = query.where(APICredentialGrant.owner_user_id == owner_user_id)
    if grant_status is not None:
        query = query.where(APICredentialGrant.status == grant_status)
    grants = list(
        db.scalars(query.order_by(APICredentialGrant.created_at, APICredentialGrant.id))
    )
    return [_grant_read(grant) for grant in grants]


@router.get("/grants/{grant_id}", response_model=APIGrantRead)
def read_grant(
    organization_id: uuid.UUID,
    grant_id: uuid.UUID,
    authorization: Annotated[AuthorizationContext, Depends(_read)],
    db: Annotated[Session, Depends(get_db)],
) -> APIGrantRead:
    del authorization
    grant = db.scalar(
        select(APICredentialGrant).where(
            APICredentialGrant.id == grant_id,
            APICredentialGrant.organization_id == organization_id,
        )
    )
    if grant is None:
        raise HTTPException(status_code=404, detail="API grant not found")
    return _grant_read(grant)


@router.post("/grants/{grant_id}/owner", response_model=APIGrantRead)
def update_grant_owner(
    organization_id: uuid.UUID,
    grant_id: uuid.UUID,
    payload: APIGrantOwnerUpdate,
    authorization: Annotated[AuthorizationContext, Depends(_manage)],
    db: Annotated[Session, Depends(get_db)],
) -> APIGrantRead:
    try:
        grant = change_api_grant_owner(
            db,
            organization_id=organization_id,
            grant_id=grant_id,
            actor_user_id=authorization.user_id,
            owner_user_id=payload.owner_user_id,
            reason=payload.reason,
        )
    except APIRegistryError as exc:
        _raise_registry_error(exc)
    return _grant_read(grant)


@router.post("/grants/{grant_id}/scopes", response_model=APIGrantRead)
def update_grant_scopes(
    organization_id: uuid.UUID,
    grant_id: uuid.UUID,
    payload: APIGrantScopesUpdate,
    authorization: Annotated[AuthorizationContext, Depends(_manage)],
    db: Annotated[Session, Depends(get_db)],
) -> APIGrantRead:
    try:
        grant = change_api_grant_scopes(
            db,
            organization_id=organization_id,
            grant_id=grant_id,
            actor_user_id=authorization.user_id,
            scopes=payload.scopes,
            reason=payload.reason,
        )
    except APIRegistryError as exc:
        _raise_registry_error(exc)
    return _grant_read(grant)


@router.post("/grants/{grant_id}/environment", response_model=APIGrantRead)
def update_grant_environment(
    organization_id: uuid.UUID,
    grant_id: uuid.UUID,
    payload: APIGrantEnvironmentUpdate,
    authorization: Annotated[AuthorizationContext, Depends(_manage)],
    db: Annotated[Session, Depends(get_db)],
) -> APIGrantRead:
    try:
        grant = change_api_grant_environment(
            db,
            organization_id=organization_id,
            grant_id=grant_id,
            actor_user_id=authorization.user_id,
            environment=payload.environment,
            reason=payload.reason,
        )
    except APIRegistryError as exc:
        _raise_registry_error(exc)
    return _grant_read(grant)


@router.post("/grants/{grant_id}/status", response_model=APIGrantRead)
def update_grant_status(
    organization_id: uuid.UUID,
    grant_id: uuid.UUID,
    payload: APIGrantStatusUpdate,
    authorization: Annotated[AuthorizationContext, Depends(_manage)],
    db: Annotated[Session, Depends(get_db)],
) -> APIGrantRead:
    try:
        grant = set_api_grant_enabled(
            db,
            organization_id=organization_id,
            grant_id=grant_id,
            actor_user_id=authorization.user_id,
            enabled=payload.enabled,
            reason=payload.reason,
        )
    except APIRegistryError as exc:
        _raise_registry_error(exc)
    return _grant_read(grant)


@router.post("/grants/{grant_id}/rotate", response_model=APIGrantRead)
def rotate_grant(
    organization_id: uuid.UUID,
    grant_id: uuid.UUID,
    payload: APIGrantCredentialRotate,
    authorization: Annotated[AuthorizationContext, Depends(_manage)],
    db: Annotated[Session, Depends(get_db)],
    secret_store: Annotated[SecretStore, Depends(get_secret_store)],
) -> APIGrantRead:
    try:
        grant = rotate_api_grant_credentials(
            db,
            secret_store=secret_store,
            organization_id=organization_id,
            grant_id=grant_id,
            actor_user_id=authorization.user_id,
            credentials=payload.credentials,
            reason=payload.reason,
        )
    except APIRegistryError as exc:
        _raise_registry_error(exc)
    return _grant_read(grant)


@router.post("/grants/{grant_id}/revoke", response_model=APIGrantRead)
def revoke_grant(
    organization_id: uuid.UUID,
    grant_id: uuid.UUID,
    payload: APIGrantRevoke,
    authorization: Annotated[AuthorizationContext, Depends(_manage)],
    db: Annotated[Session, Depends(get_db)],
    secret_store: Annotated[SecretStore, Depends(get_secret_store)],
) -> APIGrantRead:
    try:
        grant = revoke_api_grant(
            db,
            secret_store=secret_store,
            organization_id=organization_id,
            grant_id=grant_id,
            actor_user_id=authorization.user_id,
            reason=payload.reason,
        )
    except APIRegistryError as exc:
        _raise_registry_error(exc)
    return _grant_read(grant)


@router.get("/grants/{grant_id}/history", response_model=list[APIGrantHistoryRead])
def read_grant_history(
    organization_id: uuid.UUID,
    grant_id: uuid.UUID,
    authorization: Annotated[AuthorizationContext, Depends(_read)],
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[APIGrantHistory]:
    del authorization
    exists = db.scalar(
        select(APICredentialGrant.id).where(
            APICredentialGrant.id == grant_id,
            APICredentialGrant.organization_id == organization_id,
        )
    )
    if exists is None:
        raise HTTPException(status_code=404, detail="API grant not found")
    return list(
        db.scalars(
            select(APIGrantHistory)
            .where(
                APIGrantHistory.organization_id == organization_id,
                APIGrantHistory.grant_id == grant_id,
            )
            .order_by(APIGrantHistory.created_at.desc(), APIGrantHistory.id.desc())
            .limit(limit)
        )
    )


@router.get("/grants/{grant_id}/usage", response_model=list[APIUsageObservationRead])
def read_grant_usage(
    organization_id: uuid.UUID,
    grant_id: uuid.UUID,
    authorization: Annotated[AuthorizationContext, Depends(_read)],
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[APIUsageObservation]:
    del authorization
    exists = db.scalar(
        select(APICredentialGrant.id).where(
            APICredentialGrant.id == grant_id,
            APICredentialGrant.organization_id == organization_id,
        )
    )
    if exists is None:
        raise HTTPException(status_code=404, detail="API grant not found")
    return list(
        db.scalars(
            select(APIUsageObservation)
            .where(
                APIUsageObservation.organization_id == organization_id,
                APIUsageObservation.grant_id == grant_id,
            )
            .order_by(APIUsageObservation.observed_at.desc())
            .limit(limit)
        )
    )
