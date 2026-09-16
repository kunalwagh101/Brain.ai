"""Revocable participant access and monotonic visibility epochs for Brain-native DMs.

Revision ID: 20260916_0024
Revises: 20260916_0023
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260916_0024"
down_revision: str | None = "20260916_0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "direct_conversations",
        sa.Column(
            "next_message_sequence",
            sa.Integer(),
            server_default=sa.text("1"),
            nullable=False,
        ),
    )
    op.add_column(
        "direct_conversations",
        sa.Column(
            "participant_a_visible_from_sequence",
            sa.Integer(),
            server_default=sa.text("1"),
            nullable=False,
        ),
    )
    op.add_column(
        "direct_conversations",
        sa.Column(
            "participant_b_visible_from_sequence",
            sa.Integer(),
            server_default=sa.text("1"),
            nullable=False,
        ),
    )
    op.add_column(
        "direct_conversations",
        sa.Column("participant_a_revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "direct_conversations",
        sa.Column("participant_b_revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "direct_messages",
        sa.Column("sequence", sa.Integer(), nullable=True),
    )

    op.execute(
        "WITH ranked AS ("
        " SELECT id, ROW_NUMBER() OVER ("
        "   PARTITION BY conversation_id ORDER BY created_at, id"
        " ) AS rn"
        " FROM direct_messages"
        ")"
        " UPDATE direct_messages AS message"
        " SET sequence = ranked.rn"
        " FROM ranked"
        " WHERE message.id = ranked.id"
    )
    op.alter_column(
        "direct_messages",
        "sequence",
        existing_type=sa.Integer(),
        nullable=False,
    )
    op.execute(
        "UPDATE direct_conversations AS conversation "
        "SET next_message_sequence = COALESCE(("
        " SELECT MAX(message.sequence) + 1"
        " FROM direct_messages AS message"
        " WHERE message.conversation_id = conversation.id"
        "), 1)"
    )

    op.drop_constraint(
        "ck_direct_message_body_chars",
        "direct_messages",
        type_="check",
    )
    op.create_check_constraint(
        "ck_direct_message_bounds",
        "direct_messages",
        "body_char_count > 0 AND sequence >= 1",
    )
    op.create_unique_constraint(
        "uq_direct_message_conversation_sequence",
        "direct_messages",
        ["conversation_id", "sequence"],
    )
    op.create_check_constraint(
        "ck_direct_conversation_sequence_bounds",
        "direct_conversations",
        "next_message_sequence >= 1 "
        "AND participant_a_visible_from_sequence >= 1 "
        "AND participant_b_visible_from_sequence >= 1",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_direct_conversation_sequence_bounds",
        "direct_conversations",
        type_="check",
    )
    op.drop_constraint(
        "uq_direct_message_conversation_sequence",
        "direct_messages",
        type_="unique",
    )
    op.drop_constraint(
        "ck_direct_message_bounds",
        "direct_messages",
        type_="check",
    )
    op.create_check_constraint(
        "ck_direct_message_body_chars",
        "direct_messages",
        "body_char_count > 0",
    )
    op.drop_column("direct_messages", "sequence")
    op.drop_column("direct_conversations", "participant_b_revoked_at")
    op.drop_column("direct_conversations", "participant_a_revoked_at")
    op.drop_column("direct_conversations", "participant_b_visible_from_sequence")
    op.drop_column("direct_conversations", "participant_a_visible_from_sequence")
    op.drop_column("direct_conversations", "next_message_sequence")
