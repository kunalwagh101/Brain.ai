import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.ai_gateway_models import AIRequestRecord, AIRequestStatus
from app.ai_usage import _effective_rate_card, evaluate_budget_alerts_for_request
from app.ai_usage_models import AICostResolutionStatus, AIUsageCostRecord


def _needs_cost_resolution():
    return or_(
        AIUsageCostRecord.id.is_(None),
        AIUsageCostRecord.status == AICostResolutionStatus.UNKNOWN,
    )


def reconcile_usage_costs(
    db: Session,
    *,
    organization_id: uuid.UUID,
    limit: int,
) -> tuple[int, int, int]:
    query = (
        select(AIRequestRecord, AIUsageCostRecord)
        .outerjoin(AIUsageCostRecord, AIUsageCostRecord.request_id == AIRequestRecord.id)
        .where(
            AIRequestRecord.organization_id == organization_id,
            AIRequestRecord.status == AIRequestStatus.SUCCEEDED,
            _needs_cost_resolution(),
        )
        .order_by(AIRequestRecord.created_at, AIRequestRecord.id)
        .limit(limit)
    )
    if db.get_bind().dialect.name == "postgresql":
        query = query.with_for_update(skip_locked=True, of=AIRequestRecord)
    rows = db.execute(query).all()

    resolved = 0
    for request, cost in rows:
        rate = _effective_rate_card(db, request)
        can_calculate = (
            request.input_tokens is not None
            and request.output_tokens is not None
            and rate is not None
        )
        if cost is None:
            cost = AIUsageCostRecord(
                organization_id=request.organization_id,
                request_id=request.id,
                status=AICostResolutionStatus.UNKNOWN,
            )
            db.add(cost)

        if can_calculate:
            assert rate is not None
            assert request.input_tokens is not None
            assert request.output_tokens is not None
            input_cost = request.input_tokens * rate.input_nano_usd_per_token
            output_cost = request.output_tokens * rate.output_nano_usd_per_token
            cost.rate_card_id = rate.id
            cost.status = AICostResolutionStatus.CALCULATED
            cost.unknown_reason = None
            cost.input_cost_nano_usd = input_cost
            cost.output_cost_nano_usd = output_cost
            cost.total_cost_nano_usd = input_cost + output_cost
            resolved += 1
        else:
            cost.rate_card_id = rate.id if rate is not None else None
            cost.status = AICostResolutionStatus.UNKNOWN
            cost.unknown_reason = (
                "token_usage_unavailable"
                if request.input_tokens is None or request.output_tokens is None
                else "rate_card_unavailable"
            )
            cost.input_cost_nano_usd = None
            cost.output_cost_nano_usd = None
            cost.total_cost_nano_usd = None
        db.commit()
        if cost.status == AICostResolutionStatus.CALCULATED:
            evaluate_budget_alerts_for_request(db, request=request)

    remaining_query = (
        select(func.count(AIRequestRecord.id))
        .select_from(AIRequestRecord)
        .outerjoin(AIUsageCostRecord, AIUsageCostRecord.request_id == AIRequestRecord.id)
        .where(
            AIRequestRecord.organization_id == organization_id,
            AIRequestRecord.status == AIRequestStatus.SUCCEEDED,
            _needs_cost_resolution(),
        )
    )
    remaining = int(db.scalar(remaining_query) or 0)
    return len(rows), resolved, remaining
