import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class ActivityKind(StrEnum):
    MENTION = "mention"
    THREAD_REPLY = "thread_reply"
    REACTION = "reaction"
    DIRECT_MESSAGE = "direct_message"
    AGENT_APPROVAL = "agent_approval"


class ActivityResourceType(StrEnum):
    NATIVE_MESSAGE = "native_message"
    DIRECT_MESSAGE = "direct_message"
    AGENT_RUN = "agent_run"


class ActivityNotification(Base):
    __tablename__ = "activity_notifications"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "recipient_user_id",
            "dedupe_key",
            name="uq_activity_notification_recipient_dedupe",
        ),
        Index(
            "ix_activity_notification_org_recipient_created",
            "organization_id",
            "recipient_user_id",
            "created_at",
        ),
        Index(
            "ix_activity_notification_org_recipient_read",
            "organization_id",
            "recipient_user_id",
            "read_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    recipient_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    kind: Mapped[ActivityKind] = mapped_column(
        Enum(
            ActivityKind,
            native_enum=False,
            length=32,
            values_callable=lambda values: [item.value for item in values],
        ),
        nullable=False,
    )
    resource_type: Mapped[ActivityResourceType] = mapped_column(
        Enum(
            ActivityResourceType,
            native_enum=False,
            length=32,
            values_callable=lambda values: [item.value for item in values],
        ),
        nullable=False,
    )
    resource_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    context_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    dedupe_key: Mapped[str] = mapped_column(String(192), nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
