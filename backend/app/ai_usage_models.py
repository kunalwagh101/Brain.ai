import uuid
from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class AICostResolutionStatus(StrEnum):
    CALCULATED = "calculated"
    UNKNOWN = "unknown"


class AIBudgetScopeType(StrEnum):
    ORGANIZATION = "organization"
    PROVIDER = "provider"
    MODEL = "model"
    USER = "user"
    WORK_GRAPH_NODE = "work_graph_node"


class AIBudgetPeriod(StrEnum):
    CALENDAR_MONTH = "calendar_month"


class AIModelRateCard(Base):
    __tablename__ = "ai_model_rate_cards"
    __table_args__ = (
        UniqueConstraint(
            "model_configuration_id",
            "effective_from",
            name="uq_ai_model_rate_card_effective_from",
        ),
        CheckConstraint(
            "input_nano_usd_per_token >= 0",
            name="ck_ai_rate_input_nonnegative",
        ),
        CheckConstraint(
            "output_nano_usd_per_token >= 0",
            name="ck_ai_rate_output_nonnegative",
        ),
        CheckConstraint(
            "effective_to IS NULL OR effective_to > effective_from",
            name="ck_ai_rate_effective_window",
        ),
        Index(
            "ix_ai_rate_model_effective",
            "model_configuration_id",
            "effective_from",
            "effective_to",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    provider_configuration_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ai_provider_configurations.id", ondelete="CASCADE"), nullable=False
    )
    model_configuration_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ai_model_configurations.id", ondelete="CASCADE"), nullable=False
    )
    input_nano_usd_per_token: Mapped[int] = mapped_column(BigInteger, nullable=False)
    output_nano_usd_per_token: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source_label: Mapped[str] = mapped_column(String(255), nullable=False)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AIUsageCostRecord(Base):
    __tablename__ = "ai_usage_cost_records"
    __table_args__ = (
        UniqueConstraint("request_id", name="uq_ai_usage_cost_request"),
        CheckConstraint(
            "input_cost_nano_usd IS NULL OR input_cost_nano_usd >= 0",
            name="ck_ai_usage_input_cost_nonnegative",
        ),
        CheckConstraint(
            "output_cost_nano_usd IS NULL OR output_cost_nano_usd >= 0",
            name="ck_ai_usage_output_cost_nonnegative",
        ),
        CheckConstraint(
            "total_cost_nano_usd IS NULL OR total_cost_nano_usd >= 0",
            name="ck_ai_usage_total_cost_nonnegative",
        ),
        Index(
            "ix_ai_usage_cost_org_created",
            "organization_id",
            "created_at",
        ),
        Index(
            "ix_ai_usage_cost_rate_card",
            "rate_card_id",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    request_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ai_request_records.id", ondelete="CASCADE"), nullable=False
    )
    rate_card_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ai_model_rate_cards.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[AICostResolutionStatus] = mapped_column(
        Enum(AICostResolutionStatus, native_enum=False, length=16), nullable=False
    )
    unknown_reason: Mapped[str | None] = mapped_column(String(128), nullable=True)
    input_cost_nano_usd: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    output_cost_nano_usd: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    total_cost_nano_usd: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AIBudgetPolicy(Base):
    __tablename__ = "ai_budget_policies"
    __table_args__ = (
        CheckConstraint("limit_nano_usd > 0", name="ck_ai_budget_positive_limit"),
        CheckConstraint(
            "warning_threshold_percent >= 1 AND warning_threshold_percent <= 100",
            name="ck_ai_budget_warning_threshold",
        ),
        UniqueConstraint(
            "organization_id",
            "scope_type",
            "scope_target_id",
            "period",
            name="uq_ai_budget_scope_period",
        ),
        Index(
            "ix_ai_budget_org_enabled",
            "organization_id",
            "enabled",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    scope_type: Mapped[AIBudgetScopeType] = mapped_column(
        Enum(AIBudgetScopeType, native_enum=False, length=32), nullable=False
    )
    scope_target_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    period: Mapped[AIBudgetPeriod] = mapped_column(
        Enum(AIBudgetPeriod, native_enum=False, length=32),
        default=AIBudgetPeriod.CALENDAR_MONTH,
        nullable=False,
    )
    limit_nano_usd: Mapped[int] = mapped_column(BigInteger, nullable=False)
    warning_threshold_percent: Mapped[int] = mapped_column(Integer, default=80, nullable=False)
    hard_limit: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class AIBudgetAlert(Base):
    __tablename__ = "ai_budget_alerts"
    __table_args__ = (
        UniqueConstraint(
            "budget_policy_id",
            "period_start",
            "threshold_percent",
            name="uq_ai_budget_alert_threshold_period",
        ),
        CheckConstraint(
            "threshold_percent >= 1 AND threshold_percent <= 100",
            name="ck_ai_budget_alert_threshold",
        ),
        CheckConstraint(
            "spend_nano_usd >= 0",
            name="ck_ai_budget_alert_spend_nonnegative",
        ),
        Index(
            "ix_ai_budget_alert_org_created",
            "organization_id",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    budget_policy_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ai_budget_policies.id", ondelete="CASCADE"), nullable=False
    )
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    threshold_percent: Mapped[int] = mapped_column(Integer, nullable=False)
    spend_nano_usd: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
