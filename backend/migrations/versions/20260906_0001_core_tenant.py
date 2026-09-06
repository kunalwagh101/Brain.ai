"""Create core tenant tables.

Revision ID: 20260906_0001
Revises:
Create Date: 2026-09-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260906_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("ix_organizations_slug", "organizations", ["slug"], unique=True)

    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("display_name", sa.String(length=160), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    role_enum = sa.Enum(
        "OWNER",
        "ADMIN",
        "EXECUTIVE",
        "MANAGER",
        "MEMBER",
        "GUEST",
        name="membershiprole",
        native_enum=False,
        length=32,
    )
    op.create_table(
        "memberships",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role", role_enum, nullable=False),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "user_id", name="uq_membership_org_user"),
    )
    op.create_index("ix_memberships_organization_id", "memberships", ["organization_id"])
    op.create_index("ix_memberships_user_id", "memberships", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_memberships_user_id", table_name="memberships")
    op.drop_index("ix_memberships_organization_id", table_name="memberships")
    op.drop_table("memberships")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
    op.drop_index("ix_organizations_slug", table_name="organizations")
    op.drop_table("organizations")
