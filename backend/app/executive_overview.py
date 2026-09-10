import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.ai_usage import budget_snapshot, calendar_month_window, usage_summary
from app.ai_usage_models import AIBudgetPolicy, AIBudgetScopeType
from app.api_registry_models import (
    APICredentialGrant,
    APIGrantStatus,
    APIService,
    APIUsageObservation,
)
from app.models import MembershipRole
from app.project_status import ProjectStatusSnapshot, list_project_statuses
from app.work_graph import node_visible_to_user
from app.work_graph_models import WorkGraphNode


@dataclass(frozen=True, slots=True)
class MetricProvenance:
    metric_key: str
    source_records: str
    calculation: str
    source_count: int
    period_start: datetime | None = None
    period_end: datetime | None = None
    drilldown_path: str | None = None
    complete: bool = True


@dataclass(frozen=True, slots=True)
class ExecutiveProject:
    project_node_id: uuid.UUID
    project_name: str
    status: str
    progress_percent: float | None
    progress_basis: str
    active_blocker_count: int
    confirmed_decision_count: int
    candidate_memory_count: int
    evidence_count: int


@dataclass(frozen=True, slots=True)
class AIProviderSpend:
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


@dataclass(frozen=True, slots=True)
class AISpendSummary:
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
    by_provider: tuple[AIProviderSpend, ...]
    provenance: MetricProvenance


@dataclass(frozen=True, slots=True)
class APIServiceUsage:
    service_id: uuid.UUID
    service_key: str
    display_name: str
    provider_name: str
    observation_count: int
    succeeded_count: int
    failed_count: int


@dataclass(frozen=True, slots=True)
class APIUsageSummary:
    period_start: datetime
    period_end: datetime
    observation_count: int
    succeeded_count: int
    failed_count: int
    active_grant_count: int
    known_spend_nano_usd: None
    cost_status: str
    by_service: tuple[APIServiceUsage, ...]
    provenance: MetricProvenance


@dataclass(frozen=True, slots=True)
class ExecutiveBudgetWarning:
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
    provenance: MetricProvenance


@dataclass(frozen=True, slots=True)
class ExecutiveRisk:
    key: str
    severity: str
    message: str
    project_node_id: uuid.UUID | None
    budget_policy_id: uuid.UUID | None
    provenance: MetricProvenance


@dataclass(frozen=True, slots=True)
class ExecutiveOverview:
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
    portfolio: tuple[ExecutiveProject, ...]
    ai_spend: AISpendSummary
    api_usage: APIUsageSummary
    budget_warnings: tuple[ExecutiveBudgetWarning, ...]
    risks: tuple[ExecutiveRisk, ...]
    metric_provenance: tuple[MetricProvenance, ...]
    employee_productivity_score: None


def _portfolio(
    db: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    role: MembershipRole,
) -> tuple[ProjectStatusSnapshot, ...]:
    # Correctness is more important than silently truncating aggregate metrics.
    # The API response may later paginate the rendered portfolio independently,
    # but all executive counts are calculated from every currently visible project.
    return tuple(
        list_project_statuses(
            db,
            organization_id=organization_id,
            user_id=user_id,
            role=role,
            limit=1_000_000_000,
        )
    )


