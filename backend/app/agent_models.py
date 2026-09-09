import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class AgentToolPolicyMode(StrEnum):
    READ = "read"
    ACT = "act"
    ACT_WITH_APPROVAL = "act_with_approval"
    DENY = "deny"


class AgentRunStatus(StrEnum):
    READY = "ready"
    PLANNING = "planning"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    STEP_LIMIT = "step_limit"


class AgentStepStatus(StrEnum):
    WAITING_APPROVAL = "waiting_approval"
    APPROVED = "approved"
    EXECUTING = "executing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DENIED = "denied"
    REJECTED = "rejected"
    EXPIRED = "expired"


class AgentDefinition(Base):
    __tablename__ = "agent_definitions"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_agent_definition_org_name"),
        CheckConstraint("max_steps >= 1 AND max_steps <= 20", name="ck_agent_max_steps"),
        Index("ix_agent_definition_org_enabled", "organization_id", "enabled"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    provider_configuration_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ai_provider_configurations.id", ondelete="RESTRICT"), nullable=False
    )
    model_configuration_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ai_model_configurations.id", ondelete="RESTRICT"), nullable=False
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    max_steps: Mapped[int] = mapped_column(Integer, default=8, nullable=False)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class AgentToolPolicy(Base):
    __tablename__ = "agent_tool_policies"
    __table_args__ = (
        UniqueConstraint("agent_definition_id", "tool_name", name="uq_agent_tool_policy"),
        Index("ix_agent_tool_policy_org_agent", "organization_id", "agent_definition_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    agent_definition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agent_definitions.id", ondelete="CASCADE"), nullable=False
    )
    tool_name: Mapped[str] = mapped_column(String(128), nullable=False)
    policy: Mapped[AgentToolPolicyMode] = mapped_column(
        Enum(AgentToolPolicyMode, native_enum=False, length=24), nullable=False
    )
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AgentRun(Base):
    __tablename__ = "agent_runs"
    __table_args__ = (
        CheckConstraint("objective_char_count > 0", name="ck_agent_run_objective_chars"),
        CheckConstraint("step_count >= 0", name="ck_agent_run_step_count"),
        Index("ix_agent_run_org_created", "organization_id", "created_at"),
        Index("ix_agent_run_requester_created", "requested_by_user_id", "created_at"),
        Index("ix_agent_run_org_status", "organization_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    agent_definition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agent_definitions.id", ondelete="RESTRICT"), nullable=False
    )
    requested_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[AgentRunStatus] = mapped_column(
        Enum(AgentRunStatus, native_enum=False, length=24),
        default=AgentRunStatus.READY,
        nullable=False,
    )
    objective_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    objective_char_count: Mapped[int] = mapped_column(Integer, nullable=False)
    step_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    planning_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    final_output_sha256: Mapped[str | None] = mapped_column(String(64))
    last_error_code: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AgentStep(Base):
    __tablename__ = "agent_steps"
    __table_args__ = (
        UniqueConstraint("run_id", "sequence", name="uq_agent_step_run_sequence"),
        CheckConstraint("sequence > 0", name="ck_agent_step_sequence"),
        Index("ix_agent_step_org_run", "organization_id", "run_id", "sequence"),
        Index("ix_agent_step_org_status", "organization_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    tool_name: Mapped[str] = mapped_column(String(128), nullable=False)
    policy: Mapped[AgentToolPolicyMode] = mapped_column(
        Enum(AgentToolPolicyMode, native_enum=False, length=24), nullable=False
    )
    status: Mapped[AgentStepStatus] = mapped_column(
        Enum(AgentStepStatus, native_enum=False, length=24), nullable=False
    )
    arguments_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)
    arguments_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    proposal_reason: Mapped[str | None] = mapped_column(String(500))
    result_sha256: Mapped[str | None] = mapped_column(String(64))
    result_metadata: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    approval_reason: Mapped[str | None] = mapped_column(String(500))
    approval_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(128))
    proposed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    execution_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
