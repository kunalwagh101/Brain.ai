"""Audit, retention and deletion governance.

Revision ID: 20260908_0014
Revises: 20260907_0013
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260908_0014"
down_revision: str | None = "20260907_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "organization_retention_policies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("raw_event_days", sa.Integer(), nullable=True),
        sa.Column("derived_content_days", sa.Integer(), nullable=True),
        sa.Column("audit_event_days", sa.Integer(), nullable=True),
        sa.Column("legal_hold", sa.Boolean(), nullable=False),
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
            "raw_event_days IS NULL OR (raw_event_days >= 1 AND raw_event_days <= 36500)",
            name="ck_retention_policy_raw_days",
        ),
        sa.CheckConstraint(
            "derived_content_days IS NULL OR "
            "(derived_content_days >= 1 AND derived_content_days <= 36500)",
            name="ck_retention_policy_derived_days",
        ),
        sa.CheckConstraint(
            "audit_event_days IS NULL OR "
            "(audit_event_days >= 1 AND audit_event_days <= 36500)",
            name="ck_retention_policy_audit_days",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            name="uq_retention_policy_organization",
        ),
    )

    op.create_table(
        "security_audit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("event_key", sa.String(length=255), nullable=False),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("outcome", sa.String(length=32), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("resource_type", sa.String(length=128), nullable=True),
        sa.Column("resource_id", sa.String(length=512), nullable=True),
        sa.Column("request_id", sa.String(length=128), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("payload_sha256", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "event_key",
            name="uq_security_audit_org_event_key",
        ),
    )
    op.create_index(
        "ix_security_audit_org_created",
        "security_audit_events",
        ["organization_id", "created_at"],
    )
    op.create_index(
        "ix_security_audit_org_type",
        "security_audit_events",
        ["organization_id", "event_type"],
    )

    op.create_table(
        "retention_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("raw_event_days", sa.Integer(), nullable=True),
        sa.Column("derived_content_days", sa.Integer(), nullable=True),
        sa.Column("audit_event_days", sa.Integer(), nullable=True),
        sa.Column("raw_events_deleted", sa.Integer(), nullable=False),
        sa.Column("derived_events_deleted", sa.Integer(), nullable=False),
        sa.Column("audit_events_deleted", sa.Integer(), nullable=False),
        sa.Column("error_code", sa.String(length=128), nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "raw_events_deleted >= 0 AND derived_events_deleted >= 0 "
            "AND audit_events_deleted >= 0",
            name="ck_retention_run_nonnegative_counts",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_retention_runs_org_started",
        "retention_runs",
        ["organization_id", "started_at"],
    )

    op.create_table(
        "data_deletion_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("request_key", sa.String(length=128), nullable=False),
        sa.Column("scope", sa.String(length=32), nullable=False),
        sa.Column("target_reference", sa.String(length=768), nullable=False),
        sa.Column("integration_connection_id", sa.Uuid(), nullable=True),
        sa.Column("source_provider", sa.String(length=40), nullable=True),
        sa.Column("object_type", sa.String(length=64), nullable=True),
        sa.Column("object_external_id", sa.String(length=512), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("requested_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("reason", sa.String(length=512), nullable=False),
        sa.Column("raw_events_deleted", sa.Integer(), nullable=False),
        sa.Column("canonical_events_deleted", sa.Integer(), nullable=False),
        sa.Column("completion_digest", sa.String(length=64), nullable=True),
        sa.Column("error_code", sa.String(length=128), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "raw_events_deleted >= 0 AND canonical_events_deleted >= 0",
            name="ck_data_deletion_nonnegative_counts",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["integration_connection_id"],
            ["integration_connections.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["requested_by_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "request_key",
            name="uq_data_deletion_org_request_key",
        ),
    )
    op.create_index(
        "ix_data_deletion_org_status",
        "data_deletion_requests",
        ["organization_id", "status"],
    )
    op.create_index(
        "ix_data_deletion_org_created",
        "data_deletion_requests",
        ["organization_id", "created_at"],
    )

    op.create_table(
        "derived_retention_tombstones",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("raw_event_id", sa.Uuid(), nullable=False),
        sa.Column("source_provider", sa.String(length=40), nullable=False),
        sa.Column("object_type", sa.String(length=64), nullable=False),
        sa.Column("object_external_id", sa.String(length=512), nullable=False),
        sa.Column(
            "purged_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["raw_event_id"], ["raw_events.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("raw_event_id", name="uq_derived_retention_raw_event"),
    )
    op.create_index(
        "ix_derived_retention_org_purged",
        "derived_retention_tombstones",
        ["organization_id", "purged_at"],
    )
    op.create_index(
        "ix_derived_retention_org_object",
        "derived_retention_tombstones",
        [
            "organization_id",
            "source_provider",
            "object_type",
            "object_external_id",
        ],
    )

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            """
            CREATE FUNCTION brain_reject_security_audit_update()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            BEGIN
                RAISE EXCEPTION 'security_audit_events are append-only';
            END;
            $$
            """
        )
        op.execute(
            """
            CREATE TRIGGER trg_security_audit_events_no_update
            BEFORE UPDATE ON security_audit_events
            FOR EACH ROW
            EXECUTE FUNCTION brain_reject_security_audit_update()
            """
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            "DROP TRIGGER IF EXISTS trg_security_audit_events_no_update "
            "ON security_audit_events"
        )
        op.execute("DROP FUNCTION IF EXISTS brain_reject_security_audit_update()")

    op.drop_index(
        "ix_derived_retention_org_object",
        table_name="derived_retention_tombstones",
    )
    op.drop_index(
        "ix_derived_retention_org_purged",
        table_name="derived_retention_tombstones",
    )
    op.drop_table("derived_retention_tombstones")
    op.drop_index("ix_data_deletion_org_created", table_name="data_deletion_requests")
    op.drop_index("ix_data_deletion_org_status", table_name="data_deletion_requests")
    op.drop_table("data_deletion_requests")
    op.drop_index("ix_retention_runs_org_started", table_name="retention_runs")
    op.drop_table("retention_runs")
    op.drop_index("ix_security_audit_org_type", table_name="security_audit_events")
    op.drop_index("ix_security_audit_org_created", table_name="security_audit_events")
    op.drop_table("security_audit_events")
    op.drop_table("organization_retention_policies")
