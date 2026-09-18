import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class CollaborationPresenceLease(Base):
    __tablename__ = "collaboration_presence_leases"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "user_id",
            name="uq_collaboration_presence_org_user",
        ),
        ForeignKeyConstraint(
            ["organization_id", "user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_collaboration_presence_membership",
            ondelete="CASCADE",
        ),
        Index(
            "ix_collaboration_presence_org_expires",
            "organization_id",
            "expires_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CollaborationTypingLease(Base):
    __tablename__ = "collaboration_typing_leases"
    __table_args__ = (
        CheckConstraint(
            "(native_channel_id IS NOT NULL AND direct_conversation_id IS NULL) "
            "OR (native_channel_id IS NULL AND direct_conversation_id IS NOT NULL)",
            name="ck_collaboration_typing_exact_context",
        ),
        UniqueConstraint(
            "native_channel_id",
            "user_id",
            name="uq_collaboration_typing_channel_user",
        ),
        UniqueConstraint(
            "direct_conversation_id",
            "user_id",
            name="uq_collaboration_typing_dm_user",
        ),
        ForeignKeyConstraint(
            ["organization_id", "user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_collaboration_typing_membership",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "native_channel_id"],
            ["native_channels.organization_id", "native_channels.id"],
            name="fk_collaboration_typing_channel_scope",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "direct_conversation_id"],
            ["direct_conversations.organization_id", "direct_conversations.id"],
            name="fk_collaboration_typing_dm_scope",
            ondelete="CASCADE",
        ),
        Index(
            "ix_collaboration_typing_org_expires",
            "organization_id",
            "expires_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    native_channel_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    direct_conversation_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
