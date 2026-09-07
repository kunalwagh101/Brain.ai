import uuid

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.ai_gateway_models import AIRequestRecord, AIRequestStatus
from app.ai_usage import _effective_rate_card, evaluate_budget_alerts_for_request
from app.ai_usage_models import AICostResolutionStatus, AIUsageCostRecord


def reconcile_usage_costs(
    db: Session,
    *,
    organization_id: uuid.UUID,
    limit: int,
) -> tuple[int, int, int]:
    rows = db.execute(
        select(AIRequestRecord, AIUsageCostRecord)
        .outerjoin(AIUsageCostRecord, AIUsageCostRecord.request_id == AIRequestRecord.id)
        .where(
            AIRequestRecord.organization_id == organization_id,
            AIRequestRecord.status == AIRequestStatus.SUCCEEDED,
            or_(
                AIUsageCostRecord.id.is_(None),
                AIUsageCostRecord.status == AICostResolutionStatus.UNKNOWN,
            ),
        )
        .order_by(AIRequestRecord.created_at, AIRequestRecord.id)
        .limit(limit)
    ).all()

    resolved = 0
    unknown = 0
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
            unknown += 1
        db.commit()
        if cost.status == AICostResolutionStatus.CALCULATED:
            evaluate_budget_alerts_for_request(db, request=request)

    remaining = db.scalar(
        select(AIRequestRecord.id)
        .outerjoin(AIUsageCostRecord, AIUsageCostRecord.request_id == AIRequestRecord.id)
        .where(
            AIRequestRecord.organization_id == organization_id,
            AIRequestRecord.status == AIRequestStatus.SUCCEEDED,
            or_(
                AIUsageCostRecord.id.is_(None),
                AIUsageCostRecord.status == AICostResolutionStatus.UNKNOWN,
            ),
        )
        .limit(1)
    )
    return len(rows), resolved, unknown + int(remaining is not None and len(rows) == limit)