def _ai_spend(
    db: Session,
    *,
    organization_id: uuid.UUID,
    start: datetime,
    end: datetime,
) -> AISpendSummary:
    org_rows = usage_summary(
        db,
        organization_id=organization_id,
        start=start,
        end=end,
        dimension="organization",
    )
    row = org_rows[0] if org_rows else None
    provider_rows = usage_summary(
        db,
        organization_id=organization_id,
        start=start,
        end=end,
        dimension="provider",
    )
    providers: list[AIProviderSpend] = []
    for provider in provider_rows:
        provider_id: uuid.UUID | None = None
        if provider.dimension_id is not None:
            try:
                provider_id = uuid.UUID(provider.dimension_id)
            except ValueError:
                provider_id = None
        providers.append(
            AIProviderSpend(
                provider_configuration_id=provider_id,
                provider_key=provider.dimension_label,
                request_count=provider.request_count,
                succeeded_count=provider.succeeded_count,
                failed_count=provider.failed_count,
                known_cost_requests=provider.known_cost_requests,
                unknown_cost_requests=provider.unknown_cost_requests,
                input_tokens=provider.input_tokens,
                cached_input_tokens=provider.cached_input_tokens,
                output_tokens=provider.output_tokens,
                known_spend_nano_usd=provider.total_cost_nano_usd,
            )
        )
    providers.sort(key=lambda item: (-item.known_spend_nano_usd, item.provider_key or ""))

    request_count = row.request_count if row else 0
    succeeded_count = row.succeeded_count if row else 0
    failed_count = row.failed_count if row else 0
    known_cost_requests = row.known_cost_requests if row else 0
    unknown_cost_requests = row.unknown_cost_requests if row else 0
    input_tokens = row.input_tokens if row else 0
    cached_input_tokens = row.cached_input_tokens if row else 0
    output_tokens = row.output_tokens if row else 0
    spend = row.total_cost_nano_usd if row else 0
    provenance = MetricProvenance(
        metric_key="ai_spend_month_to_date",
        source_records="AIRequestRecord + AIUsageCostRecord",
        calculation=(
            "sum calculated request costs for this organisation in [period_start, period_end); "
            "unknown-cost successful requests remain separately counted"
        ),
        source_count=request_count,
        period_start=start,
        period_end=end,
        drilldown_path=(
            f"/api/v1/organizations/{organization_id}/ai/usage/summary?dimension=provider"
        ),
        complete=unknown_cost_requests == 0,
    )
    return AISpendSummary(
        period_start=start,
        period_end=end,
        request_count=request_count,
        succeeded_count=succeeded_count,
        failed_count=failed_count,
        known_cost_requests=known_cost_requests,
        unknown_cost_requests=unknown_cost_requests,
        input_tokens=input_tokens,
        cached_input_tokens=cached_input_tokens,
        output_tokens=output_tokens,
        known_spend_nano_usd=spend,
        cost_complete=unknown_cost_requests == 0,
        by_provider=tuple(providers),
        provenance=provenance,
    )


def _api_usage(
    db: Session,
    *,
    organization_id: uuid.UUID,
    start: datetime,
    end: datetime,
) -> APIUsageSummary:
    rows = db.execute(
        select(
            APIService.id.label("service_id"),
            APIService.service_key.label("service_key"),
            APIService.display_name.label("display_name"),
            APIService.provider_name.label("provider_name"),
            func.count(APIUsageObservation.id).label("observation_count"),
            func.sum(case((APIUsageObservation.success.is_(True), 1), else_=0)).label(
                "succeeded_count"
            ),
            func.sum(case((APIUsageObservation.success.is_(False), 1), else_=0)).label(
                "failed_count"
            ),
        )
        .select_from(APIUsageObservation)
        .join(APICredentialGrant, APICredentialGrant.id == APIUsageObservation.grant_id)
        .join(APIService, APIService.id == APICredentialGrant.service_id)
        .where(
            APIUsageObservation.organization_id == organization_id,
            APIUsageObservation.observed_at >= start,
            APIUsageObservation.observed_at < end,
        )
        .group_by(
            APIService.id,
            APIService.service_key,
            APIService.display_name,
            APIService.provider_name,
        )
        .order_by(func.count(APIUsageObservation.id).desc(), APIService.service_key)
    ).all()
    services = tuple(
        APIServiceUsage(
            service_id=row.service_id,
            service_key=row.service_key,
            display_name=row.display_name,
            provider_name=row.provider_name,
            observation_count=int(row.observation_count or 0),
            succeeded_count=int(row.succeeded_count or 0),
            failed_count=int(row.failed_count or 0),
        )
        for row in rows
    )
    observations = sum(item.observation_count for item in services)
    succeeded = sum(item.succeeded_count for item in services)
    failed = sum(item.failed_count for item in services)
    active_grants = int(
        db.scalar(
            select(func.count(APICredentialGrant.id)).where(
                APICredentialGrant.organization_id == organization_id,
                APICredentialGrant.status == APIGrantStatus.ACTIVE,
            )
        )
        or 0
    )
    provenance = MetricProvenance(
        metric_key="external_api_usage_month_to_date",
        source_records="APIUsageObservation + APICredentialGrant + APIService",
        calculation=(
            "count trusted API usage observations by service in [period_start, period_end); "
            "monetary API cost is intentionally unavailable because no tariff model exists"
        ),
        source_count=observations,
        period_start=start,
        period_end=end,
        drilldown_path=f"/api/v1/organizations/{organization_id}/api-registry/usage",
        complete=True,
    )
    return APIUsageSummary(
        period_start=start,
        period_end=end,
        observation_count=observations,
        succeeded_count=succeeded,
        failed_count=failed,
        active_grant_count=active_grants,
        known_spend_nano_usd=None,
        cost_status="not_modeled",
        by_service=services,
        provenance=provenance,
    )


