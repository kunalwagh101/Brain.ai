"""Bind governed agent runs to visible workspace context.

Revision ID: 20260916_0021
Revises: 20260912_0020
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260916_0021"
down_revision: str | None = "20260912_0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_run_contexts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("project_node_id", sa.Uuid(), nullable=True),
        sa.Column("native_channel_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "project_node_id IS NOT NULL OR native_channel_id IS NOT NULL",
            name="ck_agent_run_context_has_scope",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["run_id"], ["agent_runs.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["project_node_id"], ["work_graph_nodes.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["native_channel_id"], ["native_channels.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", name="uq_agent_run_context_run"),
    )
    op.create_index(
        "ix_agent_run_context_org_project",
        "agent_run_contexts",
        ["organization_id", "project_node_id"],
        unique=False,
    )
    op.create_index(
        "ix_agent_run_context_org_channel",
        "agent_run_contexts",
        ["organization_id", "native_channel_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_agent_run_context_org_channel",
        table_name="agent_run_contexts",
    )
    op.drop_index(
        "ix_agent_run_context_org_project",
        table_name="agent_run_contexts",
    )
    op.drop_table("agent_run_contexts")
