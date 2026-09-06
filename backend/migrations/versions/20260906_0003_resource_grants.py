"""Add tenant-scoped resource ACL grants.

Revision ID: 20260906_0003
Revises: 20260906_0002
Create Date: 2026-09-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260906_0003"
down_revision: str | None = "20260906_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    access_enum = sa.Enum(
        "READ",
        "WRITE",
        name="resourceaccesslevel",
        native_enum=False,
        length=16,
    )
    op.create_table(
        "resource_grants",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("resource_type", sa.String(length=64), nullable=False),
        sa.Column("resource_id", sa.String(length=255), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("access", access_enum, nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "resource_type",
            "resource_id",
            "user_id",
            "access",
            name="uq_resource_grant_scope_user_access",
        ),
    )
    op.create_index(
        "ix_resource_grants_org_resource",
        "resource_grants",
        ["organization_id", "resource_type", "resource_id"],
    )
    op.create_index(
        "ix_resource_grants_organization_id",
        "resource_grants",
        ["organization_id"],
    )
    op.create_index("ix_resource_grants_user_id", "resource_grants", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_resource_grants_user_id", table_name="resource_grants")
    op.drop_index("ix_resource_grants_organization_id", table_name="resource_grants")
    op.drop_index("ix_resource_grants_org_resource", table_name="resource_grants")
    op.drop_table("resource_grants")
