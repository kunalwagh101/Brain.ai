"""Add per-user reference-only activity notifications.

Revision ID: 20260918_0025
Revises: 20260916_0024
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260918_0025"
down_revision: str | None = "20260916_0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "activity_notifications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("recipient_user_id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("resource_type", sa.String(length=32), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=False),
        sa.Column("context_id", sa.Uuid(), nullable=True),
        sa.Column("dedupe_key", sa.String(length=192), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "kind IN ('mention','thread_reply','reaction','direct_message','agent_approval')",
            name="ck_activity_notification_kind",
        ),
        sa.CheckConstraint(
            "resource_type IN ('native_message','direct_message','agent_run')",
            name="ck_activity_notification_resource_type",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["recipient_user_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "recipient_user_id",
            "dedupe_key",
            name="uq_activity_notification_recipient_dedupe",
        ),
    )
    op.create_index(
        "ix_activity_notification_org_recipient_created",
        "activity_notifications",
        ["organization_id", "recipient_user_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_activity_notification_org_recipient_read",
        "activity_notifications",
        ["organization_id", "recipient_user_id", "read_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_activity_notification_org_recipient_read",
        table_name="activity_notifications",
    )
    op.drop_index(
        "ix_activity_notification_org_recipient_created",
        table_name="activity_notifications",
    )
    op.drop_table("activity_notifications")
