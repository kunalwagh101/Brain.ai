import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base, ResourceAccessLevel


class NativeChannelVisibility(StrEnum):
    ORGANIZATION = "organization"
    RESTRICTED = "restricted"


class NativeChannelStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class NativeMessageActorKind(StrEnum):
    USER = "user"
    AGENT = "agent"


class NativeMessageProjectionStatus(StrEnum):
    PENDING = "pending"
    READY = "ready"
    FAILED = "failed"


class NativeChannel(Base):
    __tablename__ = "native_channels"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "slug",
            name="uq_native_channel_org_slug",
        ),
        UniqueConstraint(
            "work_graph_node_id",
            name="uq_native_channel_work_graph_node",
        ),
        Index(
            "ix_native_channel_org_status_created",
            "organization_id",
            "status",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    work_graph_node_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("work_graph_nodes.id", ondelete="RESTRICT"),
        nullable=True,
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    slug: Mapped[str] = mapped_column(String(96), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    visibility: Mapped[NativeChannelVisibility] = mapped_column(
        Enum(NativeChannelVisibility, native_enum=False, length=24),
        nullable=False,
    )
    status: Mapped[NativeChannelStatus] = mapped_column(
        Enum(NativeChannelStatus, native_enum=False, length=24),
        default=NativeChannelStatus.ACTIVE,
        nullable=False,
    )
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
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class NativeChannelMembership(Base):
    __tablename__ = "native_channel_memberships"
    __table_args__ = (
        UniqueConstraint(
            "channel_id",
            "user_id",
            name="uq_native_channel_membership_channel_user",
        ),
        Index(
            "ix_native_channel_membership_org_user_active",
            "organization_id",
            "user_id",
            "revoked_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    channel_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("native_channels.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    access: Mapped[ResourceAccessLevel] = mapped_column(
        Enum(ResourceAccessLevel, native_enum=False, length=16), nullable=False
    )
    granted_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class NativeMessage(Base):
    __tablename__ = "native_messages"
    __table_args__ = (
        UniqueConstraint(
            "channel_id",
            "idempotency_key",
            name="uq_native_message_channel_idempotency",
        ),
        UniqueConstraint(
            "canonical_event_id",
            name="uq_native_message_canonical_event",
        ),
        CheckConstraint("body_char_count > 0", name="ck_native_message_body_chars"),
        CheckConstraint(
            "(actor_kind = 'user' AND author_user_id IS NOT NULL AND agent_run_id IS NULL) OR "
            "(actor_kind = 'agent' AND author_user_id IS NULL AND agent_run_id IS NOT NULL)",
            name="ck_native_message_actor_identity",
        ),
        Index(
            "ix_native_message_org_channel_created",
            "organization_id",
            "channel_id",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    channel_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("native_channels.id", ondelete="CASCADE"), nullable=False
    )
    actor_kind: Mapped[NativeMessageActorKind] = mapped_column(
        Enum(NativeMessageActorKind, native_enum=False, length=16), nullable=False
    )
    author_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    agent_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="SET NULL"), nullable=True
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    body_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    body_char_count: Mapped[int] = mapped_column(nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    raw_event_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("raw_events.id", ondelete="SET NULL"), nullable=True
    )
    canonical_event_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("canonical_events.id", ondelete="SET NULL"), nullable=True
    )
    projection_status: Mapped[NativeMessageProjectionStatus] = mapped_column(
        Enum(NativeMessageProjectionStatus, native_enum=False, length=16),
        default=NativeMessageProjectionStatus.PENDING,
        nullable=False,
    )
    last_error_code: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
