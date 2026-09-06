"""Add scoped integration connections.

Revision ID: 20260906_0004
Revises: 20260906_0003
Create Date: 2026-09-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260906_0004"
down_revision: str | None = "20260906_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    status_enum = sa.Enum(
        "ACTIVE",
        "REVOKING",
        "REVOKE_FAILED",
        "REVOKED",
        name="integrationstatus",
        native_enum=False,
        length=32,
    )
    health_enum = sa.Enum(
        "UNKNOWN",
        "HEALTHY",
        "DEGRADED",
        "ERROR",
        name="integrationhealth",
        native_enum=False,
        length=16,
    )
    op.create_table(
        "integration_connections",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("external_account_id", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=160), nullable=False),
        sa.Column("status", status_enum, nullable=False),
        sa.Column("health", health_enum, nullable=False),
        sa.Column("scopes", sa.JSON(), nullable=False),
        sa.Column("secret_ref", sa.String(length=512), nullable=True),
        sa.Column("sync_cursor", sa.String(length=2048), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(length=128), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
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
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "provider",
            "external_account_id",
            name="uq_integration_org_provider_account",
        ),
    )
    op.create_index(
        "ix_integration_connections_organization_id",
        "integration_connections",
        ["organization_id"],
    )
    op.create_index(
        "ix_integration_connections_org_status",
        "integration_connections",
        ["organization_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_integration_connections_org_status", table_name="integration_connections")
    op.drop_index(
        "ix_integration_connections_organization_id", table_name="integration_connections"
    )
    op.drop_table("integration_connections")