def _budget_is_visible(
    db: Session,
    *,
    policy: AIBudgetPolicy,
    user_id: uuid.UUID,
    role: MembershipRole,
) -> bool:
    if policy.scope_type != AIBudgetScopeType.WORK_GRAPH_NODE:
        return True
    if policy.scope_target_id is None:
        return False
    node = db.scalar(
        select(WorkGraphNode).where(
            WorkGraphNode.id == policy.scope_target_id,
            WorkGraphNode.organization_id == policy.organization_id,
        )
    )
    if node is None:
        return False
    return node_visible_to_user(db, node, user_id=user_id, role=role)


def _budget_warnings(
    db: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    role: MembershipRole,
    at: datetime,
) -> tuple[ExecutiveBudgetWarning, ...]:
    policies = list(
        db.scalars(
            select(AIBudgetPolicy)
            .where(
                AIBudgetPolicy.organization_id == organization_id,
                AIBudgetPolicy.enabled.is_(True),
            )
            .order_by(AIBudgetPolicy.created_at, AIBudgetPolicy.id)
        )
    )
    warnings: list[ExecutiveBudgetWarning] = []
    for policy in policies:
        if not _budget_is_visible(db, policy=policy, user_id=user_id, role=role):
            continue
        snapshot = budget_snapshot(db, policy=policy, at=at)
        percent_used = round(
            (snapshot.known_spend_nano_usd / snapshot.limit_nano_usd) * 100.0,
            2,
        )
        warning_active = percent_used >= snapshot.warning_threshold_percent
        if not warning_active and snapshot.enforcement_complete:
            continue
        provenance = MetricProvenance(
            metric_key=f"ai_budget:{policy.id}",
            source_records="AIBudgetPolicy + AIRequestRecord + AIUsageCostRecord",
            calculation=(
                "calendar-month known spend divided by configured budget limit; "
                "unknown successful-request costs make enforcement incomplete"
            ),
            source_count=snapshot.unknown_cost_requests,
            period_start=snapshot.period_start,
            period_end=snapshot.period_end,
            drilldown_path=(
                f"/api/v1/organizations/{organization_id}/ai/budgets/{policy.id}/snapshot"
            ),
            complete=snapshot.enforcement_complete,
        )
        warnings.append(
            ExecutiveBudgetWarning(
                budget_policy_id=policy.id,
                scope_type=policy.scope_type,
                scope_target_id=policy.scope_target_id,
                known_spend_nano_usd=snapshot.known_spend_nano_usd,
                unknown_cost_requests=snapshot.unknown_cost_requests,
                limit_nano_usd=snapshot.limit_nano_usd,
                warning_threshold_percent=snapshot.warning_threshold_percent,
                percent_used=percent_used,
                hard_limit=snapshot.hard_limit,
                exhausted=snapshot.exhausted,
                enforcement_complete=snapshot.enforcement_complete,
                warning_active=warning_active,
                provenance=provenance,
            )
        )
    warnings.sort(
        key=lambda item: (
            not item.exhausted,
            not item.warning_active,
            -item.percent_used,
            str(item.budget_policy_id),
        )
    )
    return tuple(warnings)


