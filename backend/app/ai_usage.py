import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import case, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.ai_gateway_models import (
    AIModelConfiguration,
    AIProviderConfiguration,
    AIRequestRecord,
    AIRequestStatus,
)
from app.ai_usage_models import (
    AIBudgetAlert,
    AIBudgetPeriod,
    AIBudgetPolicy,
    AIBudgetScopeType,
    AICostResolutionStatus,
    AIModelRateCard,
    AIUsageCostRecord,
)
from app.models import Membership
from app.work_graph_models import WorkGraphNode, WorkGraphNodeType


class AIUsageError(ValueError):
    """Raised when usage/cost/budget configuration is invalid."""


@dataclass(frozen=True, slots=True)
class BudgetSnapshot:
    budget_policy_id: uuid.UUID
    period_start: datetime
    period_end: datetime
    known_spend_nano_usd: int
    unknown_cost_requests: int
    limit_nano_usd: int
    warning_threshold_percent: int
    hard_limit: bool
    exhausted: bool
    enforcement_complete: bool


@dataclass(frozen=True, slots=True)
class UsageSummaryRow:
    dimension: str
    dimension_id: str | None
    dimension_label: str | None
    request_count: int
    succeeded_count: int
    failed_count: int
    known_cost_requests: int
    unknown_cost_requests: int
    input_tokens: int
    output_tokens: int
    total_cost_nano_usd: int


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def calendar_month_window(at: datetime) -> tuple[datetime, datetime]:
    at = _utc(at)
    start = datetime(at.year, at.month, 1, tzinfo=UTC)
    if at.month == 12:
        end = datetime(at.year + 1, 1, 1, tzinfo=UTC)
    else:
        end = datetime(at.year, at.month + 1, 1, tzinfo=UTC)
    return start, end


def create_model_rate_card(
    db: Session,
    *,
    organization_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    provider_configuration_id: uuid.UUID,
    model_configuration_id: uuid.UUID,
    input_nano_usd_per_token: int,
    output_nano_usd_per_token: int,
    source_label: str,
    effective_from: datetime,
    effective_to: datetime | None,
) -> AIModelRateCard:
    provider = db.scalar(
        select(AIProviderConfiguration).where(
            AIProviderConfiguration.id == provider_configuration_id,
            AIProviderConfiguration.organization_id == organization_id,
        )
    )
    model = db.scalar(
        select(AIModelConfiguration).where(
            AIModelConfiguration.id == model_configuration_id,
            AIModelConfiguration.organization_id == organization_id,
            AIModelConfiguration.provider_configuration_id == provider_configuration_id,
        )
    )
    if provider is None or model is None:
        raise AIUsageError("AI provider or model not found")
    if input_nano_usd_per_token < 0 or output_nano_usd_per_token < 0:
        raise AIUsageError("AI model rates must be non-negative")
    label = " ".join(source_label.strip().split())[:255]
    if not label:
        raise AIUsageError("Rate-card source label is required")

    start = _utc(effective_from)
    end = _utc(effective_to) if effective_to is not None else None
    if end is not None and end <= start:
        raise AIUsageError("Rate-card effective_to must be after effective_from")

    overlap = select(AIModelRateCard.id).where(
        AIModelRateCard.organization_id == organization_id,
        AIModelRateCard.model_configuration_id == model_configuration_id,
        or_(
            AIModelRateCard.effective_to.is_(None),
            AIModelRateCard.effective_to > start,
        ),
    )
    if end is not None:
        overlap = overlap.where(AIModelRateCard.effective_from < end)
    existing = db.scalar(overlap.limit(1))
    if existing is not None:
        raise AIUsageError("AI model rate-card window overlaps an existing rate")

    rate = AIModelRateCard(
        organization_id=organization_id,
        provider_configuration_id=provider_configuration_id,
        model_configuration_id=model_configuration_id,
        input_nano_usd_per_token=input_nano_usd_per_token,
        output_nano_usd_per_token=output_nano_usd_per_token,
        source_label=label,
        effective_from=start,
        effective_to=end,
        created_by_user_id=actor_user_id,
    )
    db.add(rate)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise AIUsageError("AI model rate card already exists") from exc
    db.refresh(rate)
    return rate


