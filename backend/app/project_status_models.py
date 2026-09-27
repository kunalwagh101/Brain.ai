import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class ProjectWorkState(StrEnum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    DONE = "done"


class ProjectProgressItem(Base):
    __tablename__ = "project_progress_items"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "project_node_id",
            "work_item_node_id",
            name="uq_project_progress_org_project_item",
        ),
        CheckConstraint("weight > 0 AND weight <= 10000", name="ck_project_progress_weight"),
        Index(
            "ix_project_progress_org_project",
            "organization_id",
            "project_node_id",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    project_node_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("work_graph_nodes.id", ondelete="CASCADE"), nullable=False
    )
    work_item_node_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("work_graph_nodes.id", ondelete="CASCADE"), nullable=False
    )
    state: Mapped[ProjectWorkState] = mapped_column(
        Enum(ProjectWorkState, native_enum=False, length=24),
        default=ProjectWorkState.NOT_STARTED,
        nullable=False,
    )
    weight: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    note: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    updated_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
