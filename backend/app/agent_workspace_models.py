import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class AgentRunContext(Base):
    __tablename__ = "agent_run_contexts"
    __table_args__ = (
        UniqueConstraint("run_id", name="uq_agent_run_context_run"),
        CheckConstraint(
            "project_node_id IS NOT NULL OR native_channel_id IS NOT NULL",
            name="ck_agent_run_context_has_scope",
        ),
        Index(
            "ix_agent_run_context_org_project",
            "organization_id",
            "project_node_id",
        ),
        Index(
            "ix_agent_run_context_org_channel",
            "organization_id",
            "native_channel_id",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False
    )
    project_node_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("work_graph_nodes.id", ondelete="SET NULL"), nullable=True
    )
    native_channel_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("native_channels.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
