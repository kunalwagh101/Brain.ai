import uuid
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai_usage import calendar_month_window
from app.ai_usage_models import AIBudgetScopeType
from app.api_registry_models import APICredentialGrant, APIService, APIUsageObservation
from app.database import get_db
from app.decision_memory_models import MemoryKind, MemoryState
from app.executive_overview import ExecutiveOverview, build_executive_overview
from app.permissions import AuthorizationContext, Permission, require_organization_permission

router = APIRouter(
    prefix="/organizations/{organization_id}/executive-overview",
    tags=["executive-overview"],
)
_read = require_organization_permission(Permission.AUDIT_READ)


class MetricProvenanceRead(BaseModel):
    metric_key: str
    source_records: str
    calculation: str
    source_count: int
    period_start: datetime | None
    period_end: datetime | None
    drilldown_path: str | None
    complete: bool


class ExecutiveProjectRead(BaseModel):
    project_node_id: uuid.UUID
    project_name: str
    status: str
    progress_percent: float | None
    progress_basis: str
    active_blocker_count: int
    confirmed_decision_count: int
    candidate_memory_count: int
    evidence_count: int
    provenance: MetricProvenanceRead


class ExecutiveMemoryRead(BaseModel):
    id: uuid.UUID
    kind: MemoryKind
    state: MemoryState
    summary: str
    confidence: float
    canonical_event_id: uuid.UUID
    search_document_id: uuid.UUID | None
    work_graph_node_id: uuid.UUID | None
    project_node_ids: list[uuid.UUID]
    project_names: list[str]
    provenance: MetricProvenanceRead


class AIProviderSpendRead(BaseModel):
    provider_configuration_id: uuid.UUID | None
    provider_key: str | None
    request_count: int
    succeeded_count: int
    failed_count: int
    known_cost_requests: int
    unknown_cost_requests: int
    input_tokens: int
    cached_input_tokens: int
    output_tokens: int
    known_spend_nano_usd: int


class AISpendSummaryRead(BaseModel):
    period_start: datetime
    period_end: datetime
    request_count: int
    succeeded_count: int
    failed_count: int
    known_cost_requests: int
    unknown_cost_requests: int
    input_tokens: int
    cached_input_tokens: int
    output_tokens: int
    known_spend_nano_usd: int
    cost_complete: bool
    by_provider: list[AIProviderSpendRead]
    provenance: MetricProvenanceRead


class APIServiceUsageRead(BaseModel):
    service_id: uuid.UUID
    service_key: str
    display_name: str
    provider_name: str
    observation_count: int
    succeeded_count: int
    failed_count: int


class APIUsageSummaryRead(BaseModel):
    period_start: datetime
    period_end: datetime
    observation_count: int
    succeeded_count: int
    failed_count: int
    active_grant_count: int
    known_spend_nano_usd: None
    cost_status: str
    by_service: list[APIServiceUsageRead]
    provenance: MetricProvenanceRead
    cost_provenance: MetricProvenanceRead


class APIUsageDrilldownRead(BaseModel):
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


class ExecutiveBudgetWarningRead(BaseModel):
    budget_policy_id: uuid.UUID
    scope_type: AIBudgetScopeType
    scope_target_id: uuid.UUID | None
    known_spend_nano_usd: int
    unknown_cost_requests: int
    limit_nano_usd: int
    warning_threshold_percent: int
    percent_used: float
    hard_limit: bool
    exhausted: bool
    enforcement_complete: bool
    warning_active: bool
    provenance: MetricProvenanceRead


class ExecutiveRiskRead(BaseModel):
    key: str
    severity: str
    message: str
    project_node_id: uuid.UUID | None
    budget_policy_id: uuid.UUID | None
    provenance: MetricProvenanceRead


class ExecutiveOverviewRead(BaseModel):
    generated_at: datetime
    period_start: datetime
    period_end: datetime
    visible_project_count: int
    blocked_project_count: int
    in_progress_project_count: int
    done_project_count: int
    unconfigured_project_count: int
    active_blocker_count: int
    confirmed_decision_count: int
    portfolio: list[ExecutiveProjectRead]
    active_blockers: list[ExecutiveMemoryRead]
    confirmed_decisions: list[ExecutiveMemoryRead]
    ai_spend: AISpendSummaryRead
    api_usage: APIUsageSummaryRead
    budget_warnings: list[ExecutiveBudgetWarningRead]
    risks: list[ExecutiveRiskRead]
    metric_provenance: list[MetricProvenanceRead]
    employee_productivity_score: None


@router.get("", response_model=ExecutiveOverviewRead)
def read_executive_overview(
    organization_id: uuid.UUID,
    authorization: Annotated[AuthorizationContext, Depends(_read)],
    db: Annotated[Session, Depends(get_db)],
) -> ExecutiveOverviewRead:
    overview: ExecutiveOverview = build_executive_overview(
        db,
        organization_id=organization_id,
        user_id=authorization.user_id,
        role=authorization.role,
    )
    return ExecutiveOverviewRead(**asdict(overview))


@router.get("/api-usage", response_model=list[APIUsageDrilldownRead])
def read_api_usage_drilldown(
    organization_id: uuid.UUID,
    authorization: Annotated[AuthorizationContext, Depends(_read)],
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[APIUsageDrilldownRead]:
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
        APIUsageDrilldownRead(
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
