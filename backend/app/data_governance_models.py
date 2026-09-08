import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    JSON,
    Boolean,
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


class RetentionRunStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class DeletionScope(StrEnum):
    INTEGRATION = "integration"
    SOURCE_OBJECT = "source_object"


class DeletionStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class OrganizationRetentionPolicy(Base):
    __tablename__ = "organization_retention_policies"
    __table_args__ = (
        UniqueConstraint("organization_id", name="uq_retention_policy_organization"),
        CheckConstraint(
            "raw_event_days IS NULL OR (raw_event_days >= 1 AND raw_event_days <= 36500)",
            name="ck_retention_policy_raw_days",
        ),
        CheckConstraint(
            "derived_content_days IS NULL OR "
            "(derived_content_days >= 1 AND derived_content_days <= 36500)",
            name="ck_retention_policy_derived_days",
        ),
        CheckConstraint(
            "audit_event_days IS NULL OR "
            "(audit_event_days >= 1 AND audit_event_days <= 36500)",
            name="ck_retention_policy_audit_days",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    raw_event_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    derived_content_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    audit_event_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    legal_hold: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    updated_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class SecurityAuditEvent(Base):
    __tablename__ = "security_audit_events"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "event_key",
            name="uq_security_audit_org_event_key",
        ),
        Index("ix_security_audit_org_created", "organization_id", "created_at"),
        Index("ix_security_audit_org_type", "organization_id", "event_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    event_key: Mapped[str] = mapped_column(String(255), nullable=False)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    resource_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(512), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    metadata_json: Mapped[dict[str, object]] = mapped_column(
        "metadata", JSON, default=dict, nullable=False
    )
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class RetentionRun(Base):
    __tablename__ = "retention_runs"
    __table_args__ = (
        Index("ix_retention_runs_org_started", "organization_id", "started_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[RetentionRunStatus] = mapped_column(
        Enum(RetentionRunStatus, native_enum=False, length=16),
        default=RetentionRunStatus.RUNNING,
        nullable=False,
    )
    raw_event_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    derived_content_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    audit_event_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    raw_events_deleted: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    derived_events_deleted: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    audit_events_deleted: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DataDeletionRequest(Base):
    __tablename__ = "data_deletion_requests"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "request_key",
            name="uq_data_deletion_org_request_key",
        ),
        Index("ix_data_deletion_org_status", "organization_id", "status"),
        Index("ix_data_deletion_org_created", "organization_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    request_key: Mapped[str] = mapped_column(String(128), nullable=False)
    scope: Mapped[DeletionScope] = mapped_column(
        Enum(DeletionScope, native_enum=False, length=32), nullable=False
    )
    integration_connection_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("integration_connections.id", ondelete="SET NULL"), nullable=True
    )
    source_provider: Mapped[str | None] = mapped_column(String(40), nullable=True)
    object_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    object_external_id: Mapped[str | None] = mapped_column(String(512), nullable=True)
    status: Mapped[DeletionStatus] = mapped_column(
        Enum(DeletionStatus, native_enum=False, length=16),
        default=DeletionStatus.PENDING,
        nullable=False,
    )
    requested_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    reason: Mapped[str] = mapped_column(String(512), nullable=False)
    raw_events_deleted: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    canonical_events_deleted: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completion_digest: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
