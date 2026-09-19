"""Add per-user native thread read state.

Revision ID: 20260920_0036
Revises: 20260919_0035
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260920_0036"
down_revision: str | None = "20260919_0035"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "native_thread_read_states",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("channel_id", sa.Uuid(), nullable=False),
        sa.Column("root_message_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("last_read_message_id", sa.Uuid(), nullable=False),
        sa.Column("last_read_sequence", sa.BigInteger(), nullable=False),
        sa.Column("last_read_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_native_thread_read_state_membership",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "channel_id", "root_message_id"],
            [
                "native_messages.organization_id",
                "native_messages.channel_id",
                "native_messages.id",
            ],
            name="fk_native_thread_read_state_root_scope",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "channel_id", "last_read_message_id"],
            [
                "native_messages.organization_id",
                "native_messages.channel_id",
                "native_messages.id",
            ],
            name="fk_native_thread_read_state_message_scope",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "root_message_id",
            "user_id",
            name="uq_native_thread_read_state_root_user",
        ),
    )
    op.create_index(
        "ix_native_thread_read_state_org_user",
        "native_thread_read_states",
        ["organization_id", "user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_native_thread_read_state_org_user",
        table_name="native_thread_read_states",
    )
    op.drop_table("native_thread_read_states")
