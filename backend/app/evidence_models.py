import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    LargeBinary,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class EvidenceKind(StrEnum):
    DOCUMENT = "document"
    TRANSCRIPT = "transcript"


class EvidenceVisibility(StrEnum):
    ORGANIZATION = "organization"
    RESTRICTED = "restricted"


class EvidenceSourceStatus(StrEnum):
    PROCESSING = "processing"
    ACTIVE = "active"
    FAILED = "failed"
    DELETED = "deleted"


class EvidenceSource(Base):
    __tablename__ = "evidence_sources"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "idempotency_key",
            name="uq_evidence_source_org_idempotency",
        ),
        CheckConstraint("byte_size >= 1", name="ck_evidence_source_positive_bytes"),
        CheckConstraint("chunk_count >= 0", name="ck_evidence_source_chunk_count"),
        CheckConstraint(
            "extracted_char_count >= 0",
            name="ck_evidence_source_extracted_char_count",
        ),
        Index(
            "ix_evidence_source_org_status_created",
            "organization_id",
            "status",
            "created_at",
        ),
        Index(
            "ix_evidence_source_org_sha",
            "organization_id",
            "content_sha256",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    integration_connection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("integration_connections.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[EvidenceKind] = mapped_column(
        Enum(EvidenceKind, native_enum=False, length=16), nullable=False
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    media_type: Mapped[str] = mapped_column(String(128), nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    byte_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    raw_content: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    source_visibility: Mapped[EvidenceVisibility] = mapped_column(
        Enum(EvidenceVisibility, native_enum=False, length=32), nullable=False
    )
    source_acl: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    chunk_count: Mapped[int] = mapped_column(default=0, nullable=False)
    extracted_char_count: Mapped[int] = mapped_column(default=0, nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[EvidenceSourceStatus] = mapped_column(
        Enum(EvidenceSourceStatus, native_enum=False, length=16),
        default=EvidenceSourceStatus.PROCESSING,
        nullable=False,
    )
    last_error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
