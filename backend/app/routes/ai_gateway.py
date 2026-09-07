import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai_gateway import (
    AIGatewayError,
    AIInvocationError,
    create_model_configuration,
    create_provider_configuration,
    invoke_ai,
    revoke_provider_configuration,
    set_model_enabled,
    set_provider_enabled,
)
from app.ai_gateway_models import (
    AIModelConfiguration,
    AIProviderAdapterKind,
    AIProviderConfiguration,
    AIProviderStatus,
)
from app.database import get_db
from app.permissions import AuthorizationContext, Permission, require_organization_permission
from app.secrets import SecretStore, get_secret_store

router = APIRouter(
    prefix="/organizations/{organization_id}/ai",
    tags=["ai-gateway"],
)
_manage_ai = require_organization_permission(Permission.AI_MANAGE)
_use_ai = require_organization_permission(Permission.AI_USE)


class AIProviderCreate(BaseModel):
    provider_key: str = Field(min_length=1, max_length=64)
    display_name: str = Field(min_length=1, max_length=160)
    adapter_kind: AIProviderAdapterKind
    api_url: str = Field(min_length=1, max_length=2048)
    credentials: dict[str, str]


class AIProviderRead(BaseModel):
    id: uuid.UUID
    provider_key: str
    display_name: str
    adapter_kind: AIProviderAdapterKind
    api_url: str
    status: AIProviderStatus
    created_at: datetime
    updated_at: datetime
    credential_rotated_at: datetime | None
    revoked_at: datetime | None

    model_config = {"from_attributes": True}


class AIProviderStatusUpdate(BaseModel):
    enabled: bool


class AIModelCreate(BaseModel):
    model_key: str = Field(min_length=1, max_length=255)
    display_name: str = Field(min_length=1, max_length=255)
    enabled: bool = True
    max_output_tokens: int | None = Field(default=None, ge=1, le=1_000_000)


class AIModelRead(BaseModel):
    id: uuid.UUID
    provider_configuration_id: uuid.UUID
    model_key: str
    display_name: str
    enabled: bool
    max_output_tokens: int | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AIModelStatusUpdate(BaseModel):
    enabled: bool


class AIInvokeRequest(BaseModel):
    provider_configuration_id: uuid.UUID
    model_configuration_id: uuid.UUID
    input_text: str = Field(min_length=1, max_length=200_000)
    system_text: str | None = Field(default=None, max_length=50_000)
    max_output_tokens: int | None = Field(default=None, ge=1, le=1_000_000)
    attribution_node_id: uuid.UUID | None = None


class AIInvokeResponse(BaseModel):
    request_id: uuid.UUID
    output_text: str
    provider_request_id: str | None
    input_tokens: int | None
    output_tokens: int | None
    latency_ms: int


def _raise_gateway_error(exc: AIGatewayError) -> None:
    message = str(exc)
    if "already exists" in message:
        code = status.HTTP_409_CONFLICT
    elif "not found" in message:
        code = status.HTTP_404_NOT_FOUND
    elif message == "AI budget exhausted":
        code = status.HTTP_429_TOO_MANY_REQUESTS
    elif "credential storage failed" in message or "revocation is incomplete" in message:
        code = status.HTTP_503_SERVICE_UNAVAILABLE
    else:
        code = status.HTTP_400_BAD_REQUEST
    raise HTTPException(status_code=code, detail=message) from exc


@router.post(
    "/providers",
    response_model=AIProviderRead,
    status_code=status.HTTP_201_CREATED,
)
def create_provider(
    organization_id: uuid.UUID,
    payload: AIProviderCreate,
    authorization: Annotated[AuthorizationContext, Depends(_manage_ai)],
    db: Annotated[Session, Depends(get_db)],
    secret_store: Annotated[SecretStore, Depends(get_secret_store)],
) -> AIProviderConfiguration:
    try:
        return create_provider_configuration(
            db,
            secret_store=secret_store,
            organization_id=organization_id,
            actor_user_id=authorization.user_id,
            provider_key=payload.provider_key,
            display_name=payload.display_name,
            adapter_kind=payload.adapter_kind,
            api_url=payload.api_url,
            credentials=payload.credentials,
        )
    except AIGatewayError as exc:
        _raise_gateway_error(exc)


@router.get("/providers", response_model=list[AIProviderRead])
def list_providers(
    organization_id: uuid.UUID,
    authorization: Annotated[AuthorizationContext, Depends(_manage_ai)],
    db: Annotated[Session, Depends(get_db)],
) -> list[AIProviderConfiguration]:
    del authorization
    return list(
        db.scalars(
            select(AIProviderConfiguration)
            .where(AIProviderConfiguration.organization_id == organization_id)
            .order_by(AIProviderConfiguration.created_at, AIProviderConfiguration.id)
        )
    )


