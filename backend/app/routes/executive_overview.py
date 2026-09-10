from dataclasses import asdict
from datetime import datetime
from typing import Annotated
import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.ai_usage_models import AIBudgetScopeType
from app.database import get_db
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
