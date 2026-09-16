import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai_gateway_models import AIModelConfiguration, AIProviderConfiguration
from app.api_registry_models import APICredentialGrant, APIService
from app.database import get_db
from app.models import IntegrationConnection, Membership, MembershipRole, Organization, User
from app.permissions import (
    AuthorizationContext,
    Permission,
    require_organization_permission,
    role_has_permission,
)

router = APIRouter(
    prefix="/organizations/{organization_id}/admin-center",
    tags=["admin-center"],
)
_admin_entry = require_organization_permission(Permission.MEMBERSHIP_MANAGE)
_REQUIRED_ADMIN_PERMISSIONS = (
    Permission.MEMBERSHIP_MANAGE,
    Permission.INTEGRATION_MANAGE,
    Permission.AI_MANAGE,
    Permission.API_MANAGE,
)


class AdminMemberRead(BaseModel):
    membership_id: uuid.UUID
    user_id: uuid.UUID
    email: str
    display_name: str | None
    role: MembershipRole
    joined_at: datetime


class AdminIntegrationRead(BaseModel):
    id: uuid.UUID
    provider: str
    display_name: str
    status: str
    health: str
    scopes: list[str]
    last_synced_at: datetime | None
    last_error_code: str | None
    created_at: datetime
    revoked_at: datetime | None


class AdminAIModelRead(BaseModel):
    id: uuid.UUID
    model_key: str
    display_name: str
    enabled: bool
    max_output_tokens: int | None


class AdminAIProviderRead(BaseModel):
    id: uuid.UUID
    provider_key: str
    display_name: str
    adapter_kind: str
    api_url: str
    status: str
    models: list[AdminAIModelRead]
    credential_rotated_at: datetime | None
    revoked_at: datetime | None


class AdminAPIGrantRead(BaseModel):
    id: uuid.UUID
    grant_key: str
    display_name: str
    owner_user_id: uuid.UUID
    owner_email: str | None
    environment: str
    scopes: list[str]
    status: str
    expires_at: datetime | None
    credential_present: bool
    credential_rotated_at: datetime | None
    last_used_at: datetime | None
    usage_count: int
    last_usage_success: bool | None
    last_usage_latency_ms: int | None


class AdminAPIServiceRead(BaseModel):
    id: uuid.UUID
    service_key: str
    display_name: str
    provider_name: str
    base_url: str | None
    grants: list[AdminAPIGrantRead]


class AdminCenterSummaryRead(BaseModel):
    member_count: int
    integration_count: int
    unhealthy_integration_count: int
    ai_provider_count: int
    enabled_ai_model_count: int
    api_service_count: int
    active_api_grant_count: int
    expiring_api_grant_count: int


class AdminCenterRead(BaseModel):
    organization_id: uuid.UUID
    organization_name: str
    organization_slug: str
    members: list[AdminMemberRead]
    integrations: list[AdminIntegrationRead]
    ai_providers: list[AdminAIProviderRead]
    api_services: list[AdminAPIServiceRead]
    summary: AdminCenterSummaryRead


def _require_complete_admin_role(authorization: AuthorizationContext) -> None:
    if not all(
        role_has_permission(authorization.role, permission)
        for permission in _REQUIRED_ADMIN_PERMISSIONS
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
        )


