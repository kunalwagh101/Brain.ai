"""Staging demo sessions with revocation and signup limits.

Revision ID: 20260927_0041
Revises: 20260920_0040
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260927_0041"
down_revision: str | None = "20260920_0040"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "demo_sessions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "organization_id",
            sa.Uuid(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("source_hash", sa.String(64), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_demo_sessions_user_id", "demo_sessions", ["user_id"])
    op.create_index(
        "ix_demo_sessions_source_created", "demo_sessions", ["source_hash", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_demo_sessions_source_created", table_name="demo_sessions")
    op.drop_index("ix_demo_sessions_user_id", table_name="demo_sessions")
    op.drop_table("demo_sessions")
