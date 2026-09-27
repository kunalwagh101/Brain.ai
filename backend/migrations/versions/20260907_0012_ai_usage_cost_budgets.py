"""AI usage, cost and budgets

Revision ID: 20260907_0012
Revises: 20260907_0011
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260907_0012"
down_revision: str | None = "20260907_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_model_rate_cards",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("provider_configuration_id", sa.Uuid(), nullable=False),
        sa.Column("model_configuration_id", sa.Uuid(), nullable=False),
        sa.Column("input_nano_usd_per_token", sa.BigInteger(), nullable=False),
        sa.Column("output_nano_usd_per_token", sa.BigInteger(), nullable=False),
        sa.Column("source_label", sa.String(length=255), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "input_nano_usd_per_token >= 0",
            name="ck_ai_rate_input_nonnegative",
        ),
        sa.CheckConstraint(
            "output_nano_usd_per_token >= 0",
            name="ck_ai_rate_output_nonnegative",
        ),
        sa.CheckConstraint(
            "effective_to IS NULL OR effective_to > effective_from",
            name="ck_ai_rate_effective_window",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["provider_configuration_id"],
            ["ai_provider_configurations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["model_configuration_id"],
            ["ai_model_configurations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "model_configuration_id",
            "effective_from",
            name="uq_ai_model_rate_card_effective_from",
        ),
    )
    op.create_index(
        "ix_ai_rate_model_effective",
        "ai_model_rate_cards",
        ["model_configuration_id", "effective_from", "effective_to"],
    )

    op.create_table(
        "ai_usage_cost_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("rate_card_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("unknown_reason", sa.String(length=128), nullable=True),
        sa.Column("input_cost_nano_usd", sa.BigInteger(), nullable=True),
        sa.Column("output_cost_nano_usd", sa.BigInteger(), nullable=True),
        sa.Column("total_cost_nano_usd", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "input_cost_nano_usd IS NULL OR input_cost_nano_usd >= 0",
            name="ck_ai_usage_input_cost_nonnegative",
        ),
        sa.CheckConstraint(
            "output_cost_nano_usd IS NULL OR output_cost_nano_usd >= 0",
            name="ck_ai_usage_output_cost_nonnegative",
        ),
        sa.CheckConstraint(
            "total_cost_nano_usd IS NULL OR total_cost_nano_usd >= 0",
            name="ck_ai_usage_total_cost_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["request_id"], ["ai_request_records.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["rate_card_id"], ["ai_model_rate_cards.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("request_id", name="uq_ai_usage_cost_request"),
    )
    op.create_index(
        "ix_ai_usage_cost_org_created",
        "ai_usage_cost_records",
        ["organization_id", "created_at"],
    )
    op.create_index(
        "ix_ai_usage_cost_rate_card",
        "ai_usage_cost_records",
        ["rate_card_id"],
    )

    op.create_table(
        "ai_budget_policies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("scope_type", sa.String(length=32), nullable=False),
        sa.Column("scope_key", sa.String(length=64), nullable=False),
        sa.Column("scope_target_id", sa.Uuid(), nullable=True),
        sa.Column("period", sa.String(length=32), nullable=False),
        sa.Column("limit_nano_usd", sa.BigInteger(), nullable=False),
        sa.Column("warning_threshold_percent", sa.Integer(), nullable=False),
        sa.Column("hard_limit", sa.Boolean(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "limit_nano_usd > 0", name="ck_ai_budget_positive_limit"
        ),
        sa.CheckConstraint(
            "warning_threshold_percent >= 1 AND warning_threshold_percent <= 100",
            name="ck_ai_budget_warning_threshold",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "scope_type",
            "scope_key",
            "period",
            name="uq_ai_budget_scope_period",
        ),
    )
    op.create_index(
        "ix_ai_budget_org_enabled",
        "ai_budget_policies",
        ["organization_id", "enabled"],
    )

    op.create_table(
        "ai_budget_alerts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("budget_policy_id", sa.Uuid(), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("threshold_percent", sa.Integer(), nullable=False),
        sa.Column("spend_nano_usd", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "threshold_percent >= 1 AND threshold_percent <= 100",
            name="ck_ai_budget_alert_threshold",
        ),
        sa.CheckConstraint(
            "spend_nano_usd >= 0",
            name="ck_ai_budget_alert_spend_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["budget_policy_id"], ["ai_budget_policies.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "budget_policy_id",
            "period_start",
            "threshold_percent",
            name="uq_ai_budget_alert_threshold_period",
        ),
    )
    op.create_index(
        "ix_ai_budget_alert_org_created",
        "ai_budget_alerts",
        ["organization_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("ai_budget_alerts")
    op.drop_table("ai_budget_policies")
    op.drop_table("ai_usage_cost_records")
    op.drop_table("ai_model_rate_cards")
