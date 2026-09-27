"""Explicit private-message retention policy and run accounting.

Revision ID: 20260916_0023
Revises: 20260916_0022
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260916_0023"
down_revision: str | None = "20260916_0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "organization_retention_policies",
        sa.Column("private_message_days", sa.Integer(), nullable=True),
    )
    op.create_check_constraint(
        "ck_retention_policy_private_message_days",
        "organization_retention_policies",
        "private_message_days IS NULL OR "
        "(private_message_days >= 1 AND private_message_days <= 36500)",
    )

    op.add_column(
        "retention_runs",
        sa.Column("private_message_days", sa.Integer(), nullable=True),
    )
    op.add_column(
        "retention_runs",
        sa.Column(
            "private_messages_deleted",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
    )
    op.drop_constraint(
        "ck_retention_run_nonnegative_counts",
        "retention_runs",
        type_="check",
    )
    op.create_check_constraint(
        "ck_retention_run_nonnegative_counts",
        "retention_runs",
        "raw_events_deleted >= 0 AND derived_events_deleted >= 0 "
        "AND audit_events_deleted >= 0 AND private_messages_deleted >= 0",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_retention_run_nonnegative_counts",
        "retention_runs",
        type_="check",
    )
    op.create_check_constraint(
        "ck_retention_run_nonnegative_counts",
        "retention_runs",
        "raw_events_deleted >= 0 AND derived_events_deleted >= 0 "
        "AND audit_events_deleted >= 0",
    )
    op.drop_column("retention_runs", "private_messages_deleted")
    op.drop_column("retention_runs", "private_message_days")

    op.drop_constraint(
        "ck_retention_policy_private_message_days",
        "organization_retention_policies",
        type_="check",
    )
    op.drop_column("organization_retention_policies", "private_message_days")
