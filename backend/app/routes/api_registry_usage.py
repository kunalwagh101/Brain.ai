import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai_usage import calendar_month_window
from app.api_registry_models import APICredentialGrant, APIService, APIUsageObservation
from app.database import get_db
from app.permissions import AuthorizationContext, Permission, require_organization_permission

router = APIRouter(
    prefix="/organizations/{organization_id}/api-registry",
    tags=["api-registry"],
)
_read = require_organization_permission(Permission.AUDIT_READ)


class OrganizationAPIUsageRead(BaseModel):
    id: uuid.UUID
    grant_id: uuid.UUID
    service_id: uuid.UUID
    service_key: str
    service_name: str
    provider_name: str
    caller_component: str
    operation_label: str | None
    success: bool
    latency_ms: int | None
    observed_at: datetime


@router.get("/usage", response_model=list[OrganizationAPIUsageRead])
def read_organization_api_usage(
    organization_id: uuid.UUID,
    authorization: Annotated[AuthorizationContext, Depends(_read)],
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[OrganizationAPIUsageRead]:
    del authorization
    now = datetime.now(UTC)
    period_start, period_end = calendar_month_window(now)
    rows = db.execute(
        select(APIUsageObservation, APICredentialGrant, APIService)
        .join(APICredentialGrant, APICredentialGrant.id == APIUsageObservation.grant_id)
        .join(APIService, APIService.id == APICredentialGrant.service_id)
        .where(
            APIUsageObservation.organization_id == organization_id,
            APICredentialGrant.organization_id == organization_id,
            APIService.organization_id == organization_id,
            APIUsageObservation.observed_at >= period_start,
            APIUsageObservation.observed_at < min(period_end, now),
        )
        .order_by(APIUsageObservation.observed_at.desc(), APIUsageObservation.id.desc())
        .limit(limit)
    ).all()
    return [
        OrganizationAPIUsageRead(
            id=observation.id,
            grant_id=grant.id,
            service_id=service.id,
            service_key=service.service_key,
            service_name=service.display_name,
            provider_name=service.provider_name,
            caller_component=observation.caller_component,
            operation_label=observation.operation_label,
            success=observation.success,
            latency_ms=observation.latency_ms,
            observed_at=observation.observed_at,
        )
        for observation, grant, service in rows
    ]
