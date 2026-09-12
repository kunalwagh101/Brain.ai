import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint, func
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
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    channel_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("native_channels.id", ondelete="CASCADE"), nullable=False
    )
    message_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("native_messages.id", ondelete="CASCADE"), nullable=False
    )
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
        CheckConstraint("length(reaction) > 0", name="ck_native_reaction_not_empty"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    channel_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("native_channels.id", ondelete="CASCADE"), nullable=False
    )
    message_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("native_messages.id", ondelete="CASCADE"), nullable=False
    )
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
    last_read_message_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("native_messages.id", ondelete="CASCADE"), nullable=False
    )
    last_read_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
