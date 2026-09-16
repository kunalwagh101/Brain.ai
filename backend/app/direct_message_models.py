import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class DirectConversation(Base):
    __tablename__ = "direct_conversations"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "participant_a_user_id",
            "participant_b_user_id",
            name="uq_direct_conversation_org_pair",
        ),
        UniqueConstraint(
            "organization_id",
            "id",
            name="uq_direct_conversation_org_id",
        ),
        CheckConstraint(
            "participant_a_user_id <> participant_b_user_id",
            name="ck_direct_conversation_distinct_participants",
        ),
        CheckConstraint(
            "next_message_sequence >= 1 AND participant_a_visible_from_sequence >= 1 "
            "AND participant_b_visible_from_sequence >= 1",
            name="ck_direct_conversation_sequence_bounds",
        ),
        Index(
            "ix_direct_conversation_org_a_created",
            "organization_id",
            "participant_a_user_id",
            "created_at",
        ),
        Index(
            "ix_direct_conversation_org_b_created",
            "organization_id",
            "participant_b_user_id",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    participant_a_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    participant_b_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    next_message_sequence: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    participant_a_visible_from_sequence: Mapped[int] = mapped_column(
        Integer, default=1, nullable=False
    )
    participant_b_visible_from_sequence: Mapped[int] = mapped_column(
        Integer, default=1, nullable=False
    )
    participant_a_revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    participant_b_revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
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


class DirectMessage(Base):
    __tablename__ = "direct_messages"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "conversation_id"],
            ["direct_conversations.organization_id", "direct_conversations.id"],
            ondelete="CASCADE",
            name="fk_direct_message_org_conversation",
        ),
        CheckConstraint(
            "body_char_count > 0 AND sequence >= 1",
            name="ck_direct_message_bounds",
        ),
        UniqueConstraint(
            "conversation_id",
            "sequence",
            name="uq_direct_message_conversation_sequence",
        ),
        UniqueConstraint(
            "conversation_id",
            "idempotency_key",
            name="uq_direct_message_conversation_idempotency",
        ),
        Index(
            "ix_direct_message_org_conversation_created",
            "organization_id",
            "conversation_id",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    conversation_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    author_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    body_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    body_char_count: Mapped[int] = mapped_column(Integer, nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
