"""Workspace notifications and activity inbox state.

Revision ID: 20260917_0025
Revises: 20260916_0024
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260917_0025"
down_revision: str | None = "20260916_0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workspace_notifications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("recipient_user_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("dedupe_key", sa.String(length=255), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("channel_id", sa.Uuid(), nullable=True),
        sa.Column("native_message_id", sa.Uuid(), nullable=True),
        sa.Column("direct_conversation_id", sa.Uuid(), nullable=True),
        sa.Column("direct_message_id", sa.Uuid(), nullable=True),
        sa.Column("event_metadata", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["recipient_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["channel_id"], ["native_channels.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["native_message_id"], ["native_messages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["direct_conversation_id"], ["direct_conversations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["direct_message_id"], ["direct_messages.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "recipient_user_id",
            "dedupe_key",
            name="uq_workspace_notification_recipient_dedupe",
        ),
        sa.CheckConstraint(
            "kind IN ('mention', 'thread_reply', 'reaction', 'direct_message')",
            name="ck_workspace_notification_kind",
        ),
    )
    op.create_index(
        "ix_workspace_notification_org_recipient_created",
        "workspace_notifications",
        ["organization_id", "recipient_user_id", "created_at"],
    )
    op.create_index(
        "ix_workspace_notification_org_recipient_read",
        "workspace_notifications",
        ["organization_id", "recipient_user_id", "read_at", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_workspace_notification_org_recipient_read",
        table_name="workspace_notifications",
    )
    op.drop_index(
        "ix_workspace_notification_org_recipient_created",
        table_name="workspace_notifications",
    )
    op.drop_table("workspace_notifications")
