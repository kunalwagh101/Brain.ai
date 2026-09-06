import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class WorkGraphNodeType(StrEnum):
    PERSON = "person"
    PROJECT = "project"
    TRACK = "track"
    WORK_ITEM = "work_item"
    EVIDENCE = "evidence"


class WorkGraphEdgeType(StrEnum):
    PERFORMED = "performed"
    RESOLVES_TO = "resolves_to"
    CONTAINS = "contains"
    SUPPORTED_BY = "supported_by"
    DEPENDS_ON = "depends_on"
    RELATED_TO = "related_to"


class WorkGraphEdgeSource(StrEnum):
    CANONICAL = "canonical"
    IDENTITY = "identity"
    MANUAL = "manual"
    INFERENCE = "inference"


class WorkGraphEvidenceState(StrEnum):
    VERIFIED = "verified"
    INFERRED = "inferred"


class WorkGraphNode(Base):
    __tablename__ = "work_graph_nodes"
    __table_args__ = (
        UniqueConstraint("organization_id", "stable_key", name="uq_work_graph_node_org_key"),
        UniqueConstraint("canonical_event_id", name="uq_work_graph_node_canonical_event"),
        Index("ix_work_graph_nodes_org_type", "organization_id", "node_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    node_type: Mapped[WorkGraphNodeType] = mapped_column(
        Enum(WorkGraphNodeType, native_enum=False, length=32), nullable=False
    )
    stable_key: Mapped[str] = mapped_column(String(512), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    canonical_event_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("canonical_events.id", ondelete="CASCADE"), index=True, nullable=True
    )
    source_identity_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("source_identities.id", ondelete="SET NULL"), index=True, nullable=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
    source_visibility: Mapped[str] = mapped_column(
        String(32), default="organization", nullable=False
    )
    source_acl: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    attributes: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class WorkGraphEdge(Base):
    __tablename__ = "work_graph_edges"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "provenance_key", name="uq_work_graph_edge_org_provenance"
        ),
        CheckConstraint(
            "confidence >= 0.0 AND confidence <= 1.0",
            name="ck_work_graph_edge_confidence",
        ),
        Index("ix_work_graph_edges_org_source", "organization_id", "source_node_id"),
        Index("ix_work_graph_edges_org_target", "organization_id", "target_node_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    source_node_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("work_graph_nodes.id", ondelete="CASCADE"), nullable=False
    )
    target_node_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("work_graph_nodes.id", ondelete="CASCADE"), nullable=False
    )
    edge_type: Mapped[WorkGraphEdgeType] = mapped_column(
        Enum(WorkGraphEdgeType, native_enum=False, length=32), nullable=False
    )
    source_kind: Mapped[WorkGraphEdgeSource] = mapped_column(
        Enum(WorkGraphEdgeSource, native_enum=False, length=24), nullable=False
    )
    evidence_state: Mapped[WorkGraphEvidenceState] = mapped_column(
        Enum(WorkGraphEvidenceState, native_enum=False, length=16), nullable=False
    )
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    provenance_key: Mapped[str] = mapped_column(String(512), nullable=False)
    provenance: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)
    canonical_event_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("canonical_events.id", ondelete="CASCADE"), index=True, nullable=True
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
