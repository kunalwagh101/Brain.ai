import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.ai_gateway_models import AIProviderAdapterKind, AIProviderConfiguration, AIProviderStatus
from app.ai_provider_adapter import AIGatewayError
from app.ai_provider_credentials import rotate_ai_provider_credentials
from app.database import get_db
from app.permissions import AuthorizationContext, Permission, require_organization_permission
from app.secrets import SecretStore, get_secret_store

router = APIRouter(
    prefix="/organizations/{organization_id}/ai/providers",
    tags=["ai-provider-credentials"],
)
_manage_ai = require_organization_permission(Permission.AI_MANAGE)


class AIProviderCredentialRotate(BaseModel):
    credentials: dict[str, str]

    model_config = {"extra": "forbid"}


class AIProviderCredentialRead(BaseModel):
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


def _raise_gateway_error(exc: AIGatewayError) -> None:
    message = str(exc)
    if "not found" in message:
        code = status.HTTP_404_NOT_FOUND
    elif "rotation failed" in message:
        code = status.HTTP_503_SERVICE_UNAVAILABLE
    elif "revocation" in message or "no credential secret reference" in message:
        code = status.HTTP_409_CONFLICT
    else:
        code = status.HTTP_400_BAD_REQUEST
    raise HTTPException(status_code=code, detail=message) from exc


@router.post("/{provider_id}/rotate", response_model=AIProviderCredentialRead)
def rotate_provider_credentials(
    organization_id: uuid.UUID,
    provider_id: uuid.UUID,
    payload: AIProviderCredentialRotate,
    authorization: Annotated[AuthorizationContext, Depends(_manage_ai)],
    db: Annotated[Session, Depends(get_db)],
    secret_store: Annotated[SecretStore, Depends(get_secret_store)],
) -> AIProviderConfiguration:
    del authorization
    try:
        return rotate_ai_provider_credentials(
            db,
            secret_store=secret_store,
            organization_id=organization_id,
            provider_configuration_id=provider_id,
            credentials=payload.credentials,
        )
    except AIGatewayError as exc:
        _raise_gateway_error(exc)
