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
            "next_message_sequence >= 1 "
            "AND participant_a_visible_from_sequence >= 1 "
            "AND participant_b_visible_from_sequence >= 1 "
            "AND participant_a_visible_from_sequence <= next_message_sequence "
            "AND participant_b_visible_from_sequence <= next_message_sequence "
            "AND participant_a_last_read_sequence >= participant_a_visible_from_sequence - 1 "
            "AND participant_b_last_read_sequence >= participant_b_visible_from_sequence - 1 "
            "AND participant_a_last_read_sequence < next_message_sequence "
            "AND participant_b_last_read_sequence < next_message_sequence",
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
    participant_a_last_read_sequence: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    participant_b_last_read_sequence: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
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
            "organization_id",
            "conversation_id",
            "id",
            name="uq_direct_message_scope_id",
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
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    author_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    body_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    body_char_count: Mapped[int] = mapped_column(Integer, nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

class DirectMessageRevision(Base):
    __tablename__ = "direct_message_revisions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "conversation_id", "message_id"],
            [
                "direct_messages.organization_id",
                "direct_messages.conversation_id",
                "direct_messages.id",
            ],
            ondelete="CASCADE",
            name="fk_direct_message_revision_message_scope",
        ),
        UniqueConstraint(
            "message_id",
            "revision",
            name="uq_direct_message_revision_message_revision",
        ),
        CheckConstraint(
            "revision >= 1 AND body_char_count > 0 AND action IN ('edit', 'retract')",
            name="ck_direct_message_revision_bounds",
        ),
        Index(
            "ix_direct_message_revision_org_conversation_created",
            "organization_id",
            "conversation_id",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    conversation_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    message_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    body_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    body_char_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

class DirectMessageReaction(Base):
    __tablename__ = "direct_message_reactions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "conversation_id", "message_id"],
            [
                "direct_messages.organization_id",
                "direct_messages.conversation_id",
                "direct_messages.id",
            ],
            ondelete="CASCADE",
            name="fk_direct_message_reaction_message_scope",
        ),
        ForeignKeyConstraint(
            ["organization_id", "user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            ondelete="CASCADE",
            name="fk_direct_message_reaction_membership",
        ),
        UniqueConstraint(
            "message_id",
            "user_id",
            "reaction",
            name="uq_direct_message_reaction_message_user_value",
        ),
        CheckConstraint(
            "reaction IN ('👍', '❤️', '🎉', '👀', '✅')",
            name="ck_direct_message_reaction_allowed",
        ),
        Index(
            "ix_direct_message_reaction_org_message",
            "organization_id",
            "message_id",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    conversation_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    message_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    reaction: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

