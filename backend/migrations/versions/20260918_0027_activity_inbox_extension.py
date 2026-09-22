"""Extend Activity into the unified notifications inbox.

Revision ID: 20260918_0027
Revises: 20260918_0026
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260918_0027"
down_revision: str | None = "20260918_0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_ACTIVITY_KINDS = (
    "mention",
    "thread_reply",
    "reaction",
    "direct_message",
    "channel_activity",
    "agent_approval",
    "agent_completed",
    "agent_failed",
    "project_update",
    "blocker_update",
    "integration_failure",
)
_RESOURCE_TYPES = (
    "native_message",
    "direct_message",
    "native_channel",
    "agent_run",
    "project",
    "blocker",
    "integration",
)


def _check_values(column: str, values: tuple[str, ...]) -> str:
    quoted = ", ".join(f"'{value}'" for value in values)
    return f"{column} IN ({quoted})"


def upgrade() -> None:
    op.drop_constraint("ck_activity_notification_kind", "activity_notifications", type_="check")
    op.drop_constraint(
        "ck_activity_notification_resource_type",
        "activity_notifications",
        type_="check",
    )
    op.create_check_constraint(
        "ck_activity_notification_kind",
        "activity_notifications",
        _check_values("kind", _ACTIVITY_KINDS),
    )
    op.create_check_constraint(
        "ck_activity_notification_resource_type",
        "activity_notifications",
        _check_values("resource_type", _RESOURCE_TYPES),
    )

    op.create_table(
        "activity_preferences",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("mentions", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("thread_replies", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("direct_messages", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("channel_activity", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("agent_approvals", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("agent_run_events", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("project_updates", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("integration_failures", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "user_id", name="uq_activity_preference_org_user"),
    )
    op.create_index(
        "ix_activity_preference_org_user",
        "activity_preferences",
        ["organization_id", "user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_activity_preference_org_user", table_name="activity_preferences")
    op.drop_table("activity_preferences")

    op.drop_constraint("ck_activity_notification_kind", "activity_notifications", type_="check")
    op.drop_constraint("ck_activity_notification_resource_type", "activity_notifications", type_="check")
    op.create_check_constraint(
        "ck_activity_notification_kind",
        "activity_notifications",
        _check_values(
            "kind",
            ("mention", "thread_reply", "reaction", "direct_message", "agent_approval"),
        ),
    )
    op.create_check_constraint(
        "ck_activity_notification_resource_type",
        "activity_notifications",
        _check_values("resource_type", ("native_message", "direct_message", "agent_run")),
    )
