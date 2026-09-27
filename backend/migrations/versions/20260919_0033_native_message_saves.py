"""Add private saved native messages.

Revision ID: 20260919_0033
Revises: 20260919_0032
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260919_0033"
down_revision: str | None = "20260919_0032"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "native_message_saves",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("channel_id", sa.Uuid(), nullable=False),
        sa.Column("message_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_native_message_save_membership",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "channel_id", "message_id"],
            [
                "native_messages.organization_id",
                "native_messages.channel_id",
                "native_messages.id",
            ],
            name="fk_native_message_save_message_scope",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "message_id",
            name="uq_native_message_save_user_message",
        ),
    )
    op.create_index(
        "ix_native_message_save_org_user_created",
        "native_message_saves",
        ["organization_id", "user_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_native_message_save_org_user_created",
        table_name="native_message_saves",
    )
    op.drop_table("native_message_saves")
