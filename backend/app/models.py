import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class MembershipRole(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    EXECUTIVE = "executive"
    MANAGER = "manager"
    MEMBER = "member"
    GUEST = "guest"


class ResourceAccessLevel(StrEnum):
    READ = "read"
    WRITE = "write"


class IntegrationStatus(StrEnum):
    ACTIVE = "active"
    REVOKING = "revoking"
    REVOKE_FAILED = "revoke_failed"
    REVOKED = "revoked"


class IntegrationHealth(StrEnum):
    UNKNOWN = "unknown"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    ERROR = "error"


class RawEventStatus(StrEnum):
    RECEIVED = "received"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"
    QUARANTINED = "quarantined"


class SourceIdentityState(StrEnum):
    UNRESOLVED = "unresolved"
    RESOLVED = "resolved"
    REVIEW_REQUIRED = "review_required"


class Organization(Base):
    __tablename__ = "organizations"
    __table_args__ = (
        UniqueConstraint("slug", name="organizations_slug_key"),
        Index("ix_organizations_slug", "slug", unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(80))
    name: Mapped[str] = mapped_column(String(160))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    memberships: Mapped[list["Membership"]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("email", name="users_email_key"),
        Index("ix_users_email", "email", unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320))
    display_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    memberships: Mapped[list["Membership"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    external_identities: Mapped[list["ExternalIdentity"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class ExternalIdentity(Base):
    __tablename__ = "external_identities"
    __table_args__ = (
        UniqueConstraint("provider", "subject", name="uq_external_identity_provider_subject"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped[User] = relationship(back_populates="external_identities")


class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = (
        UniqueConstraint("organization_id", "user_id", name="uq_membership_org_user"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[MembershipRole] = mapped_column(
        Enum(MembershipRole, native_enum=False, length=32),
        default=MembershipRole.MEMBER,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    organization: Mapped[Organization] = relationship(back_populates="memberships")
    user: Mapped[User] = relationship(back_populates="memberships")


class ResourceGrant(Base):
    __tablename__ = "resource_grants"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "resource_type",
            "resource_id",
            "user_id",
            "access",
            name="uq_resource_grant_scope_user_access",
        ),
        Index(
            "ix_resource_grants_org_resource",
            "organization_id",
            "resource_type",
            "resource_id",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(255), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    access: Mapped[ResourceAccessLevel] = mapped_column(
        Enum(ResourceAccessLevel, native_enum=False, length=16),
        nullable=False,
    )
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class IntegrationConnection(Base):
    __tablename__ = "integration_connections"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "provider",
            "external_account_id",
            name="uq_integration_org_provider_account",
        ),
        Index("ix_integration_connections_org_status", "organization_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    external_account_id: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[IntegrationStatus] = mapped_column(
        Enum(IntegrationStatus, native_enum=False, length=32),
        default=IntegrationStatus.ACTIVE,
        nullable=False,
    )
    health: Mapped[IntegrationHealth] = mapped_column(
        Enum(IntegrationHealth, native_enum=False, length=16),
        default=IntegrationHealth.UNKNOWN,
        nullable=False,
    )
    scopes: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    provider_metadata: Mapped[dict[str, object]] = mapped_column(
        JSON, default=dict, nullable=False
    )
    secret_ref: Mapped[str | None] = mapped_column(String(512), nullable=True)
    sync_cursor: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SlackChannelAuthorization(Base):
    __tablename__ = "slack_channel_authorizations"
    __table_args__ = (
        UniqueConstraint(
            "integration_connection_id",
            "channel_id",
            name="uq_slack_channel_connection_channel",
        ),
        Index(
            "ix_slack_channel_authorizations_org_channel",
            "organization_id",
            "channel_id",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    integration_connection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("integration_connections.id", ondelete="CASCADE"), index=True
    )
    channel_id: Mapped[str] = mapped_column(String(64), nullable=False)
    channel_name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_private: Mapped[bool] = mapped_column(Boolean, nullable=False)
    member_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    backfill_cursor: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    backfill_complete: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_backfilled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    authorized_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class RawEvent(Base):
    __tablename__ = "raw_events"
    __table_args__ = (
        UniqueConstraint(
            "integration_connection_id",
            "source_event_id",
            name="uq_raw_event_connection_source_event",
        ),
        Index("ix_raw_events_org_received", "organization_id", "received_at"),
        Index("ix_raw_events_status_received", "processing_status", "received_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    integration_connection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("integration_connections.id", ondelete="CASCADE"), index=True
    )
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    source_event_id: Mapped[str] = mapped_column(String(255), nullable=False)
    source_event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    delivery_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    source_timestamp: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    content_type: Mapped[str] = mapped_column(String(128), nullable=False)
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_payload: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    source_visibility: Mapped[str] = mapped_column(String(32), nullable=False)
    source_acl: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    processing_status: Mapped[RawEventStatus] = mapped_column(
        Enum(RawEventStatus, native_enum=False, length=24),
        default=RawEventStatus.RECEIVED,
        nullable=False,
    )
    processing_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class SourceIdentity(Base):
    __tablename__ = "source_identities"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "provider",
            "external_id",
            name="uq_source_identity_org_provider_external",
        ),
        Index("ix_source_identities_org_state", "organization_id", "state"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    state: Mapped[SourceIdentityState] = mapped_column(
        Enum(SourceIdentityState, native_enum=False, length=32),
        default=SourceIdentityState.UNRESOLVED,
        nullable=False,
    )
    resolved_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=True
    )
    resolution_method: Mapped[str | None] = mapped_column(String(32), nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class CanonicalEvent(Base):
    __tablename__ = "canonical_events"
    __table_args__ = (
        UniqueConstraint("raw_event_id", name="uq_canonical_event_raw_event"),
        Index("ix_canonical_events_org_occurred", "organization_id", "occurred_at"),
        Index("ix_canonical_events_org_type", "organization_id", "event_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    raw_event_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("raw_events.id", ondelete="CASCADE"), nullable=False
    )
    integration_connection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("integration_connections.id", ondelete="CASCADE"), index=True
    )
    source_identity_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("source_identities.id", ondelete="SET NULL"), index=True, nullable=True
    )
    resolved_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    actor_display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    object_type: Mapped[str] = mapped_column(String(64), nullable=False)
    object_external_id: Mapped[str] = mapped_column(String(512), nullable=False)
    object_display_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    source_provider: Mapped[str] = mapped_column(String(40), nullable=False)
    source_event_id: Mapped[str] = mapped_column(String(255), nullable=False)
    source_event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    occurred_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    source_visibility: Mapped[str] = mapped_column(String(32), nullable=False)
    source_acl: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    provenance: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    event_metadata: Mapped[dict[str, object]] = mapped_column(
        "metadata", JSON, default=dict, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class SourceIdentityObservation(Base):
    __tablename__ = "source_identity_observations"
    __table_args__ = (
        UniqueConstraint(
            "canonical_event_id",
            name="uq_source_identity_observation_canonical_event",
        ),
        Index("ix_source_identity_observations_identity", "source_identity_id", "observed_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    source_identity_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("source_identities.id", ondelete="CASCADE"), index=True
    )
    canonical_event_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("canonical_events.id", ondelete="CASCADE"), nullable=False
    )
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    evidence: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class IdentityResolutionHistory(Base):
    __tablename__ = "identity_resolution_history"
    __table_args__ = (
        Index("ix_identity_resolution_history_identity", "source_identity_id", "created_at"),
        Index("ix_identity_resolution_history_org", "organization_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    source_identity_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("source_identities.id", ondelete="CASCADE"), index=True
    )
    previous_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    new_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    method: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    evidence: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
