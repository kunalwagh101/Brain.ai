"""Brain native channels and messages.

Revision ID: 20260912_0019
Revises: 20260910_0018
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260912_0019"
down_revision: str | None = "20260910_0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "native_channels",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("work_graph_node_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("slug", sa.String(length=96), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("visibility", sa.String(length=24), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["work_graph_node_id"], ["work_graph_nodes.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "slug", name="uq_native_channel_org_slug"
        ),
        sa.UniqueConstraint(
            "work_graph_node_id", name="uq_native_channel_work_graph_node"
        ),
    )
    op.create_index(
        "ix_native_channel_org_status_created",
        "native_channels",
        ["organization_id", "status", "created_at"],
        unique=False,
    )

    op.create_table(
        "native_channel_memberships",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("channel_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("access", sa.String(length=16), nullable=False),
        sa.Column("granted_by_user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["channel_id"], ["native_channels.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["granted_by_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "channel_id",
            "user_id",
            name="uq_native_channel_membership_channel_user",
        ),
    )
    op.create_index(
        "ix_native_channel_membership_org_user_active",
        "native_channel_memberships",
        ["organization_id", "user_id", "revoked_at"],
        unique=False,
    )

    op.create_table(
        "native_messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("channel_id", sa.Uuid(), nullable=False),
        sa.Column("actor_kind", sa.String(length=16), nullable=False),
        sa.Column("author_user_id", sa.Uuid(), nullable=True),
        sa.Column("agent_run_id", sa.Uuid(), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("body_sha256", sa.String(length=64), nullable=False),
        sa.Column("body_char_count", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("raw_event_id", sa.Uuid(), nullable=True),
        sa.Column("canonical_event_id", sa.Uuid(), nullable=True),
        sa.Column("projection_status", sa.String(length=16), nullable=False),
        sa.Column("last_error_code", sa.String(length=128), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "body_char_count > 0",
            name="ck_native_message_body_chars",
        ),
        sa.CheckConstraint(
            "(actor_kind = 'user' AND author_user_id IS NOT NULL AND agent_run_id IS NULL) OR "
            "(actor_kind = 'agent' AND author_user_id IS NULL AND agent_run_id IS NOT NULL)",
            name="ck_native_message_actor_identity",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["channel_id"], ["native_channels.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["author_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["agent_run_id"], ["agent_runs.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["raw_event_id"], ["raw_events.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["canonical_event_id"], ["canonical_events.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "channel_id",
            "idempotency_key",
            name="uq_native_message_channel_idempotency",
        ),
        sa.UniqueConstraint(
            "canonical_event_id", name="uq_native_message_canonical_event"
        ),
    )
    op.create_index(
        "ix_native_message_org_channel_created",
        "native_messages",
        ["organization_id", "channel_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_native_message_org_channel_created",
        table_name="native_messages",
    )
    op.drop_table("native_messages")
    op.drop_index(
        "ix_native_channel_membership_org_user_active",
        table_name="native_channel_memberships",
    )
    op.drop_table("native_channel_memberships")
    op.drop_index(
        "ix_native_channel_org_status_created",
        table_name="native_channels",
    )
    op.drop_table("native_channels")
