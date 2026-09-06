"""Add tenant-scoped source identity resolution.

Revision ID: 20260906_0007
Revises: 20260906_0006
Create Date: 2026-09-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260906_0007"
down_revision: str | None = "20260906_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    state_enum = sa.Enum(
        "UNRESOLVED",
        "RESOLVED",
        "REVIEW_REQUIRED",
        name="sourceidentitystate",
        native_enum=False,
        length=32,
    )
    op.create_table(
        "source_identities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("email_verified", sa.Boolean(), nullable=False),
        sa.Column("state", state_enum, nullable=False),
        sa.Column("resolved_user_id", sa.Uuid(), nullable=True),
        sa.Column("resolution_method", sa.String(length=32), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
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
        sa.ForeignKeyConstraint(["resolved_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "provider",
            "external_id",
            name="uq_source_identity_org_provider_external",
        ),
    )
    op.create_index(
        "ix_source_identities_organization_id",
        "source_identities",
        ["organization_id"],
    )
    op.create_index(
        "ix_source_identities_resolved_user_id",
        "source_identities",
        ["resolved_user_id"],
    )
    op.create_index(
        "ix_source_identities_org_state",
        "source_identities",
        ["organization_id", "state"],
    )

    op.add_column("canonical_events", sa.Column("source_identity_id", sa.Uuid(), nullable=True))
    op.add_column("canonical_events", sa.Column("resolved_user_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_canonical_events_source_identity_id",
        "canonical_events",
        "source_identities",
        ["source_identity_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_canonical_events_resolved_user_id",
        "canonical_events",
        "users",
        ["resolved_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_canonical_events_source_identity_id",
        "canonical_events",
        ["source_identity_id"],
    )
    op.create_index(
        "ix_canonical_events_resolved_user_id",
        "canonical_events",
        ["resolved_user_id"],
    )

    op.create_table(
        "source_identity_observations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_identity_id", sa.Uuid(), nullable=False),
        sa.Column("canonical_event_id", sa.Uuid(), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("email_verified", sa.Boolean(), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["source_identity_id"], ["source_identities.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["canonical_event_id"], ["canonical_events.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "canonical_event_id",
            name="uq_source_identity_observation_canonical_event",
        ),
    )
    op.create_index(
        "ix_source_identity_observations_source_identity_id",
        "source_identity_observations",
        ["source_identity_id"],
    )
    op.create_index(
        "ix_source_identity_observations_identity",
        "source_identity_observations",
        ["source_identity_id", "observed_at"],
    )

    op.create_table(
        "identity_resolution_history",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("source_identity_id", sa.Uuid(), nullable=False),
        sa.Column("previous_user_id", sa.Uuid(), nullable=True),
        sa.Column("new_user_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("method", sa.String(length=32), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("evidence", sa.JSON(), nullable=False),
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
            ["source_identity_id"], ["source_identities.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["previous_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["new_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_identity_resolution_history_organization_id",
        "identity_resolution_history",
        ["organization_id"],
    )
    op.create_index(
        "ix_identity_resolution_history_source_identity_id",
        "identity_resolution_history",
        ["source_identity_id"],
    )
    op.create_index(
        "ix_identity_resolution_history_identity",
        "identity_resolution_history",
        ["source_identity_id", "created_at"],
    )
    op.create_index(
        "ix_identity_resolution_history_org",
        "identity_resolution_history",
        ["organization_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_identity_resolution_history_org", table_name="identity_resolution_history")
    op.drop_index(
        "ix_identity_resolution_history_identity", table_name="identity_resolution_history"
    )
    op.drop_index(
        "ix_identity_resolution_history_source_identity_id",
        table_name="identity_resolution_history",
    )
    op.drop_index(
        "ix_identity_resolution_history_organization_id",
        table_name="identity_resolution_history",
    )
    op.drop_table("identity_resolution_history")

    op.drop_index(
        "ix_source_identity_observations_identity",
        table_name="source_identity_observations",
    )
    op.drop_index(
        "ix_source_identity_observations_source_identity_id",
        table_name="source_identity_observations",
    )
    op.drop_table("source_identity_observations")

    op.drop_index("ix_canonical_events_resolved_user_id", table_name="canonical_events")
    op.drop_index("ix_canonical_events_source_identity_id", table_name="canonical_events")
    op.drop_constraint(
        "fk_canonical_events_resolved_user_id",
        "canonical_events",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_canonical_events_source_identity_id",
        "canonical_events",
        type_="foreignkey",
    )
    op.drop_column("canonical_events", "resolved_user_id")
    op.drop_column("canonical_events", "source_identity_id")

    op.drop_index("ix_source_identities_org_state", table_name="source_identities")
    op.drop_index("ix_source_identities_resolved_user_id", table_name="source_identities")
    op.drop_index("ix_source_identities_organization_id", table_name="source_identities")
    op.drop_table("source_identities")
