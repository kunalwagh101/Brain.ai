"""External API registry

Revision ID: 20260907_0013
Revises: 20260907_0012
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260907_0013"
down_revision: str | None = "20260907_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "api_services",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("service_key", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=160), nullable=False),
        sa.Column("provider_name", sa.String(length=160), nullable=False),
        sa.Column("base_url", sa.String(length=2048), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "service_key",
            name="uq_api_service_org_key",
        ),
    )
    op.create_index(
        "ix_api_services_org_created",
        "api_services",
        ["organization_id", "created_at"],
    )

    op.create_table(
        "api_credential_grants",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("service_id", sa.Uuid(), nullable=False),
        sa.Column("grant_key", sa.String(length=96), nullable=False),
        sa.Column("display_name", sa.String(length=160), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("environment", sa.String(length=64), nullable=False),
        sa.Column("scopes", sa.JSON(), nullable=False),
        sa.Column("secret_ref", sa.String(length=512), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("credential_rotated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("usage_count", sa.BigInteger(), nullable=False),
        sa.Column("last_usage_success", sa.Boolean(), nullable=True),
        sa.Column("last_usage_latency_ms", sa.Integer(), nullable=True),
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
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expired_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("usage_count >= 0", name="ck_api_grant_usage_count"),
        sa.CheckConstraint(
            "last_usage_latency_ms IS NULL OR last_usage_latency_ms >= 0",
            name="ck_api_grant_latency_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["service_id"], ["api_services.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "grant_key",
            name="uq_api_grant_org_key",
        ),
    )
    op.create_index(
        "ix_api_grants_org_status",
        "api_credential_grants",
        ["organization_id", "status"],
    )
    op.create_index(
        "ix_api_grants_org_owner",
        "api_credential_grants",
        ["organization_id", "owner_user_id"],
    )
    op.create_index(
        "ix_api_grants_org_expiry",
        "api_credential_grants",
        ["organization_id", "expires_at"],
    )

    op.create_table(
        "api_grant_history",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("grant_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("previous_status", sa.String(length=24), nullable=True),
        sa.Column("new_status", sa.String(length=24), nullable=True),
        sa.Column("previous_owner_user_id", sa.Uuid(), nullable=True),
        sa.Column("new_owner_user_id", sa.Uuid(), nullable=True),
        sa.Column("previous_scopes", sa.JSON(), nullable=True),
        sa.Column("new_scopes", sa.JSON(), nullable=True),
        sa.Column("previous_environment", sa.String(length=64), nullable=True),
        sa.Column("new_environment", sa.String(length=64), nullable=True),
        sa.Column("reason", sa.String(length=512), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["grant_id"], ["api_credential_grants.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_api_grant_history_grant_created",
        "api_grant_history",
        ["grant_id", "created_at"],
    )
    op.create_index(
        "ix_api_grant_history_org_created",
        "api_grant_history",
        ["organization_id", "created_at"],
    )

    op.create_table(
        "api_usage_observations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("grant_id", sa.Uuid(), nullable=False),
        sa.Column("observation_key", sa.String(length=160), nullable=False),
        sa.Column("caller_component", sa.String(length=128), nullable=False),
        sa.Column("operation_label", sa.String(length=160), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "latency_ms IS NULL OR latency_ms >= 0",
            name="ck_api_usage_latency_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["grant_id"], ["api_credential_grants.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "grant_id",
            "observation_key",
            name="uq_api_usage_grant_observation",
        ),
    )
    op.create_index(
        "ix_api_usage_org_observed",
        "api_usage_observations",
        ["organization_id", "observed_at"],
    )
    op.create_index(
        "ix_api_usage_grant_observed",
        "api_usage_observations",
        ["grant_id", "observed_at"],
    )


def downgrade() -> None:
    op.drop_table("api_usage_observations")
    op.drop_table("api_grant_history")
    op.drop_table("api_credential_grants")
    op.drop_table("api_services")
