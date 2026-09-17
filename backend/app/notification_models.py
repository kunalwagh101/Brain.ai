import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, ForeignKey, Index, JSON, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


def _enum_values(enum_type):
    return [item.value for item in enum_type]


class NotificationKind(StrEnum):
    MENTION = "mention"
    THREAD_REPLY = "thread_reply"
    REACTION = "reaction"
    DIRECT_MESSAGE = "direct_message"


class WorkspaceNotification(Base):
    __tablename__ = "workspace_notifications"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "recipient_user_id",
            "dedupe_key",
            name="uq_workspace_notification_recipient_dedupe",
        ),
        Index(
            "ix_workspace_notification_org_recipient_created",
            "organization_id",
            "recipient_user_id",
            "created_at",
        ),
        Index(
            "ix_workspace_notification_org_recipient_read",
            "organization_id",
            "recipient_user_id",
            "read_at",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    recipient_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[NotificationKind] = mapped_column(
        Enum(
            NotificationKind,
            native_enum=False,
            length=32,
            values_callable=_enum_values,
        ),
        nullable=False,
    )
    dedupe_key: Mapped[str] = mapped_column(String(255), nullable=False)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    channel_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("native_channels.id", ondelete="CASCADE"), nullable=True
    )
    native_message_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("native_messages.id", ondelete="CASCADE"), nullable=True
    )
    direct_conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("direct_conversations.id", ondelete="CASCADE"), nullable=True
    )
    direct_message_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("direct_messages.id", ondelete="CASCADE"), nullable=True
    )
    event_metadata: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
