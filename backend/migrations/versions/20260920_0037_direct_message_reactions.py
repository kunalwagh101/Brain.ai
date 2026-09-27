"""Add participant-private direct-message reactions.

Revision ID: 20260920_0037
Revises: 20260920_0036
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260920_0037"
down_revision: str | None = "20260920_0036"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "direct_message_reactions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
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
            name="ck_direct_message_reaction_allowed",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "conversation_id", "message_id"],
            [
                "direct_messages.organization_id",
                "direct_messages.conversation_id",
                "direct_messages.id",
            ],
            name="fk_direct_message_reaction_message_scope",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_direct_message_reaction_membership",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "message_id",
            "user_id",
            "reaction",
            name="uq_direct_message_reaction_message_user_value",
        ),
    )
    op.create_index(
        "ix_direct_message_reaction_org_message",
        "direct_message_reactions",
        ["organization_id", "message_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_direct_message_reaction_org_message",
        table_name="direct_message_reactions",
    )
    op.drop_table("direct_message_reactions")
