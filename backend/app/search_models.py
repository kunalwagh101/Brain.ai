import json
import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import UserDefinedType

from app.models import Base


class Vector(UserDefinedType):
    """Minimal pgvector type without adding a Python dependency.

    PostgreSQL receives vector literals such as ``[0.1,0.2]``. SQLite accepts the
    declared type name and stores the same literal as text, which keeps unit tests
    portable without pretending SQLite is the production vector engine.
    """

    cache_ok = True

    def get_col_spec(self, **kw) -> str:  # noqa: ARG002
        return "vector"

    def bind_processor(self, dialect):  # noqa: ANN201, ARG002
        def process(value):
            if value is None or isinstance(value, str):
                return value
            return "[" + ",".join(format(float(item), ".12g") for item in value) + "]"

        return process

    def result_processor(self, dialect, coltype):  # noqa: ANN201, ARG002
        def process(value):
            if value is None or isinstance(value, list):
                return value
            if isinstance(value, str):
                text = value.strip()
                if text.startswith("[") and text.endswith("]"):
                    return [float(item) for item in text[1:-1].split(",") if item]
            return value

        return process


class SearchEmbeddingStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class SearchDocument(Base):
    __tablename__ = "search_documents"
    __table_args__ = (
        UniqueConstraint("canonical_event_id", name="uq_search_document_canonical_event"),
        Index("ix_search_documents_org_created", "organization_id", "created_at"),
        Index("ix_search_documents_org_provider", "organization_id", "source_provider"),
        Index("ix_search_documents_embedding_status", "embedding_status", "next_retry_at"),
        Index(
            "ix_search_documents_org_object",
            "organization_id",
            "integration_connection_id",
            "source_provider",
            "object_type",
            "object_external_id",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE")
    )
    canonical_event_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("canonical_events.id", ondelete="CASCADE"), nullable=False
    )
    integration_connection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("integration_connections.id", ondelete="CASCADE")
    )
    work_graph_node_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("work_graph_nodes.id", ondelete="SET NULL"), index=True, nullable=True
    )
    source_provider: Mapped[str] = mapped_column(String(40), nullable=False)
    source_visibility: Mapped[str] = mapped_column(String(32), nullable=False)
    source_acl: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    channel_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    repository_id: Mapped[str | None] = mapped_column(String(255), index=True, nullable=True)
    object_type: Mapped[str] = mapped_column(String(64), nullable=False)
    object_external_id: Mapped[str] = mapped_column(String(512), nullable=False)
    title: Mapped[str] = mapped_column(String(1024), default="", nullable=False)
    content: Mapped[str] = mapped_column(Text, default="", nullable=False)
    provenance: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_deleted: Mapped[bool] = mapped_column(default=False, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(), nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    embedding_status: Mapped[SearchEmbeddingStatus] = mapped_column(
        Enum(SearchEmbeddingStatus, native_enum=False, length=16),
        default=SearchEmbeddingStatus.PENDING,
        nullable=False,
    )
    embedding_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def searchable_text(self) -> str:
        return f"{self.title}\n{self.content}".strip()


def vector_literal(values: list[float]) -> str:
    return "[" + ",".join(format(float(item), ".12g") for item in values) + "]"


def vector_from_json(value: str) -> list[float]:
    parsed = json.loads(value)
    if not isinstance(parsed, list):
        raise ValueError("Embedding response is not a vector")
    return [float(item) for item in parsed]
