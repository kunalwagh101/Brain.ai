import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from app.ai_usage import budget_snapshot, calendar_month_window, usage_summary
from app.ai_usage_models import AIBudgetPolicy, AIBudgetScopeType
from app.api_registry_models import (
    APICredentialGrant,
    APIGrantStatus,
    APIService,
    APIUsageObservation,
)
from app.decision_memory_models import MemoryKind, MemoryState
from app.models import MembershipRole
from app.project_status import ProjectMemory, ProjectStatusSnapshot, list_project_statuses
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
    provenance: MetricProvenance


@dataclass(frozen=True, slots=True)
class ExecutiveMemory:
    id: uuid.UUID
    kind: MemoryKind
    state: MemoryState
    summary: str
    confidence: float
    canonical_event_id: uuid.UUID
    search_document_id: uuid.UUID | None
    work_graph_node_id: uuid.UUID | None
    project_node_ids: tuple[uuid.UUID, ...]
    project_names: tuple[str, ...]
    provenance: MetricProvenance


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
    cost_provenance: MetricProvenance


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
    active_blockers: tuple[ExecutiveMemory, ...]
    confirmed_decisions: tuple[ExecutiveMemory, ...]
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
    # Aggregate metrics must not silently change because of an output page limit.
    # S-07.01 currently materializes the visible portfolio in-process, so consume all
    # visible projects here and let a future pagination layer be independent of counts.
    return tuple(
        list_project_statuses(
            db,
            organization_id=organization_id,
            user_id=user_id,
            role=role,
            limit=1_000_000_000,
        )
    )


def _project_metric_provenance(
    organization_id: uuid.UUID,
    project: ProjectStatusSnapshot,
) -> MetricProvenance:
    return MetricProvenance(
        metric_key=f"project_status:{project.project_node_id}",
        source_records=(
            "permission-filtered WorkGraph + ProjectProgressItem + "
            "DecisionMemoryCandidate + SearchDocument"
        ),
        calculation=(
            "reuse S-07.01 deterministic project status; percentage is weighted only "
            "from configured visible work items; blocked state requires confirmed blocker "
            "memory or an explicitly BLOCKED configured work item"
        ),
        source_count=(
            len(project.progress_items)
            + len(project.active_blockers)
            + len(project.confirmed_decisions)
            + len(project.evidence)
        ),
        drilldown_path=(
            f"/api/v1/organizations/{organization_id}/project-status/"
            f"{project.project_node_id}"
        ),
        complete=True,
    )