def _effective_rate_card(db: Session, request: AIRequestRecord) -> AIModelRateCard | None:
    occurred_at = _utc(request.created_at)
    return db.scalar(
        select(AIModelRateCard)
        .where(
            AIModelRateCard.organization_id == request.organization_id,
            AIModelRateCard.provider_configuration_id
            == request.provider_configuration_id,
            AIModelRateCard.model_configuration_id == request.model_configuration_id,
            AIModelRateCard.effective_from <= occurred_at,
            or_(
                AIModelRateCard.effective_to.is_(None),
                AIModelRateCard.effective_to > occurred_at,
            ),
        )
        .order_by(AIModelRateCard.effective_from.desc())
        .limit(1)
    )


def materialize_request_cost(
    db: Session,
    *,
    request: AIRequestRecord,
) -> AIUsageCostRecord:
    if request.status != AIRequestStatus.SUCCEEDED:
        raise AIUsageError("Only successful AI requests can be cost-resolved")
    existing = db.scalar(
        select(AIUsageCostRecord).where(AIUsageCostRecord.request_id == request.id)
    )
    if existing is not None:
        return existing

    rate = _effective_rate_card(db, request)
    if request.input_tokens is None or request.output_tokens is None:
        cost = AIUsageCostRecord(
            organization_id=request.organization_id,
            request_id=request.id,
            rate_card_id=rate.id if rate is not None else None,
            status=AICostResolutionStatus.UNKNOWN,
            unknown_reason="token_usage_unavailable",
        )
    elif rate is None:
        cost = AIUsageCostRecord(
            organization_id=request.organization_id,
            request_id=request.id,
            rate_card_id=None,
            status=AICostResolutionStatus.UNKNOWN,
            unknown_reason="rate_card_unavailable",
        )
    else:
        input_cost = request.input_tokens * rate.input_nano_usd_per_token
        output_cost = request.output_tokens * rate.output_nano_usd_per_token
        cost = AIUsageCostRecord(
            organization_id=request.organization_id,
            request_id=request.id,
            rate_card_id=rate.id,
            status=AICostResolutionStatus.CALCULATED,
            unknown_reason=None,
            input_cost_nano_usd=input_cost,
            output_cost_nano_usd=output_cost,
            total_cost_nano_usd=input_cost + output_cost,
        )
    db.add(cost)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        concurrent = db.scalar(
            select(AIUsageCostRecord).where(AIUsageCostRecord.request_id == request.id)
        )
        if concurrent is None:
            raise
        return concurrent
    db.refresh(cost)
    evaluate_budget_alerts_for_request(db, request=request)
    return cost


def _validate_budget_scope(
    db: Session,
    *,
    organization_id: uuid.UUID,
    scope_type: AIBudgetScopeType,
    scope_target_id: uuid.UUID | None,
) -> tuple[str, uuid.UUID | None]:
    if scope_type == AIBudgetScopeType.ORGANIZATION:
        if scope_target_id is not None:
            raise AIUsageError("Organization budget must not have a scope target")
        return "organization", None
    if scope_target_id is None:
        raise AIUsageError("Budget scope target is required")

    if scope_type == AIBudgetScopeType.PROVIDER:
        exists = db.scalar(
            select(AIProviderConfiguration.id).where(
                AIProviderConfiguration.id == scope_target_id,
                AIProviderConfiguration.organization_id == organization_id,
            )
        )
    elif scope_type == AIBudgetScopeType.MODEL:
        exists = db.scalar(
            select(AIModelConfiguration.id).where(
                AIModelConfiguration.id == scope_target_id,
                AIModelConfiguration.organization_id == organization_id,
            )
        )
    elif scope_type == AIBudgetScopeType.USER:
        exists = db.scalar(
            select(Membership.user_id).where(
                Membership.organization_id == organization_id,
                Membership.user_id == scope_target_id,
            )
        )
    elif scope_type == AIBudgetScopeType.WORK_GRAPH_NODE:
        exists = db.scalar(
            select(WorkGraphNode.id).where(
                WorkGraphNode.id == scope_target_id,
                WorkGraphNode.organization_id == organization_id,
                WorkGraphNode.node_type.in_(
                    (
                        WorkGraphNodeType.PROJECT,
                        WorkGraphNodeType.TRACK,
                        WorkGraphNodeType.WORK_ITEM,
                    )
                ),
            )
        )
    else:
        raise AIUsageError("Unsupported budget scope")
    if exists is None:
        raise AIUsageError("Budget scope target not found")
    return str(scope_target_id), scope_target_id


