"""Governed agent runtime.

Revision ID: 20260909_0015
Revises: 20260908_0014
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260909_0015"
down_revision: str | None = "20260908_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_definitions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("provider_configuration_id", sa.Uuid(), nullable=False),
        sa.Column("model_configuration_id", sa.Uuid(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("max_steps", sa.Integer(), nullable=False),
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
        sa.CheckConstraint("max_steps >= 1 AND max_steps <= 20", name="ck_agent_max_steps"),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["provider_configuration_id"],
            ["ai_provider_configurations.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["model_configuration_id"],
            ["ai_model_configurations.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "name", name="uq_agent_definition_org_name"),
    )
    op.create_index(
        "ix_agent_definition_org_enabled",
        "agent_definitions",
        ["organization_id", "enabled"],
    )

    op.create_table(
        "agent_tool_policies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("agent_definition_id", sa.Uuid(), nullable=False),
        sa.Column("tool_name", sa.String(length=128), nullable=False),
        sa.Column("policy", sa.String(length=24), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
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
            ["agent_definition_id"], ["agent_definitions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agent_definition_id", "tool_name", name="uq_agent_tool_policy"),
    )
    op.create_index(
        "ix_agent_tool_policy_org_agent",
        "agent_tool_policies",
        ["organization_id", "agent_definition_id"],
    )

    op.create_table(
        "agent_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("agent_definition_id", sa.Uuid(), nullable=False),
        sa.Column("requested_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("objective_sha256", sa.String(length=64), nullable=False),
        sa.Column("objective_char_count", sa.Integer(), nullable=False),
        sa.Column("step_count", sa.Integer(), nullable=False),
        sa.Column("planning_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("final_output_sha256", sa.String(length=64), nullable=True),
        sa.Column("last_error_code", sa.String(length=128), nullable=True),
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
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("objective_char_count > 0", name="ck_agent_run_objective_chars"),
        sa.CheckConstraint("step_count >= 0", name="ck_agent_run_step_count"),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["agent_definition_id"], ["agent_definitions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["requested_by_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_agent_run_org_created", "agent_runs", ["organization_id", "created_at"]
    )
    op.create_index(
        "ix_agent_run_requester_created",
        "agent_runs",
        ["requested_by_user_id", "created_at"],
    )
    op.create_index(
        "ix_agent_run_org_status", "agent_runs", ["organization_id", "status"]
    )

    op.create_table(
        "agent_steps",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("tool_name", sa.String(length=128), nullable=False),
        sa.Column("policy", sa.String(length=24), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("arguments_json", sa.JSON(), nullable=False),
        sa.Column("arguments_sha256", sa.String(length=64), nullable=False),
        sa.Column("proposal_reason", sa.String(length=500), nullable=True),
        sa.Column("result_sha256", sa.String(length=64), nullable=True),
        sa.Column("result_metadata", sa.JSON(), nullable=False),
        sa.Column("approved_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("approval_reason", sa.String(length=500), nullable=True),
        sa.Column("approval_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=128), nullable=True),
        sa.Column(
            "proposed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("execution_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("sequence > 0", name="ck_agent_step_sequence"),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["approved_by_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "sequence", name="uq_agent_step_run_sequence"),
    )
    op.create_index(
        "ix_agent_step_org_run",
        "agent_steps",
        ["organization_id", "run_id", "sequence"],
    )
    op.create_index(
        "ix_agent_step_org_status", "agent_steps", ["organization_id", "status"]
    )


def downgrade() -> None:
    op.drop_index("ix_agent_step_org_status", table_name="agent_steps")
    op.drop_index("ix_agent_step_org_run", table_name="agent_steps")
    op.drop_table("agent_steps")
    op.drop_index("ix_agent_run_org_status", table_name="agent_runs")
    op.drop_index("ix_agent_run_requester_created", table_name="agent_runs")
    op.drop_index("ix_agent_run_org_created", table_name="agent_runs")
    op.drop_table("agent_runs")
    op.drop_index("ix_agent_tool_policy_org_agent", table_name="agent_tool_policies")
    op.drop_table("agent_tool_policies")
    op.drop_index("ix_agent_definition_org_enabled", table_name="agent_definitions")
    op.drop_table("agent_definitions")