def _aggregate_memories(
    organization_id: uuid.UUID,
    projects: tuple[ProjectStatusSnapshot, ...],
    *,
    attribute: str,
) -> tuple[ExecutiveMemory, ...]:
    entries: dict[uuid.UUID, tuple[ProjectMemory, list[tuple[uuid.UUID, str]]]] = {}
    for project in projects:
        memories = getattr(project, attribute)
        for memory in memories:
            existing = entries.get(memory.id)
            if existing is None:
                entries[memory.id] = (
                    memory,
                    [(project.project_node_id, project.project_name)],
                )
            else:
                existing[1].append((project.project_node_id, project.project_name))

    result: list[ExecutiveMemory] = []
    for memory, links in entries.values():
        unique_links = sorted(set(links), key=lambda item: (item[1].casefold(), str(item[0])))
        result.append(
            ExecutiveMemory(
                id=memory.id,
                kind=memory.kind,
                state=memory.state,
                summary=memory.summary,
                confidence=memory.confidence,
                canonical_event_id=memory.canonical_event_id,
                search_document_id=memory.search_document_id,
                work_graph_node_id=memory.work_graph_node_id,
                project_node_ids=tuple(item[0] for item in unique_links),
                project_names=tuple(item[1] for item in unique_links),
                provenance=MetricProvenance(
                    metric_key=f"decision_memory:{memory.id}",
                    source_records="DecisionMemoryCandidate + authorised SearchDocument",
                    calculation=(
                        "surface only currently visible human-confirmed memory from S-04.02; "
                        "machine-only candidates never enter confirmed executive facts"
                    ),
                    source_count=1,
                    drilldown_path=(
                        f"/api/v1/organizations/{organization_id}/memory/{memory.id}"
                    ),
                    complete=True,
                ),
            )
        )
    result.sort(key=lambda item: (item.summary.casefold(), str(item.id)))
    return tuple(result)


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
            APICredentialGrant.organization_id == organization_id,
            APIService.organization_id == organization_id,
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
                or_(
                    APICredentialGrant.expires_at.is_(None),
                    APICredentialGrant.expires_at > end,
                ),
            )
        )
        or 0
    )
    usage_provenance = MetricProvenance(
        metric_key="external_api_usage_month_to_date",
        source_records="APIUsageObservation + APICredentialGrant + APIService",
        calculation="count trusted API usage observations by service in [period_start, period_end)",
        source_count=observations,
        period_start=start,
        period_end=end,
        drilldown_path=f"/api/v1/organizations/{organization_id}/api-registry/usage",
        complete=True,
    )
    cost_provenance = MetricProvenance(
        metric_key="external_api_spend_month_to_date",
        source_records="no external-API tariff/cost ledger exists in S-06.03",
        calculation=(
            "not calculated; Brain refuses to convert call counts into monetary spend without "
            "an explicit provider tariff and cost-allocation contract"
        ),
        source_count=0,
        period_start=start,
        period_end=end,
        drilldown_path=None,
        complete=False,
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
        provenance=usage_provenance,
        cost_provenance=cost_provenance,
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
            source_records="AIBudgetPolicy + computed calendar-month budget snapshot",
            calculation=(
                "known calendar-month spend divided by configured budget limit; unknown "
                "successful-request costs make enforcement incomplete"
            ),
            source_count=1,
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


def _normalise_time(at: datetime | None) -> datetime:
    if at is None:
        return datetime.now(UTC)
    if at.tzinfo is None:
        return at.replace(tzinfo=UTC)
    return at.astimezone(UTC)


def build_executive_overview(
    db: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    role: MembershipRole,
    at: datetime | None = None,
) -> ExecutiveOverview:
    generated_at = _normalise_time(at)
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
            provenance=_project_metric_provenance(organization_id, project),
        )
        for project in project_snapshots
    )
    active_blockers = _aggregate_memories(
        organization_id,
        project_snapshots,
        attribute="active_blockers",
    )
    confirmed_decisions = _aggregate_memories(
        organization_id,
        project_snapshots,
        attribute="confirmed_decisions",
    )

    portfolio_provenance = MetricProvenance(
        metric_key="visible_project_count_and_statuses",
        source_records="permission-filtered S-07.01 ProjectStatusSnapshot",
        calculation=(
            "count only projects visible through current Work Graph authorization and group "
            "their deterministic S-07.01 status"
        ),
        source_count=len(project_snapshots),
        drilldown_path=f"/api/v1/organizations/{organization_id}/project-status",
        complete=True,
    )
    blocker_provenance = MetricProvenance(
        metric_key="active_blocker_count",
        source_records="human-confirmed visible S-04.02 blocker memory",
        calculation="count unique confirmed blocker IDs across currently visible project evidence",
        source_count=len(active_blockers),
        drilldown_path=f"/api/v1/organizations/{organization_id}/memory?kind=blocker&state=confirmed",
        complete=True,
    )
    decision_provenance = MetricProvenance(
        metric_key="confirmed_decision_count",
        source_records="human-confirmed visible S-04.02 decision memory",
        calculation="count unique confirmed decision IDs across currently visible project evidence",
        source_count=len(confirmed_decisions),
        drilldown_path=f"/api/v1/organizations/{organization_id}/memory?kind=decision&state=confirmed",
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
                    message=(
                        f"{project.project_name} is blocked by confirmed memory or configured "
                        "work state"
                    ),
                    project_node_id=project.project_node_id,
                    budget_policy_id=None,
                    provenance=_project_metric_provenance(organization_id, project),
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
            message = (
                "AI budget enforcement is incomplete because some request costs are unknown"
            )
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
                message=(
                    "AI spend is incomplete because successful requests with unknown cost exist"
                ),
                project_node_id=None,
                budget_policy_id=None,
                provenance=ai_spend.provenance,
            )
        )
    if api_usage.observation_count > 0 and api_usage.cost_status == "not_modeled":
        risks.append(
            ExecutiveRisk(
                key="external_api_cost_not_modeled",
                severity="low",
                message=(
                    "External API monetary spend is unavailable because Brain has usage records "
                    "but no approved API tariff/cost model"
                ),
                project_node_id=None,
                budget_policy_id=None,
                provenance=api_usage.cost_provenance,
            )
        )

    return ExecutiveOverview(
        generated_at=generated_at,
        period_start=month_start,
        period_end=period_end,
        visible_project_count=len(project_snapshots),
        blocked_project_count=sum(project.status == "blocked" for project in project_snapshots),
        in_progress_project_count=sum(
            project.status == "in_progress" for project in project_snapshots
        ),
        done_project_count=sum(project.status == "done" for project in project_snapshots),
        unconfigured_project_count=sum(
            project.status == "unconfigured" for project in project_snapshots
        ),
        active_blocker_count=len(active_blockers),
        confirmed_decision_count=len(confirmed_decisions),
        portfolio=portfolio,
        active_blockers=active_blockers,
        confirmed_decisions=confirmed_decisions,
        ai_spend=ai_spend,
        api_usage=api_usage,
        budget_warnings=warnings,
        risks=tuple(risks),
        metric_provenance=(
            portfolio_provenance,
            blocker_provenance,
            decision_provenance,
            ai_spend.provenance,
            api_usage.provenance,
            api_usage.cost_provenance,
        ),
        employee_productivity_score=None,
    )