def create_budget_policy(
    db: Session,
    *,
    organization_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    scope_type: AIBudgetScopeType,
    scope_target_id: uuid.UUID | None,
    limit_nano_usd: int,
    warning_threshold_percent: int,
    hard_limit: bool,
    enabled: bool,
) -> AIBudgetPolicy:
    if limit_nano_usd <= 0:
        raise AIUsageError("Budget limit must be positive")
    if not 1 <= warning_threshold_percent <= 100:
        raise AIUsageError("Budget warning threshold must be between 1 and 100")
    scope_key, target_id = _validate_budget_scope(
        db,
        organization_id=organization_id,
        scope_type=scope_type,
        scope_target_id=scope_target_id,
    )
    duplicate = db.scalar(
        select(AIBudgetPolicy.id).where(
            AIBudgetPolicy.organization_id == organization_id,
            AIBudgetPolicy.scope_type == scope_type,
            AIBudgetPolicy.scope_key == scope_key,
            AIBudgetPolicy.period == AIBudgetPeriod.CALENDAR_MONTH,
        )
    )
    if duplicate is not None:
        raise AIUsageError("Budget policy already exists for this scope")

    policy = AIBudgetPolicy(
        organization_id=organization_id,
        scope_type=scope_type,
        scope_key=scope_key,
        scope_target_id=target_id,
        period=AIBudgetPeriod.CALENDAR_MONTH,
        limit_nano_usd=limit_nano_usd,
        warning_threshold_percent=warning_threshold_percent,
        hard_limit=hard_limit,
        enabled=enabled,
        created_by_user_id=actor_user_id,
    )
    db.add(policy)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise AIUsageError("Budget policy already exists for this scope") from exc
    db.refresh(policy)
    return policy


def set_budget_enabled(
    db: Session,
    *,
    organization_id: uuid.UUID,
    budget_policy_id: uuid.UUID,
    enabled: bool,
) -> AIBudgetPolicy:
    policy = db.scalar(
        select(AIBudgetPolicy).where(
            AIBudgetPolicy.id == budget_policy_id,
            AIBudgetPolicy.organization_id == organization_id,
        )
    )
    if policy is None:
        raise AIUsageError("Budget policy not found")
    policy.enabled = enabled
    db.commit()
    db.refresh(policy)
    return policy


def _scope_request_query(query, policy: AIBudgetPolicy):
    if policy.scope_type == AIBudgetScopeType.ORGANIZATION:
        return query
    target = policy.scope_target_id
    if policy.scope_type == AIBudgetScopeType.PROVIDER:
        return query.where(AIRequestRecord.provider_configuration_id == target)
    if policy.scope_type == AIBudgetScopeType.MODEL:
        return query.where(AIRequestRecord.model_configuration_id == target)
    if policy.scope_type == AIBudgetScopeType.USER:
        return query.where(AIRequestRecord.user_id == target)
    if policy.scope_type == AIBudgetScopeType.WORK_GRAPH_NODE:
        return query.where(AIRequestRecord.attribution_node_id == target)
    raise AIUsageError("Unsupported budget scope")


def budget_snapshot(
    db: Session,
    *,
    policy: AIBudgetPolicy,
    at: datetime,
) -> BudgetSnapshot:
    start, end = calendar_month_window(at)
    spend_query = (
        select(func.coalesce(func.sum(AIUsageCostRecord.total_cost_nano_usd), 0))
        .select_from(AIRequestRecord)
        .join(AIUsageCostRecord, AIUsageCostRecord.request_id == AIRequestRecord.id)
        .where(
            AIRequestRecord.organization_id == policy.organization_id,
            AIRequestRecord.status == AIRequestStatus.SUCCEEDED,
            AIRequestRecord.created_at >= start,
            AIRequestRecord.created_at < end,
            AIUsageCostRecord.status == AICostResolutionStatus.CALCULATED,
        )
    )
    spend_query = _scope_request_query(spend_query, policy)
    known_spend = int(db.scalar(spend_query) or 0)

    unknown_query = (
        select(func.count(AIRequestRecord.id))
        .select_from(AIRequestRecord)
        .outerjoin(AIUsageCostRecord, AIUsageCostRecord.request_id == AIRequestRecord.id)
        .where(
            AIRequestRecord.organization_id == policy.organization_id,
            AIRequestRecord.status == AIRequestStatus.SUCCEEDED,
            AIRequestRecord.created_at >= start,
            AIRequestRecord.created_at < end,
            or_(
                AIUsageCostRecord.id.is_(None),
                AIUsageCostRecord.status == AICostResolutionStatus.UNKNOWN,
            ),
        )
    )
    unknown_query = _scope_request_query(unknown_query, policy)
    unknown = int(db.scalar(unknown_query) or 0)
    return BudgetSnapshot(
        budget_policy_id=policy.id,
        period_start=start,
        period_end=end,
        known_spend_nano_usd=known_spend,
        unknown_cost_requests=unknown,
        limit_nano_usd=policy.limit_nano_usd,
        warning_threshold_percent=policy.warning_threshold_percent,
        hard_limit=policy.hard_limit,
        exhausted=known_spend >= policy.limit_nano_usd,
        enforcement_complete=unknown == 0,
    )


