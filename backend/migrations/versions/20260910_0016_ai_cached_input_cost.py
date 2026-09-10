"""Cache-aware AI usage and cost accounting.

Revision ID: 20260910_0016
Revises: 20260909_0015
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260910_0016"
down_revision: str | None = "20260909_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "ai_request_records",
        sa.Column("cached_input_tokens", sa.Integer(), nullable=True),
    )
    op.create_check_constraint(
        "ck_ai_request_cached_input_tokens",
        "ai_request_records",
        "cached_input_tokens IS NULL OR cached_input_tokens >= 0",
    )
    op.create_check_constraint(
        "ck_ai_request_cached_within_input_tokens",
        "ai_request_records",
        "cached_input_tokens IS NULL OR input_tokens IS NULL "
        "OR cached_input_tokens <= input_tokens",
    )

    op.add_column(
        "ai_model_rate_cards",
        sa.Column("cached_input_nano_usd_per_token", sa.BigInteger(), nullable=True),
    )
    op.create_check_constraint(
        "ck_ai_rate_cached_input_nonnegative",
        "ai_model_rate_cards",
        "cached_input_nano_usd_per_token IS NULL "
        "OR cached_input_nano_usd_per_token >= 0",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_ai_rate_cached_input_nonnegative",
        "ai_model_rate_cards",
        type_="check",
    )
    op.drop_column("ai_model_rate_cards", "cached_input_nano_usd_per_token")

    op.drop_constraint(
        "ck_ai_request_cached_within_input_tokens",
        "ai_request_records",
        type_="check",
    )
    op.drop_constraint(
        "ck_ai_request_cached_input_tokens",
        "ai_request_records",
        type_="check",
    )
    op.drop_column("ai_request_records", "cached_input_tokens")
