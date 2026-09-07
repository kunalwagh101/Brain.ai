import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai_usage import (
    AIUsageError,
    budget_snapshot,
    calendar_month_window,
    create_budget_policy,
    create_model_rate_card,
    set_budget_enabled,
    usage_summary,
)
from app.ai_usage_models import (
    AIBudgetAlert,
    AIBudgetPeriod,
    AIBudgetPolicy,
    AIBudgetScopeType,
    AIModelRateCard,
)
from app.database import get_db
from app.permissions import AuthorizationContext, Permission, require_organization_permission

router = APIRouter(
    prefix="/organizations/{organization_id}/ai",
    tags=["ai-usage"],
)
_manage_ai = require_organization_permission(Permission.AI_MANAGE)
_read_usage = require_organization_permission(Permission.AUDIT_READ)


class UsageDimension(StrEnum):
    ORGANIZATION = "organization"
    PROVIDER = "provider"
    MODEL = "model"
    USER = "user"
    WORK_GRAPH_NODE = "work_graph_node"


class RateCardCreate(BaseModel):
    provider_configuration_id: uuid.UUID
    model_configuration_id: uuid.UUID
    input_nano_usd_per_token: int = Field(ge=0)
    output_nano_usd_per_token: int = Field(ge=0)
    source_label: str = Field(min_length=1, max_length=255)
    effective_from: datetime
    effective_to: datetime | None = None


class RateCardRead(BaseModel):
    id: uuid.UUID
    provider_configuration_id: uuid.UUID
    model_configuration_id: uuid.UUID
    input_nano_usd_per_token: int
    output_nano_usd_per_token: int
    source_label: str
    effective_from: datetime
    effective_to: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class BudgetCreate(BaseModel):
    scope_type: AIBudgetScopeType
    scope_target_id: uuid.UUID | None = None
    limit_nano_usd: int = Field(gt=0)
    warning_threshold_percent: int = Field(default=80, ge=1, le=100)
    hard_limit: bool = False
    enabled: bool = True


class BudgetRead(BaseModel):
    id: uuid.UUID
    scope_type: AIBudgetScopeType
    scope_target_id: uuid.UUID | None
    period: AIBudgetPeriod
    limit_nano_usd: int
    warning_threshold_percent: int
    hard_limit: bool
    enabled: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BudgetStatusUpdate(BaseModel):
    enabled: bool


class BudgetSnapshotRead(BaseModel):
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


class BudgetAlertRead(BaseModel):
    id: uuid.UUID
    budget_policy_id: uuid.UUID
    period_start: object
    threshold_percent: int
    spend_nano_usd: int
    created_at: datetime

    model_config = {"from_attributes": True}


class UsageSummaryRead(BaseModel):
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


class UsageSummaryResponse(BaseModel):
    start: datetime
    end: datetime
    dimension: UsageDimension
    rows: list[UsageSummaryRead]


def _raise_usage_error(exc: AIUsageError) -> None:
    message = str(exc)
    if "already exists" in message or "overlaps" in message:
        code = status.HTTP_409_CONFLICT
    elif "not found" in message:
        code = status.HTTP_404_NOT_FOUND
    else:
        code = status.HTTP_400_BAD_REQUEST
    raise HTTPException(status_code=code, detail=message) from exc


@router.post(
    "/rate-cards",
    response_model=RateCardRead,
    status_code=status.HTTP_201_CREATED,
)
def create_rate_card(
    organization_id: uuid.UUID,
    payload: RateCardCreate,
    authorization: Annotated[AuthorizationContext, Depends(_manage_ai)],
    db: Annotated[Session, Depends(get_db)],
) -> AIModelRateCard:
    try:
        return create_model_rate_card(
            db,
            organization_id=organization_id,
            actor_user_id=authorization.user_id,
            provider_configuration_id=payload.provider_configuration_id,
            model_configuration_id=payload.model_configuration_id,
            input_nano_usd_per_token=payload.input_nano_usd_per_token,
            output_nano_usd_per_token=payload.output_nano_usd_per_token,
            source_label=payload.source_label,
            effective_from=payload.effective_from,
            effective_to=payload.effective_to,
        )
    except AIUsageError as exc:
        _raise_usage_error(exc)


@router.get("/rate-cards", response_model=list[RateCardRead])
def list_rate_cards(
    organization_id: uuid.UUID,
    authorization: Annotated[AuthorizationContext, Depends(_read_usage)],
    db: Annotated[Session, Depends(get_db)],
    model_configuration_id: uuid.UUID | None = None,
) -> list[AIModelRateCard]:
    del authorization
    query = select(AIModelRateCard).where(
        AIModelRateCard.organization_id == organization_id
    )
    if model_configuration_id is not None:
        query = query.where(
            AIModelRateCard.model_configuration_id == model_configuration_id
        )
    return list(
        db.scalars(
            query.order_by(
                AIModelRateCard.model_configuration_id,
                AIModelRateCard.effective_from.desc(),
            )
        )
    )