def _policy_matches_request_dimensions(
    policy: AIBudgetPolicy,
    *,
    provider_configuration_id: uuid.UUID,
    model_configuration_id: uuid.UUID,
    user_id: uuid.UUID,
    attribution_node_id: uuid.UUID | None,
) -> bool:
    if policy.scope_type == AIBudgetScopeType.ORGANIZATION:
        return True
    if policy.scope_type == AIBudgetScopeType.PROVIDER:
        return policy.scope_target_id == provider_configuration_id
    if policy.scope_type == AIBudgetScopeType.MODEL:
        return policy.scope_target_id == model_configuration_id
    if policy.scope_type == AIBudgetScopeType.USER:
        return policy.scope_target_id == user_id
    if policy.scope_type == AIBudgetScopeType.WORK_GRAPH_NODE:
        return policy.scope_target_id == attribution_node_id
    return False


def matching_budget_policies(
    db: Session,
    *,
    organization_id: uuid.UUID,
    provider_configuration_id: uuid.UUID,
    model_configuration_id: uuid.UUID,
    user_id: uuid.UUID,
    attribution_node_id: uuid.UUID | None,
) -> list[AIBudgetPolicy]:
    policies = list(
        db.scalars(
            select(AIBudgetPolicy).where(
                AIBudgetPolicy.organization_id == organization_id,
                AIBudgetPolicy.enabled.is_(True),
            )
        )
    )
    return [
        policy
        for policy in policies
        if _policy_matches_request_dimensions(
            policy,
            provider_configuration_id=provider_configuration_id,
            model_configuration_id=model_configuration_id,
            user_id=user_id,
            attribution_node_id=attribution_node_id,
        )
    ]


def exhausted_hard_budget(
    db: Session,
    *,
    organization_id: uuid.UUID,
    provider_configuration_id: uuid.UUID,
    model_configuration_id: uuid.UUID,
    user_id: uuid.UUID,
    attribution_node_id: uuid.UUID | None,
    at: datetime,
) -> BudgetSnapshot | None:
    for policy in matching_budget_policies(
        db,
        organization_id=organization_id,
        provider_configuration_id=provider_configuration_id,
        model_configuration_id=model_configuration_id,
        user_id=user_id,
        attribution_node_id=attribution_node_id,
    ):
        if not policy.hard_limit:
            continue
        snapshot = budget_snapshot(db, policy=policy, at=at)
        if snapshot.exhausted:
            return snapshot
    return None


def _create_alert_if_absent(
    db: Session,
    *,
    policy: AIBudgetPolicy,
    snapshot: BudgetSnapshot,
    threshold_percent: int,
) -> bool:
    period_start = snapshot.period_start.date()
    existing = db.scalar(
        select(AIBudgetAlert.id).where(
            AIBudgetAlert.budget_policy_id == policy.id,
            AIBudgetAlert.period_start == period_start,
            AIBudgetAlert.threshold_percent == threshold_percent,
        )
    )
    if existing is not None:
        return False
    alert = AIBudgetAlert(
        organization_id=policy.organization_id,
        budget_policy_id=policy.id,
        period_start=period_start,
        threshold_percent=threshold_percent,
        spend_nano_usd=snapshot.known_spend_nano_usd,
    )
    db.add(alert)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return False
    return True


def evaluate_budget_alerts_for_request(
    db: Session,
    *,
    request: AIRequestRecord,
) -> int:
    created = 0
    for policy in matching_budget_policies(
        db,
        organization_id=request.organization_id,
        provider_configuration_id=request.provider_configuration_id,
        model_configuration_id=request.model_configuration_id,
        user_id=request.user_id,
        attribution_node_id=request.attribution_node_id,
    ):
        snapshot = budget_snapshot(db, policy=policy, at=_utc(request.created_at))
        thresholds = {policy.warning_threshold_percent, 100}
        for threshold in sorted(thresholds):
            if (
                snapshot.known_spend_nano_usd * 100
                >= snapshot.limit_nano_usd * threshold
            ):
                created += int(
                    _create_alert_if_absent(
                        db,
                        policy=policy,
                        snapshot=snapshot,
                        threshold_percent=threshold,
                    )
                )
    return created