def build_executive_overview(
    db: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    role: MembershipRole,
    at: datetime | None = None,
) -> ExecutiveOverview:
    generated_at = at.astimezone(UTC) if at and at.tzinfo else (at.replace(tzinfo=UTC) if at else datetime.now(UTC))
    month_start, month_end = calendar_month_window(generated_at)
    period_end = min(month_end, generated_at)

    project_snapshots = _portfolio(
        db,
        organization_id=organization_id,
        user_id=user_id,
        role=role,
    )
    portfolio = tuple(
        ExecutiveProject(
            project_node_id=project.project_node_id,
            project_name=project.project_name,
            status=project.status,
            progress_percent=project.progress_percent,
            progress_basis=project.progress_basis,
            active_blocker_count=len(project.active_blockers),
            confirmed_decision_count=len(project.confirmed_decisions),
            candidate_memory_count=len(project.candidate_memories),
            evidence_count=len(project.evidence),
        )
        for project in project_snapshots
    )
    unique_blockers = {
        blocker.id for project in project_snapshots for blocker in project.active_blockers
    }
    unique_decisions = {
        decision.id for project in project_snapshots for decision in project.confirmed_decisions
    }
    project_provenance = MetricProvenance(
        metric_key="visible_project_portfolio",
        source_records="permission-filtered WorkGraph + ProjectProgressItem + DecisionMemoryCandidate + SearchDocument",
        calculation=(
            "build S-07.01 status for every project visible to the authenticated user; "
            "counts use unique confirmed memory IDs across visible projects"
        ),
        source_count=len(project_snapshots),
        drilldown_path=f"/api/v1/organizations/{organization_id}/project-status",
        complete=True,
    )
    ai_spend = _ai_spend(
        db,
        organization_id=organization_id,
        start=month_start,
        end=period_end,
    )
    api_usage = _api_usage(
        db,
        organization_id=organization_id,
        start=month_start,
        end=period_end,
    )
    warnings = _budget_warnings(
        db,
        organization_id=organization_id,
        user_id=user_id,
        role=role,
        at=generated_at,
    )

    risks: list[ExecutiveRisk] = []
    for project in project_snapshots:
        if project.status == "blocked":
            risks.append(
                ExecutiveRisk(
                    key=f"project_blocked:{project.project_node_id}",
                    severity="high",
                    message=f"{project.project_name} is blocked by confirmed memory or configured work state",
                    project_node_id=project.project_node_id,
                    budget_policy_id=None,
                    provenance=MetricProvenance(
                        metric_key=f"project_status:{project.project_node_id}",
                        source_records="S-07.01 ProjectStatusSnapshot",
                        calculation="blocked only from confirmed blockers or explicitly BLOCKED configured work items",
                        source_count=len(project.active_blockers) + len(project.progress_items),
                        drilldown_path=(
                            f"/api/v1/organizations/{organization_id}/project-status/{project.project_node_id}"
                        ),
                        complete=True,
                    ),
                )
            )
    for warning in warnings:
        if warning.exhausted:
            severity = "high"
            message = "AI budget is exhausted"
        elif warning.warning_active:
            severity = "medium"
            message = "AI budget warning threshold is reached"
        else:
            severity = "medium"
            message = "AI budget enforcement is incomplete because some request costs are unknown"
        risks.append(
            ExecutiveRisk(
                key=f"budget:{warning.budget_policy_id}",
                severity=severity,
                message=message,
                project_node_id=(
                    warning.scope_target_id
                    if warning.scope_type == AIBudgetScopeType.WORK_GRAPH_NODE
                    else None
                ),
                budget_policy_id=warning.budget_policy_id,
                provenance=warning.provenance,
            )
        )
    if not ai_spend.cost_complete:
        risks.append(
            ExecutiveRisk(
                key="ai_cost_incomplete",
                severity="medium",
                message="AI spend is incomplete because successful requests with unknown cost exist",
                project_node_id=None,
                budget_policy_id=None,
                provenance=ai_spend.provenance,
            )
        )

    return ExecutiveOverview(
        generated_at=generated_at,
        period_start=month_start,
        period_end=period_end,
        visible_project_count=len(project_snapshots),
        blocked_project_count=sum(project.status == "blocked" for project in project_snapshots),
        in_progress_project_count=sum(project.status == "in_progress" for project in project_snapshots),
        done_project_count=sum(project.status == "done" for project in project_snapshots),
        unconfigured_project_count=sum(project.status == "unconfigured" for project in project_snapshots),
        active_blocker_count=len(unique_blockers),
        confirmed_decision_count=len(unique_decisions),
        portfolio=portfolio,
        ai_spend=ai_spend,
        api_usage=api_usage,
        budget_warnings=warnings,
        risks=tuple(risks),
        metric_provenance=(project_provenance, ai_spend.provenance, api_usage.provenance),
        employee_productivity_score=None,
    )
