"""Add provider metadata and canonical events.

Revision ID: 20260906_0006
Revises: 20260906_0005
Create Date: 2026-09-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260906_0006"
down_revision: str | None = "20260906_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "integration_connections",
        sa.Column(
            "provider_metadata",
            sa.JSON(),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
    )
    op.alter_column(
        "integration_connections",
        "provider_metadata",
        server_default=None,
    )

    op.create_table(
        "canonical_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("raw_event_id", sa.Uuid(), nullable=False),
        sa.Column("integration_connection_id", sa.Uuid(), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("actor_type", sa.String(length=64), nullable=False),
        sa.Column("actor_external_id", sa.String(length=255), nullable=True),
        sa.Column("actor_display_name", sa.String(length=255), nullable=True),
        sa.Column("object_type", sa.String(length=64), nullable=False),
        sa.Column("object_external_id", sa.String(length=512), nullable=False),
        sa.Column("object_display_name", sa.String(length=512), nullable=True),
        sa.Column("source_provider", sa.String(length=40), nullable=False),
        sa.Column("source_event_id", sa.String(length=255), nullable=False),
        sa.Column("source_event_type", sa.String(length=128), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_visibility", sa.String(length=32), nullable=False),
        sa.Column("source_acl", sa.JSON(), nullable=False),
        sa.Column("provenance", sa.JSON(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["raw_event_id"], ["raw_events.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["integration_connection_id"],
            ["integration_connections.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("raw_event_id", name="uq_canonical_event_raw_event"),
    )
    op.create_index(
        "ix_canonical_events_organization_id",
        "canonical_events",
        ["organization_id"],
    )
    op.create_index(
        "ix_canonical_events_integration_connection_id",
        "canonical_events",
        ["integration_connection_id"],
    )
    op.create_index(
        "ix_canonical_events_org_occurred",
        "canonical_events",
        ["organization_id", "occurred_at"],
    )
    op.create_index(
        "ix_canonical_events_org_type",
        "canonical_events",
        ["organization_id", "event_type"],
    )


def downgrade() -> None:
    op.drop_index("ix_canonical_events_org_type", table_name="canonical_events")
    op.drop_index("ix_canonical_events_org_occurred", table_name="canonical_events")
    op.drop_index(
        "ix_canonical_events_integration_connection_id",
        table_name="canonical_events",
    )
    op.drop_index("ix_canonical_events_organization_id", table_name="canonical_events")
    op.drop_table("canonical_events")
    op.drop_column("integration_connections", "provider_metadata")
