"""Apply derived-content retention to native message revisions.

Revision ID: 20260918_0029
Revises: 20260918_0028
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260918_0029"
down_revision: str | None = "20260918_0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_retention_run_nonnegative_counts",
        "retention_runs",
        type_="check",
    )
    op.add_column(
        "retention_runs",
        sa.Column(
            "native_message_revisions_deleted",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_retention_run_nonnegative_counts",
        "retention_runs",
        "raw_events_deleted >= 0 AND derived_events_deleted >= 0 "
        "AND audit_events_deleted >= 0 AND private_messages_deleted >= 0 "
        "AND native_message_revisions_deleted >= 0",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_retention_run_nonnegative_counts",
        "retention_runs",
        type_="check",
    )
    op.drop_column("retention_runs", "native_message_revisions_deleted")
    op.create_check_constraint(
        "ck_retention_run_nonnegative_counts",
        "retention_runs",
        "raw_events_deleted >= 0 AND derived_events_deleted >= 0 "
        "AND audit_events_deleted >= 0 AND private_messages_deleted >= 0",
    )