@router.get("", response_model=AdminCenterRead)
def read_admin_center(
    organization_id: uuid.UUID,
    authorization: Annotated[AuthorizationContext, Depends(_admin_entry)],
    db: Annotated[Session, Depends(get_db)],
) -> AdminCenterRead:
    _require_complete_admin_role(authorization)

    organization = db.scalar(
        select(Organization).where(Organization.id == organization_id)
    )
    if organization is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    member_rows = list(
        db.execute(
            select(Membership, User)
            .join(User, User.id == Membership.user_id)
            .where(Membership.organization_id == organization_id)
            .order_by(User.email, Membership.id)
        ).all()
    )
    members = [
        AdminMemberRead(
            membership_id=membership.id,
            user_id=membership.user_id,
            email=user.email,
            display_name=user.display_name,
            role=membership.role,
            joined_at=membership.created_at,
        )
        for membership, user in member_rows
    ]
    member_email_by_id = {item.user_id: item.email for item in members}

    integration_rows = list(
        db.scalars(
            select(IntegrationConnection)
            .where(IntegrationConnection.organization_id == organization_id)
            .order_by(IntegrationConnection.display_name, IntegrationConnection.id)
        )
    )
    integrations = [
        AdminIntegrationRead(
            id=item.id,
            provider=item.provider,
            display_name=item.display_name,
            status=item.status.value,
            health=item.health.value,
            scopes=list(item.scopes),
            last_synced_at=item.last_synced_at,
            last_error_code=item.last_error_code,
            created_at=item.created_at,
            revoked_at=item.revoked_at,
        )
        for item in integration_rows
    ]

    provider_rows = list(
        db.scalars(
            select(AIProviderConfiguration)
            .where(AIProviderConfiguration.organization_id == organization_id)
            .order_by(AIProviderConfiguration.display_name, AIProviderConfiguration.id)
        )
    )
    model_rows = list(
        db.scalars(
            select(AIModelConfiguration)
            .where(AIModelConfiguration.organization_id == organization_id)
            .order_by(AIModelConfiguration.display_name, AIModelConfiguration.id)
        )
    )
    models_by_provider: dict[uuid.UUID, list[AdminAIModelRead]] = {}
    for model in model_rows:
        models_by_provider.setdefault(model.provider_configuration_id, []).append(
            AdminAIModelRead(
                id=model.id,
                model_key=model.model_key,
                display_name=model.display_name,
                enabled=model.enabled,
                max_output_tokens=model.max_output_tokens,
            )
        )
    ai_providers = [
        AdminAIProviderRead(
            id=item.id,
            provider_key=item.provider_key,
            display_name=item.display_name,
            adapter_kind=item.adapter_kind.value,
            api_url=item.api_url,
            status=item.status.value,
            models=models_by_provider.get(item.id, []),
            credential_rotated_at=item.credential_rotated_at,
            revoked_at=item.revoked_at,
        )
        for item in provider_rows
    ]

    service_rows = list(
        db.scalars(
            select(APIService)
            .where(APIService.organization_id == organization_id)
            .order_by(APIService.display_name, APIService.id)
        )
    )
    grant_rows = list(
        db.scalars(
            select(APICredentialGrant)
            .where(APICredentialGrant.organization_id == organization_id)
            .order_by(APICredentialGrant.display_name, APICredentialGrant.id)
        )
    )
    grants_by_service: dict[uuid.UUID, list[AdminAPIGrantRead]] = {}
    for grant in grant_rows:
        grants_by_service.setdefault(grant.service_id, []).append(
            AdminAPIGrantRead(
                id=grant.id,
                grant_key=grant.grant_key,
                display_name=grant.display_name,
                owner_user_id=grant.owner_user_id,
                owner_email=member_email_by_id.get(grant.owner_user_id),
                environment=grant.environment,
                scopes=list(grant.scopes),
                status=grant.status.value,
                expires_at=grant.expires_at,
                credential_present=bool(grant.secret_ref),
                credential_rotated_at=grant.credential_rotated_at,
                last_used_at=grant.last_used_at,
                usage_count=grant.usage_count,
                last_usage_success=grant.last_usage_success,
                last_usage_latency_ms=grant.last_usage_latency_ms,
            )
        )
    api_services = [
        AdminAPIServiceRead(
            id=item.id,
            service_key=item.service_key,
            display_name=item.display_name,
            provider_name=item.provider_name,
            base_url=item.base_url,
            grants=grants_by_service.get(item.id, []),
        )
        for item in service_rows
    ]

    unhealthy_integrations = sum(
        1
        for item in integrations
        if item.health not in {"healthy", "unknown"} or item.status != "active"
    )
    enabled_models = sum(
        1
        for provider in ai_providers
        if provider.status == "enabled"
        for model in provider.models
        if model.enabled
    )
    active_grants = sum(
        1
        for service in api_services
        for grant in service.grants
        if grant.status == "active"
    )
    expiring_grants = sum(
        1
        for service in api_services
        for grant in service.grants
        if grant.status == "active" and grant.expires_at is not None
    )

    return AdminCenterRead(
        organization_id=organization.id,
        organization_name=organization.name,
        organization_slug=organization.slug,
        members=members,
        integrations=integrations,
        ai_providers=ai_providers,
        api_services=api_services,
        summary=AdminCenterSummaryRead(
            member_count=len(members),
            integration_count=len(integrations),
            unhealthy_integration_count=unhealthy_integrations,
            ai_provider_count=len(ai_providers),
            enabled_ai_model_count=enabled_models,
            api_service_count=len(api_services),
            active_api_grant_count=active_grants,
            expiring_api_grant_count=expiring_grants,
        ),
    )
