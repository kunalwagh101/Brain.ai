"""Add Team channel groups and channel navigation references.

Revision ID: 20260920_0039
Revises: 20260920_0038
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260920_0039"
down_revision: str | None = "20260920_0038"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "native_channel_groups",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("team_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("slug", sa.String(length=96), nullable=False),
        sa.Column("status", sa.String(length=24), server_default="active", nullable=False),
        sa.Column("revision", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
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
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "revision >= 1",
            name="ck_native_channel_group_revision_positive",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "team_id"],
            ["native_teams.organization_id", "native_teams.id"],
            name="fk_native_channel_group_team_scope",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name="fk_native_channel_group_creator",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "team_id",
            "slug",
            name="uq_native_channel_group_team_slug",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "team_id",
            "id",
            name="uq_native_channel_group_scope_id",
        ),
    )
    op.create_index(
        "ix_native_channel_group_org_team_status_name",
        "native_channel_groups",
        ["organization_id", "team_id", "status", "name"],
        unique=False,
    )

    op.add_column("native_channels", sa.Column("team_id", sa.Uuid(), nullable=True))
    op.add_column(
        "native_channels",
        sa.Column("channel_group_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_native_channel_team_scope",
        "native_channels",
        "native_teams",
        ["organization_id", "team_id"],
        ["organization_id", "id"],
    )
    op.create_foreign_key(
        "fk_native_channel_group_scope",
        "native_channels",
        "native_channel_groups",
        ["organization_id", "team_id", "channel_group_id"],
        ["organization_id", "team_id", "id"],
    )
    op.create_check_constraint(
        "ck_native_channel_group_requires_team",
        "native_channels",
        "channel_group_id IS NULL OR team_id IS NOT NULL",
    )
    op.create_index(
        "ix_native_channel_org_team_group",
        "native_channels",
        ["organization_id", "team_id", "channel_group_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_native_channel_org_team_group", table_name="native_channels")
    op.drop_constraint(
        "ck_native_channel_group_requires_team",
        "native_channels",
        type_="check",
    )
    op.drop_constraint(
        "fk_native_channel_group_scope",
        "native_channels",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_native_channel_team_scope",
        "native_channels",
        type_="foreignkey",
    )
    op.drop_column("native_channels", "channel_group_id")
    op.drop_column("native_channels", "team_id")
    op.drop_index(
        "ix_native_channel_group_org_team_status_name",
        table_name="native_channel_groups",
    )
    op.drop_table("native_channel_groups")