@router.post("/providers/{provider_id}/status", response_model=AIProviderRead)
def update_provider_status(
    organization_id: uuid.UUID,
    provider_id: uuid.UUID,
    payload: AIProviderStatusUpdate,
    authorization: Annotated[AuthorizationContext, Depends(_manage_ai)],
    db: Annotated[Session, Depends(get_db)],
) -> AIProviderConfiguration:
    del authorization
    try:
        return set_provider_enabled(
            db,
            organization_id=organization_id,
            provider_configuration_id=provider_id,
            enabled=payload.enabled,
        )
    except AIGatewayError as exc:
        _raise_gateway_error(exc)


@router.post("/providers/{provider_id}/revoke", response_model=AIProviderRead)
def revoke_provider(
    organization_id: uuid.UUID,
    provider_id: uuid.UUID,
    authorization: Annotated[AuthorizationContext, Depends(_manage_ai)],
    db: Annotated[Session, Depends(get_db)],
    secret_store: Annotated[SecretStore, Depends(get_secret_store)],
) -> AIProviderConfiguration:
    del authorization
    try:
        return revoke_provider_configuration(
            db,
            secret_store=secret_store,
            organization_id=organization_id,
            provider_configuration_id=provider_id,
        )
    except AIGatewayError as exc:
        _raise_gateway_error(exc)


@router.post(
    "/providers/{provider_id}/models",
    response_model=AIModelRead,
    status_code=status.HTTP_201_CREATED,
)
def create_model(
    organization_id: uuid.UUID,
    provider_id: uuid.UUID,
    payload: AIModelCreate,
    authorization: Annotated[AuthorizationContext, Depends(_manage_ai)],
    db: Annotated[Session, Depends(get_db)],
) -> AIModelConfiguration:
    try:
        return create_model_configuration(
            db,
            organization_id=organization_id,
            actor_user_id=authorization.user_id,
            provider_configuration_id=provider_id,
            model_key=payload.model_key,
            display_name=payload.display_name,
            enabled=payload.enabled,
            max_output_tokens=payload.max_output_tokens,
        )
    except AIGatewayError as exc:
        _raise_gateway_error(exc)


@router.get("/providers/{provider_id}/models", response_model=list[AIModelRead])
def list_models(
    organization_id: uuid.UUID,
    provider_id: uuid.UUID,
    authorization: Annotated[AuthorizationContext, Depends(_manage_ai)],
    db: Annotated[Session, Depends(get_db)],
) -> list[AIModelConfiguration]:
    del authorization
    provider_exists = db.scalar(
        select(AIProviderConfiguration.id).where(
            AIProviderConfiguration.id == provider_id,
            AIProviderConfiguration.organization_id == organization_id,
        )
    )
    if provider_exists is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="AI provider configuration not found",
        )
    return list(
        db.scalars(
            select(AIModelConfiguration)
            .where(
                AIModelConfiguration.organization_id == organization_id,
                AIModelConfiguration.provider_configuration_id == provider_id,
            )
            .order_by(AIModelConfiguration.created_at, AIModelConfiguration.id)
        )
    )


@router.post("/models/{model_id}/status", response_model=AIModelRead)
def update_model_status(
    organization_id: uuid.UUID,
    model_id: uuid.UUID,
    payload: AIModelStatusUpdate,
    authorization: Annotated[AuthorizationContext, Depends(_manage_ai)],
    db: Annotated[Session, Depends(get_db)],
) -> AIModelConfiguration:
    del authorization
    try:
        return set_model_enabled(
            db,
            organization_id=organization_id,
            model_configuration_id=model_id,
            enabled=payload.enabled,
        )
    except AIGatewayError as exc:
        _raise_gateway_error(exc)


@router.post("/invoke", response_model=AIInvokeResponse)
def invoke(
    organization_id: uuid.UUID,
    payload: AIInvokeRequest,
    authorization: Annotated[AuthorizationContext, Depends(_use_ai)],
    db: Annotated[Session, Depends(get_db)],
    secret_store: Annotated[SecretStore, Depends(get_secret_store)],
) -> AIInvokeResponse:
    try:
        result = invoke_ai(
            db,
            secret_store=secret_store,
            organization_id=organization_id,
            user_id=authorization.user_id,
            role=authorization.role,
            provider_configuration_id=payload.provider_configuration_id,
            model_configuration_id=payload.model_configuration_id,
            input_text=payload.input_text,
            system_text=payload.system_text,
            max_output_tokens=payload.max_output_tokens,
            attribution_node_id=payload.attribution_node_id,
        )
    except AIGatewayError as exc:
        _raise_gateway_error(exc)
    except AIInvocationError as exc:
        code = (
            status.HTTP_429_TOO_MANY_REQUESTS
            if exc.code == "rate_limited"
            else status.HTTP_503_SERVICE_UNAVAILABLE
        )
        raise HTTPException(
            status_code=code,
            detail={"code": exc.code, "request_id": str(exc.request_id)},
        ) from exc
    return AIInvokeResponse(
        request_id=result.request_id,
        output_text=result.output_text,
        provider_request_id=result.provider_request_id,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        latency_ms=result.latency_ms,
    )