@router.post(
    "/budgets",
    response_model=BudgetRead,
    status_code=status.HTTP_201_CREATED,
)
def create_budget(
    organization_id: uuid.UUID,
    payload: BudgetCreate,
    authorization: Annotated[AuthorizationContext, Depends(_manage_ai)],
    db: Annotated[Session, Depends(get_db)],
) -> AIBudgetPolicy:
    try:
        return create_budget_policy(
            db,
            organization_id=organization_id,
            actor_user_id=authorization.user_id,
            scope_type=payload.scope_type,
            scope_target_id=payload.scope_target_id,
            limit_nano_usd=payload.limit_nano_usd,
            warning_threshold_percent=payload.warning_threshold_percent,
            hard_limit=payload.hard_limit,
            enabled=payload.enabled,
        )
    except AIUsageError as exc:
        _raise_usage_error(exc)


@router.get("/budgets", response_model=list[BudgetRead])
def list_budgets(
    organization_id: uuid.UUID,
    authorization: Annotated[AuthorizationContext, Depends(_read_usage)],
    db: Annotated[Session, Depends(get_db)],
) -> list[AIBudgetPolicy]:
    del authorization
    return list(
        db.scalars(
            select(AIBudgetPolicy)
            .where(AIBudgetPolicy.organization_id == organization_id)
            .order_by(AIBudgetPolicy.created_at, AIBudgetPolicy.id)
        )
    )


@router.post("/budgets/{budget_id}/status", response_model=BudgetRead)
def update_budget_status(
    organization_id: uuid.UUID,
    budget_id: uuid.UUID,
    payload: BudgetStatusUpdate,
    authorization: Annotated[AuthorizationContext, Depends(_manage_ai)],
    db: Annotated[Session, Depends(get_db)],
) -> AIBudgetPolicy:
    del authorization
    try:
        return set_budget_enabled(
            db,
            organization_id=organization_id,
            budget_policy_id=budget_id,
            enabled=payload.enabled,
        )
    except AIUsageError as exc:
        _raise_usage_error(exc)


@router.get("/budgets/{budget_id}/snapshot", response_model=BudgetSnapshotRead)
def read_budget_snapshot(
    organization_id: uuid.UUID,
    budget_id: uuid.UUID,
    authorization: Annotated[AuthorizationContext, Depends(_read_usage)],
    db: Annotated[Session, Depends(get_db)],
) -> BudgetSnapshotRead:
    del authorization
    policy = db.scalar(
        select(AIBudgetPolicy).where(
            AIBudgetPolicy.id == budget_id,
            AIBudgetPolicy.organization_id == organization_id,
        )
    )
    if policy is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Budget policy not found",
        )
    snapshot = budget_snapshot(db, policy=policy, at=datetime.now(UTC))
    return BudgetSnapshotRead(**snapshot.__dict__)


@router.get("/budget-alerts", response_model=list[BudgetAlertRead])
def list_budget_alerts(
    organization_id: uuid.UUID,
    authorization: Annotated[AuthorizationContext, Depends(_read_usage)],
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[AIBudgetAlert]:
    del authorization
    return list(
        db.scalars(
            select(AIBudgetAlert)
            .where(AIBudgetAlert.organization_id == organization_id)
            .order_by(AIBudgetAlert.created_at.desc())
            .limit(limit)
        )
    )


@router.get("/usage/summary", response_model=UsageSummaryResponse)
def read_usage_summary(
    organization_id: uuid.UUID,
    authorization: Annotated[AuthorizationContext, Depends(_read_usage)],
    db: Annotated[Session, Depends(get_db)],
    dimension: UsageDimension = UsageDimension.PROVIDER,
    start: datetime | None = None,
    end: datetime | None = None,
) -> UsageSummaryResponse:
    del authorization
    now = datetime.now(UTC)
    default_start, default_end = calendar_month_window(now)
    start = start or default_start
    end = end or min(default_end, now)
    try:
        rows = usage_summary(
            db,
            organization_id=organization_id,
            start=start,
            end=end,
            dimension=dimension.value,
        )
    except AIUsageError as exc:
        _raise_usage_error(exc)
    return UsageSummaryResponse(
        start=start,
        end=end,
        dimension=dimension,
        rows=[UsageSummaryRead(**row.__dict__) for row in rows],
    )
