"""Revocable participant access and visibility epochs for Brain-native DMs.

Revision ID: 20260916_0024
Revises: 20260916_0023
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260916_0024"
down_revision: str | None = "20260916_0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "direct_conversations",
        sa.Column("participant_a_visible_from", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "direct_conversations",
        sa.Column("participant_b_visible_from", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "direct_conversations",
        sa.Column("participant_a_revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "direct_conversations",
        sa.Column("participant_b_revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        "UPDATE direct_conversations "
        "SET participant_a_visible_from = created_at, "
        "participant_b_visible_from = created_at"
    )
    op.alter_column(
        "direct_conversations",
        "participant_a_visible_from",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
    )
    op.alter_column(
        "direct_conversations",
        "participant_b_visible_from",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
    )


def downgrade() -> None:
    op.drop_column("direct_conversations", "participant_b_revoked_at")
    op.drop_column("direct_conversations", "participant_a_revoked_at")
    op.drop_column("direct_conversations", "participant_b_visible_from")
    op.drop_column("direct_conversations", "participant_a_visible_from")