def usage_summary(
    db: Session,
    *,
    organization_id: uuid.UUID,
    start: datetime,
    end: datetime,
    dimension: str,
) -> list[UsageSummaryRow]:
    start = _utc(start)
    end = _utc(end)
    if end <= start:
        raise AIUsageError("Usage end must be after start")
    if dimension == "organization":
        id_column = AIRequestRecord.organization_id
        label_column = None
    elif dimension == "provider":
        id_column = AIRequestRecord.provider_configuration_id
        label_column = AIRequestRecord.provider_key
    elif dimension == "model":
        id_column = AIRequestRecord.model_configuration_id
        label_column = AIRequestRecord.model_key
    elif dimension == "user":
        id_column = AIRequestRecord.user_id
        label_column = None
    elif dimension == "work_graph_node":
        id_column = AIRequestRecord.attribution_node_id
        label_column = AIRequestRecord.attribution_node_type
    else:
        raise AIUsageError("Unsupported usage dimension")

    selected = [
        id_column.label("dimension_id"),
        func.count(AIRequestRecord.id).label("request_count"),
        func.sum(
            case((AIRequestRecord.status == AIRequestStatus.SUCCEEDED, 1), else_=0)
        ).label("succeeded_count"),
        func.sum(
            case((AIRequestRecord.status == AIRequestStatus.FAILED, 1), else_=0)
        ).label("failed_count"),
        func.sum(
            case(
                (
                    AIUsageCostRecord.status == AICostResolutionStatus.CALCULATED,
                    1,
                ),
                else_=0,
            )
        ).label("known_cost_requests"),
        func.sum(
            case(
                (
                    AIRequestRecord.status == AIRequestStatus.SUCCEEDED,
                    case(
                        (
                            or_(
                                AIUsageCostRecord.id.is_(None),
                                AIUsageCostRecord.status
                                == AICostResolutionStatus.UNKNOWN,
                            ),
                            1,
                        ),
                        else_=0,
                    ),
                ),
                else_=0,
            )
        ).label("unknown_cost_requests"),
        func.coalesce(func.sum(AIRequestRecord.input_tokens), 0).label("input_tokens"),
        func.coalesce(func.sum(AIRequestRecord.output_tokens), 0).label("output_tokens"),
        func.coalesce(func.sum(AIUsageCostRecord.total_cost_nano_usd), 0).label(
            "total_cost_nano_usd"
        ),
    ]
    group_columns = [id_column]
    if label_column is not None:
        selected.insert(1, label_column.label("dimension_label"))
        group_columns.append(label_column)

    query = (
        select(*selected)
        .select_from(AIRequestRecord)
        .outerjoin(AIUsageCostRecord, AIUsageCostRecord.request_id == AIRequestRecord.id)
        .where(
            AIRequestRecord.organization_id == organization_id,
            AIRequestRecord.created_at >= start,
            AIRequestRecord.created_at < end,
        )
        .group_by(*group_columns)
        .order_by(*group_columns)
    )
    rows = db.execute(query).all()
    summaries: list[UsageSummaryRow] = []
    for row in rows:
        mapping = row._mapping
        raw_id = mapping["dimension_id"]
        summaries.append(
            UsageSummaryRow(
                dimension=dimension,
                dimension_id=str(raw_id) if raw_id is not None else None,
                dimension_label=(
                    str(mapping["dimension_label"])
                    if label_column is not None
                    and mapping["dimension_label"] is not None
                    else None
                ),
                request_count=int(mapping["request_count"] or 0),
                succeeded_count=int(mapping["succeeded_count"] or 0),
                failed_count=int(mapping["failed_count"] or 0),
                known_cost_requests=int(mapping["known_cost_requests"] or 0),
                unknown_cost_requests=int(mapping["unknown_cost_requests"] or 0),
                input_tokens=int(mapping["input_tokens"] or 0),
                output_tokens=int(mapping["output_tokens"] or 0),
                total_cost_nano_usd=int(mapping["total_cost_nano_usd"] or 0),
            )
        )
    return summaries
