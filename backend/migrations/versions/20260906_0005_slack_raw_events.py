"""Add Slack channel authorisation and durable raw events.

Revision ID: 20260906_0005
Revises: 20260906_0004
Create Date: 2026-09-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260906_0005"
down_revision: str | None = "20260906_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    raw_status = sa.Enum(
        "RECEIVED",
        "PROCESSING",
        "PROCESSED",
        "FAILED",
        "QUARANTINED",
        name="raweventstatus",
        native_enum=False,
        length=24,
    )

    op.create_table(
        "slack_channel_authorizations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("integration_connection_id", sa.Uuid(), nullable=False),
        sa.Column("channel_id", sa.String(length=64), nullable=False),
        sa.Column("channel_name", sa.String(length=255), nullable=False),
        sa.Column("is_private", sa.Boolean(), nullable=False),
        sa.Column("member_ids", sa.JSON(), nullable=False),
        sa.Column("backfill_cursor", sa.String(length=2048), nullable=True),
        sa.Column("backfill_complete", sa.Boolean(), nullable=False),
        sa.Column("last_backfilled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("authorized_by_user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["integration_connection_id"],
            ["integration_connections.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["authorized_by_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "integration_connection_id",
            "channel_id",
            name="uq_slack_channel_connection_channel",
        ),
    )
    op.create_index(
        "ix_slack_channel_authorizations_organization_id",
        "slack_channel_authorizations",
        ["organization_id"],
    )
    op.create_index(
        "ix_slack_channel_authorizations_integration_connection_id",
        "slack_channel_authorizations",
        ["integration_connection_id"],
    )
    op.create_index(
        "ix_slack_channel_authorizations_org_channel",
        "slack_channel_authorizations",
        ["organization_id", "channel_id"],
    )

    op.create_table(
        "raw_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("integration_connection_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("source_event_id", sa.String(length=255), nullable=False),
        sa.Column("source_event_type", sa.String(length=128), nullable=False),
        sa.Column("delivery_kind", sa.String(length=32), nullable=False),
        sa.Column("source_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("content_type", sa.String(length=128), nullable=False),
        sa.Column("payload_sha256", sa.String(length=64), nullable=False),
        sa.Column("raw_payload", sa.LargeBinary(), nullable=False),
        sa.Column("source_visibility", sa.String(length=32), nullable=False),
        sa.Column("source_acl", sa.JSON(), nullable=False),
        sa.Column("processing_status", raw_status, nullable=False),
        sa.Column("processing_attempts", sa.Integer(), nullable=False),
        sa.Column("last_error_code", sa.String(length=128), nullable=True),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["integration_connection_id"],
            ["integration_connections.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "integration_connection_id",
            "source_event_id",
            name="uq_raw_event_connection_source_event",
        ),
    )
    op.create_index("ix_raw_events_organization_id", "raw_events", ["organization_id"])
    op.create_index(
        "ix_raw_events_integration_connection_id",
        "raw_events",
        ["integration_connection_id"],
    )
    op.create_index(
        "ix_raw_events_org_received",
        "raw_events",
        ["organization_id", "received_at"],
    )
    op.create_index(
        "ix_raw_events_status_received",
        "raw_events",
        ["processing_status", "received_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_raw_events_status_received", table_name="raw_events")
    op.drop_index("ix_raw_events_org_received", table_name="raw_events")
    op.drop_index("ix_raw_events_integration_connection_id", table_name="raw_events")
    op.drop_index("ix_raw_events_organization_id", table_name="raw_events")
    op.drop_table("raw_events")

    op.drop_index(
        "ix_slack_channel_authorizations_org_channel",
        table_name="slack_channel_authorizations",
    )
    op.drop_index(
        "ix_slack_channel_authorizations_integration_connection_id",
        table_name="slack_channel_authorizations",
    )
    op.drop_index(
        "ix_slack_channel_authorizations_organization_id",
        table_name="slack_channel_authorizations",
    )
    op.drop_table("slack_channel_authorizations")
