import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai_gateway_models import (
    AIModelConfiguration,
    AIProviderConfiguration,
    AIProviderStatus,
)
from app.auth import get_current_user
from app.database import get_db
from app.models import Membership, MembershipRole, Organization, User
from app.permissions import AuthorizationContext, Permission, require_organization_permission

router = APIRouter(tags=["runtime-discovery"])
_use_ai = require_organization_permission(Permission.AI_USE)


class CurrentOrganizationRead(BaseModel):
    id: uuid.UUID
    slug: str
    name: str
    role: MembershipRole


class AIRuntimeOptionRead(BaseModel):
    provider_configuration_id: uuid.UUID
    provider_key: str
    provider_display_name: str
    model_configuration_id: uuid.UUID
    model_key: str
    model_display_name: str
    max_output_tokens: int | None


@router.get("/organizations", response_model=list[CurrentOrganizationRead])
def list_current_organizations(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[CurrentOrganizationRead]:
    if current_user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
        )
    rows = db.execute(
        select(Organization, Membership.role)
        .join(Membership, Membership.organization_id == Organization.id)
        .where(Membership.user_id == current_user.id)
        .order_by(Organization.name, Organization.id)
    ).all()
    return [
        CurrentOrganizationRead(
            id=organization.id,
            slug=organization.slug,
            name=organization.name,
            role=role,
        )
        for organization, role in rows
    ]


@router.get(
    "/organizations/{organization_id}/ai/runtime-options",
    response_model=list[AIRuntimeOptionRead],
)
def list_ai_runtime_options(
    organization_id: uuid.UUID,
    authorization: Annotated[AuthorizationContext, Depends(_use_ai)],
    db: Annotated[Session, Depends(get_db)],
) -> list[AIRuntimeOptionRead]:
    del authorization
    rows = db.execute(
        select(AIProviderConfiguration, AIModelConfiguration)
        .join(
            AIModelConfiguration,
            AIModelConfiguration.provider_configuration_id
            == AIProviderConfiguration.id,
        )
        .where(
            AIProviderConfiguration.organization_id == organization_id,
            AIProviderConfiguration.status == AIProviderStatus.ENABLED,
            AIModelConfiguration.organization_id == organization_id,
            AIModelConfiguration.enabled.is_(True),
        )
        .order_by(
            AIProviderConfiguration.display_name,
            AIModelConfiguration.display_name,
            AIModelConfiguration.id,
        )
    ).all()
    return [
        AIRuntimeOptionRead(
            provider_configuration_id=provider.id,
            provider_key=provider.provider_key,
            provider_display_name=provider.display_name,
            model_configuration_id=model.id,
            model_key=model.model_key,
            model_display_name=model.display_name,
            max_output_tokens=model.max_output_tokens,
        )
        for provider, model in rows
    ]
