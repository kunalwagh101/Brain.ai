"""Add shared native channel message pins.

Revision ID: 20260919_0032
Revises: 20260919_0031
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260919_0032"
down_revision: str | None = "20260919_0031"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "native_message_pins",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("channel_id", sa.Uuid(), nullable=False),
        sa.Column("message_id", sa.Uuid(), nullable=False),
        sa.Column("pinned_by_user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "channel_id", "message_id"],
            [
                "native_messages.organization_id",
                "native_messages.channel_id",
                "native_messages.id",
            ],
            name="fk_native_message_pin_message_scope",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["pinned_by_user_id"],
            ["users.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "channel_id",
            "message_id",
            name="uq_native_message_pin_channel_message",
        ),
    )
    op.create_index(
        "ix_native_message_pin_org_channel_created",
        "native_message_pins",
        ["organization_id", "channel_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_native_message_pin_org_channel_created",
        table_name="native_message_pins",
    )
    op.drop_table("native_message_pins")
