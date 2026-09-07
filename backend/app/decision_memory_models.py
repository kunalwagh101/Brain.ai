import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class MemoryKind(StrEnum):
    DECISION = "decision"
    BLOCKER = "blocker"


class MemoryState(StrEnum):
    CANDIDATE = "candidate"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    RESOLVED = "resolved"
    SUPERSEDED = "superseded"


class MemoryReviewAction(StrEnum):
    CONFIRM = "confirm"
    REJECT = "reject"
    EDIT = "edit"
    RESOLVE = "resolve"
    REOPEN = "reopen"


class DecisionMemoryCandidate(Base):
    __tablename__ = "decision_memory_candidates"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "canonical_event_id",
            "kind",
            "fingerprint",
            name="uq_decision_memory_org_event_kind_fingerprint",
        ),
        CheckConstraint(
            "confidence >= 0.0 AND confidence <= 1.0",
            name="ck_decision_memory_confidence",
        ),
        Index(
            "ix_decision_memory_org_kind_state",
            "organization_id",
            "kind",
            "state",
        ),
        Index(
            "ix_decision_memory_org_created",
            "organization_id",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    canonical_event_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("canonical_events.id", ondelete="CASCADE"), nullable=False
    )
    search_document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("search_documents.id", ondelete="SET NULL"), nullable=True
    )
    work_graph_node_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("work_graph_nodes.id", ondelete="SET NULL"), nullable=True
    )
    kind: Mapped[MemoryKind] = mapped_column(
        Enum(MemoryKind, native_enum=False, length=16), nullable=False
    )
    state: Mapped[MemoryState] = mapped_column(
        Enum(MemoryState, native_enum=False, length=16),
        default=MemoryState.CANDIDATE,
        nullable=False,
    )
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    extraction_method: Mapped[str] = mapped_column(String(32), nullable=False)
    extraction_version: Mapped[str] = mapped_column(String(64), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
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


class DecisionMemoryExtraction(Base):
    __tablename__ = "decision_memory_extractions"
    __table_args__ = (
        UniqueConstraint(
            "search_document_id",
            name="uq_decision_memory_extraction_search_document",
        ),
        Index(
            "ix_decision_memory_extractions_org_processed",
            "organization_id",
            "processed_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    search_document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("search_documents.id", ondelete="CASCADE"), nullable=False
    )
    extraction_version: Mapped[str] = mapped_column(String(64), nullable=False)
    candidate_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class DecisionMemoryReview(Base):
    __tablename__ = "decision_memory_reviews"
    __table_args__ = (
        Index(
            "ix_decision_memory_reviews_candidate_created",
            "candidate_id",
            "created_at",
        ),
        Index(
            "ix_decision_memory_reviews_org_created",
            "organization_id",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("decision_memory_candidates.id", ondelete="CASCADE"), nullable=False
    )
    actor_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    action: Mapped[MemoryReviewAction] = mapped_column(
        Enum(MemoryReviewAction, native_enum=False, length=16), nullable=False
    )
    previous_state: Mapped[MemoryState] = mapped_column(
        Enum(MemoryState, native_enum=False, length=16), nullable=False
    )
    new_state: Mapped[MemoryState] = mapped_column(
        Enum(MemoryState, native_enum=False, length=16), nullable=False
    )
    previous_summary: Mapped[str] = mapped_column(Text, nullable=False)
    new_summary: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str] = mapped_column(String(1000), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
