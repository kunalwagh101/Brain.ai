import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class NativeMessageMention(Base):
    __tablename__ = "native_message_mentions"
    __table_args__ = (
        UniqueConstraint(
            "message_id",
            "mentioned_user_id",
            name="uq_native_message_mention_message_user",
        ),
        Index(
            "ix_native_message_mention_org_user_created",
            "organization_id",
            "mentioned_user_id",
            "created_at",
        ),
        ForeignKeyConstraint(
            ["organization_id", "channel_id", "message_id"],
            [
                "native_messages.organization_id",
                "native_messages.channel_id",
                "native_messages.id",
            ],
            name="fk_native_message_mention_message_scope",
            ondelete="CASCADE",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    channel_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    message_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    mentioned_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class NativeMessageReaction(Base):
    __tablename__ = "native_message_reactions"
    __table_args__ = (
        UniqueConstraint(
            "message_id",
            "user_id",
            "reaction",
            name="uq_native_message_reaction_message_user_value",
        ),
        Index(
            "ix_native_message_reaction_org_message",
            "organization_id",
            "message_id",
        ),
        CheckConstraint(
            "reaction IN ('👍', '❤️', '🎉', '👀', '✅')",
            name="ck_native_reaction_allowed",
        ),
        ForeignKeyConstraint(
            ["organization_id", "channel_id", "message_id"],
            [
                "native_messages.organization_id",
                "native_messages.channel_id",
                "native_messages.id",
            ],
            name="fk_native_message_reaction_message_scope",
            ondelete="CASCADE",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    channel_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    message_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    reaction: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class NativeChannelReadState(Base):
    __tablename__ = "native_channel_read_states"
    __table_args__ = (
        UniqueConstraint(
            "channel_id",
            "user_id",
            name="uq_native_channel_read_state_channel_user",
        ),
        Index(
            "ix_native_channel_read_state_org_user",
            "organization_id",
            "user_id",
        ),
        ForeignKeyConstraint(
            ["organization_id", "channel_id", "last_read_message_id"],
            [
                "native_messages.organization_id",
                "native_messages.channel_id",
                "native_messages.id",
            ],
            name="fk_native_channel_read_state_message_scope",
            ondelete="CASCADE",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    channel_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    last_read_message_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    last_read_sequence: Mapped[int] = mapped_column(BigInteger, nullable=False)
    last_read_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class NativeThreadReadState(Base):
    __tablename__ = "native_thread_read_states"
    __table_args__ = (
        UniqueConstraint(
            "root_message_id",
            "user_id",
            name="uq_native_thread_read_state_root_user",
        ),
        Index(
            "ix_native_thread_read_state_org_user",
            "organization_id",
            "user_id",
        ),
        ForeignKeyConstraint(
            ["organization_id", "user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_native_thread_read_state_membership",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "channel_id", "root_message_id"],
            [
                "native_messages.organization_id",
                "native_messages.channel_id",
                "native_messages.id",
            ],
            name="fk_native_thread_read_state_root_scope",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "channel_id", "last_read_message_id"],
            [
                "native_messages.organization_id",
                "native_messages.channel_id",
                "native_messages.id",
            ],
            name="fk_native_thread_read_state_message_scope",
            ondelete="CASCADE",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    channel_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    root_message_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    last_read_message_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    last_read_sequence: Mapped[int] = mapped_column(BigInteger, nullable=False)
    last_read_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class NativeMessageAttachment(Base):
    __tablename__ = "native_message_attachments"
    __table_args__ = (
        UniqueConstraint(
            "message_id",
            "evidence_source_id",
            name="uq_native_message_attachment_message_source",
        ),
        Index(
            "ix_native_message_attachment_org_channel_message",
            "organization_id",
            "channel_id",
            "message_id",
        ),
        ForeignKeyConstraint(
            ["organization_id", "channel_id", "message_id"],
            [
                "native_messages.organization_id",
                "native_messages.channel_id",
                "native_messages.id",
            ],
            name="fk_native_message_attachment_message_scope",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "evidence_source_id"],
            ["evidence_sources.organization_id", "evidence_sources.id"],
            name="fk_native_message_attachment_evidence_scope",
            ondelete="RESTRICT",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    channel_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    message_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    evidence_source_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class NativeMessagePin(Base):
    __tablename__ = "native_message_pins"
    __table_args__ = (
        UniqueConstraint(
            "channel_id",
            "message_id",
            name="uq_native_message_pin_channel_message",
        ),
        Index(
            "ix_native_message_pin_org_channel_created",
            "organization_id",
            "channel_id",
            "created_at",
        ),
        ForeignKeyConstraint(
            ["organization_id", "channel_id", "message_id"],
            [
                "native_messages.organization_id",
                "native_messages.channel_id",
                "native_messages.id",
            ],
            name="fk_native_message_pin_message_scope",
            ondelete="CASCADE",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    channel_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    message_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    pinned_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class NativeMessageSave(Base):
    __tablename__ = "native_message_saves"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "message_id",
            name="uq_native_message_save_user_message",
        ),
        Index(
            "ix_native_message_save_org_user_created",
            "organization_id",
            "user_id",
            "created_at",
        ),
        ForeignKeyConstraint(
            ["organization_id", "user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_native_message_save_membership",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "channel_id", "message_id"],
            [
                "native_messages.organization_id",
                "native_messages.channel_id",
                "native_messages.id",
            ],
            name="fk_native_message_save_message_scope",
            ondelete="CASCADE",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    channel_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    message_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
