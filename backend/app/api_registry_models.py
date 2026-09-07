import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    BigInteger,
    Boolean,
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


class APIGrantStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"
    REVOKING = "revoking"
    REVOKE_FAILED = "revoke_failed"
    REVOKED = "revoked"
    EXPIRED = "expired"


class APIGrantHistoryAction(StrEnum):
    CREATED = "created"
    OWNER_CHANGED = "owner_changed"
    SCOPES_CHANGED = "scopes_changed"
    ENVIRONMENT_CHANGED = "environment_changed"
    ENABLED = "enabled"
    DISABLED = "disabled"
    CREDENTIAL_ROTATED = "credential_rotated"
    REVOKE_STARTED = "revoke_started"
    REVOKE_FAILED = "revoke_failed"
    REVOKED = "revoked"
    EXPIRED = "expired"


class APIService(Base):
    __tablename__ = "api_services"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "service_key",
            name="uq_api_service_org_key",
        ),
        Index("ix_api_services_org_created", "organization_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    service_key: Mapped[str] = mapped_column(String(64), nullable=False)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    provider_name: Mapped[str] = mapped_column(String(160), nullable=False)
    base_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
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


class APICredentialGrant(Base):
    __tablename__ = "api_credential_grants"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "grant_key",
            name="uq_api_grant_org_key",
        ),
        Index("ix_api_grants_org_status", "organization_id", "status"),
        Index("ix_api_grants_org_owner", "organization_id", "owner_user_id"),
        Index("ix_api_grants_org_expiry", "organization_id", "expires_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    service_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("api_services.id", ondelete="CASCADE"), nullable=False
    )
    grant_key: Mapped[str] = mapped_column(String(96), nullable=False)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    environment: Mapped[str] = mapped_column(String(64), nullable=False)
    scopes: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    secret_ref: Mapped[str | None] = mapped_column(String(512), nullable=True)
    status: Mapped[APIGrantStatus] = mapped_column(
        Enum(APIGrantStatus, native_enum=False, length=24),
        default=APIGrantStatus.ACTIVE,
        nullable=False,
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    credential_rotated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    usage_count: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    last_usage_success: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    last_usage_latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
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
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    expired_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class APIGrantHistory(Base):
    __tablename__ = "api_grant_history"
    __table_args__ = (
        Index("ix_api_grant_history_grant_created", "grant_id", "created_at"),
        Index("ix_api_grant_history_org_created", "organization_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    grant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("api_credential_grants.id", ondelete="CASCADE"), nullable=False
    )
    action: Mapped[APIGrantHistoryAction] = mapped_column(
        Enum(APIGrantHistoryAction, native_enum=False, length=32), nullable=False
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    previous_status: Mapped[str | None] = mapped_column(String(24), nullable=True)
    new_status: Mapped[str | None] = mapped_column(String(24), nullable=True)
    previous_owner_user_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    new_owner_user_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    previous_scopes: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    new_scopes: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    previous_environment: Mapped[str | None] = mapped_column(String(64), nullable=True)
    new_environment: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reason: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class APIUsageObservation(Base):
    __tablename__ = "api_usage_observations"
    __table_args__ = (
        UniqueConstraint(
            "grant_id",
            "observation_key",
            name="uq_api_usage_grant_observation",
        ),
        Index("ix_api_usage_org_observed", "organization_id", "observed_at"),
        Index("ix_api_usage_grant_observed", "grant_id", "observed_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    grant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("api_credential_grants.id", ondelete="CASCADE"), nullable=False
    )
    observation_key: Mapped[str] = mapped_column(String(160), nullable=False)
    caller_component: Mapped[str] = mapped_column(String(128), nullable=False)
    operation_label: Mapped[str | None] = mapped_column(String(160), nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
