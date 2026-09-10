"""Structured project progress for the command centre.

Revision ID: 20260910_0018
Revises: 20260910_0017
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260910_0018"
down_revision: str | None = "20260910_0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "project_progress_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_node_id", sa.Uuid(), nullable=False),
        sa.Column("work_item_node_id", sa.Uuid(), nullable=False),
        sa.Column("state", sa.String(length=24), nullable=False),
        sa.Column("weight", sa.Integer(), nullable=False),
        sa.Column("note", sa.String(length=1000), nullable=True),
        sa.Column("updated_by_user_id", sa.Uuid(), nullable=False),
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
        sa.CheckConstraint(
            "weight > 0 AND weight <= 10000",
            name="ck_project_progress_weight",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["project_node_id"], ["work_graph_nodes.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["work_item_node_id"], ["work_graph_nodes.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "project_node_id",
            "work_item_node_id",
            name="uq_project_progress_org_project_item",
        ),
    )
    op.create_index(
        "ix_project_progress_org_project",
        "project_progress_items",
        ["organization_id", "project_node_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_project_progress_org_project",
        table_name="project_progress_items",
    )
    op.drop_table("project_progress_items")
