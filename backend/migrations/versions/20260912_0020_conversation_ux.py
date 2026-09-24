"""Conversation threads, mentions, reactions and per-user read state.

Revision ID: 20260912_0020
Revises: 20260912_0019
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260912_0020"
down_revision: str | None = "20260912_0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "native_channels",
        sa.Column(
            "last_message_sequence",
            sa.BigInteger(),
            server_default="0",
            nullable=False,
        ),
    )
    op.add_column(
        "native_messages",
        sa.Column("thread_root_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "native_messages",
        sa.Column("message_sequence", sa.BigInteger(), nullable=True),
    )

    # Assign a deterministic position to messages that pre-date this migration.
    op.execute(
        sa.text(
            """
            WITH ranked AS (
                SELECT id,
                       row_number() OVER (
                           PARTITION BY channel_id
                           ORDER BY created_at, id
                       ) AS message_sequence
                FROM native_messages
            )
            UPDATE native_messages AS message
            SET message_sequence = ranked.message_sequence
            FROM ranked
            WHERE message.id = ranked.id
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE native_channels AS channel
            SET last_message_sequence = COALESCE(
                (
                    SELECT MAX(message.message_sequence)
                    FROM native_messages AS message
                    WHERE message.channel_id = channel.id
                ),
                0
            )
            """
        )
    )
    op.alter_column(
        "native_messages",
        "message_sequence",
        existing_type=sa.BigInteger(),
        nullable=False,
    )
    op.create_unique_constraint(
        "uq_native_channel_org_id",
        "native_channels",
        ["organization_id", "id"],
    )
    op.create_unique_constraint(
        "uq_native_message_org_channel_id",
        "native_messages",
        ["organization_id", "channel_id", "id"],
    )
    op.create_unique_constraint(
        "uq_native_message_channel_sequence",
        "native_messages",
        ["channel_id", "message_sequence"],
    )
    op.create_foreign_key(
        "fk_native_message_thread_root_scope",
        "native_messages",
        "native_messages",
        ["organization_id", "channel_id", "thread_root_id"],
        ["organization_id", "channel_id", "id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_native_message_thread_created",
        "native_messages",
        ["organization_id", "channel_id", "thread_root_id", "message_sequence"],
        unique=False,
    )

    op.create_table(
        "native_message_mentions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("channel_id", sa.Uuid(), nullable=False),
        sa.Column("message_id", sa.Uuid(), nullable=False),
        sa.Column("mentioned_user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "channel_id", "message_id"],
            [
                "native_messages.organization_id",
                "native_messages.channel_id",
                "native_messages.id",
            ],
            name="fk_native_message_mention_message_scope",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["mentioned_user_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "message_id",
            "mentioned_user_id",
            name="uq_native_message_mention_message_user",
        ),
    )
    op.create_index(
        "ix_native_message_mention_org_user_created",
        "native_message_mentions",
        ["organization_id", "mentioned_user_id", "created_at"],
        unique=False,
    )

    op.create_table(
        "native_message_reactions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("channel_id", sa.Uuid(), nullable=False),
        sa.Column("message_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("reaction", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "reaction IN ('👍', '❤️', '🎉', '👀', '✅')",
            name="ck_native_reaction_allowed",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "channel_id", "message_id"],
            [
                "native_messages.organization_id",
                "native_messages.channel_id",
                "native_messages.id",
            ],
            name="fk_native_message_reaction_message_scope",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "message_id",
            "user_id",
            "reaction",
            name="uq_native_message_reaction_message_user_value",
        ),
    )
    op.create_index(
        "ix_native_message_reaction_org_message",
        "native_message_reactions",
        ["organization_id", "message_id"],
        unique=False,
    )

    op.create_table(
        "native_channel_read_states",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("channel_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("last_read_message_id", sa.Uuid(), nullable=False),
        sa.Column("last_read_sequence", sa.BigInteger(), nullable=False),
        sa.Column("last_read_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organization_id", "channel_id", "last_read_message_id"],
            [
                "native_messages.organization_id",
                "native_messages.channel_id",
                "native_messages.id",
            ],
            name="fk_native_channel_read_state_message_scope",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "channel_id",
            "user_id",
            name="uq_native_channel_read_state_channel_user",
        ),
    )
    op.create_index(
        "ix_native_channel_read_state_org_user",
        "native_channel_read_states",
        ["organization_id", "user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_native_channel_read_state_org_user",
        table_name="native_channel_read_states",
    )
    op.drop_table("native_channel_read_states")
    op.drop_index(
        "ix_native_message_reaction_org_message",
        table_name="native_message_reactions",
    )
    op.drop_table("native_message_reactions")
    op.drop_index(
        "ix_native_message_mention_org_user_created",
        table_name="native_message_mentions",
    )
    op.drop_table("native_message_mentions")
    op.drop_index("ix_native_message_thread_created", table_name="native_messages")
    op.drop_constraint(
        "fk_native_message_thread_root_scope",
        "native_messages",
        type_="foreignkey",
    )
    op.drop_constraint(
        "uq_native_message_channel_sequence",
        "native_messages",
        type_="unique",
    )
    op.drop_constraint(
        "uq_native_message_org_channel_id",
        "native_messages",
        type_="unique",
    )
    op.drop_constraint(
        "uq_native_channel_org_id",
        "native_channels",
        type_="unique",
    )
    op.drop_column("native_messages", "message_sequence")
    op.drop_column("native_messages", "thread_root_id")
    op.drop_column("native_channels", "last_message_sequence")
