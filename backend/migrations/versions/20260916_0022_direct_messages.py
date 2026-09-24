"""Participant-scoped Brain direct messages.

Revision ID: 20260916_0022
Revises: 20260916_0021
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260916_0022"
down_revision: str | None = "20260916_0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "direct_conversations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("participant_a_user_id", sa.Uuid(), nullable=False),
        sa.Column("participant_b_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "participant_a_user_id <> participant_b_user_id",
            name="ck_direct_conversation_distinct_participants",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["participant_a_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["participant_b_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "participant_a_user_id",
            "participant_b_user_id",
            name="uq_direct_conversation_org_pair",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "id",
            name="uq_direct_conversation_org_id",
        ),
    )
    op.create_index(
        "ix_direct_conversation_org_a_created",
        "direct_conversations",
        ["organization_id", "participant_a_user_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_direct_conversation_org_b_created",
        "direct_conversations",
        ["organization_id", "participant_b_user_id", "created_at"],
        unique=False,
    )

    op.create_table(
        "direct_messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("author_user_id", sa.Uuid(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("body_sha256", sa.String(length=64), nullable=False),
        sa.Column("body_char_count", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("body_char_count > 0", name="ck_direct_message_body_chars"),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "conversation_id"],
            ["direct_conversations.organization_id", "direct_conversations.id"],
            ondelete="CASCADE",
            name="fk_direct_message_org_conversation",
        ),
        sa.ForeignKeyConstraint(
            ["author_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "conversation_id",
            "idempotency_key",
            name="uq_direct_message_conversation_idempotency",
        ),
    )
    op.create_index(
        "ix_direct_message_org_conversation_created",
        "direct_messages",
        ["organization_id", "conversation_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_direct_message_org_conversation_created",
        table_name="direct_messages",
    )
    op.drop_table("direct_messages")
    op.drop_index(
        "ix_direct_conversation_org_b_created",
        table_name="direct_conversations",
    )
    op.drop_index(
        "ix_direct_conversation_org_a_created",
        table_name="direct_conversations",
    )
    op.drop_table("direct_conversations")
