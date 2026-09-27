"""Add ephemeral collaboration presence and typing leases.

Revision ID: 20260919_0031
Revises: 20260918_0030
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260919_0031"
down_revision: str | None = "20260918_0030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "collaboration_presence_leases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id", "user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_collaboration_presence_membership",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "user_id",
            name="uq_collaboration_presence_org_user",
        ),
    )
    op.create_index(
        "ix_collaboration_presence_org_expires",
        "collaboration_presence_leases",
        ["organization_id", "expires_at"],
        unique=False,
    )

    op.create_table(
        "collaboration_typing_leases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("native_channel_id", sa.Uuid(), nullable=True),
        sa.Column("direct_conversation_id", sa.Uuid(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "(native_channel_id IS NOT NULL AND direct_conversation_id IS NULL) "
            "OR (native_channel_id IS NULL AND direct_conversation_id IS NOT NULL)",
            name="ck_collaboration_typing_exact_context",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_collaboration_typing_membership",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "native_channel_id"],
            ["native_channels.organization_id", "native_channels.id"],
            name="fk_collaboration_typing_channel_scope",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "direct_conversation_id"],
            ["direct_conversations.organization_id", "direct_conversations.id"],
            name="fk_collaboration_typing_dm_scope",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "native_channel_id",
            "user_id",
            name="uq_collaboration_typing_channel_user",
        ),
        sa.UniqueConstraint(
            "direct_conversation_id",
            "user_id",
            name="uq_collaboration_typing_dm_user",
        ),
    )
    op.create_index(
        "ix_collaboration_typing_org_expires",
        "collaboration_typing_leases",
        ["organization_id", "expires_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_collaboration_typing_org_expires",
        table_name="collaboration_typing_leases",
    )
    op.drop_table("collaboration_typing_leases")
    op.drop_index(
        "ix_collaboration_presence_org_expires",
        table_name="collaboration_presence_leases",
    )
    op.drop_table("collaboration_presence_leases")
