"""Add participant-private direct-message lifecycle revisions.

Revision ID: 20260919_0035
Revises: 20260919_0034
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260919_0035"
down_revision: str | None = "20260919_0034"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_direct_message_scope_id",
        "direct_messages",
        ["organization_id", "conversation_id", "id"],
    )
    op.add_column(
        "direct_messages",
        sa.Column(
            "revision",
            sa.Integer(),
            server_default=sa.text("1"),
            nullable=False,
        ),
    )
    op.add_column(
        "direct_messages",
        sa.Column("edited_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "direct_messages",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "direct_message_revisions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("message_id", sa.Uuid(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=16), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("body_sha256", sa.String(length=64), nullable=False),
        sa.Column("body_char_count", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "revision >= 1 AND body_char_count > 0 "
            "AND action IN ('edit', 'retract')",
            name="ck_direct_message_revision_bounds",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "conversation_id", "message_id"],
            [
                "direct_messages.organization_id",
                "direct_messages.conversation_id",
                "direct_messages.id",
            ],
            name="fk_direct_message_revision_message_scope",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "message_id",
            "revision",
            name="uq_direct_message_revision_message_revision",
        ),
    )
    op.create_index(
        "ix_direct_message_revision_org_conversation_created",
        "direct_message_revisions",
        ["organization_id", "conversation_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_direct_message_revision_org_conversation_created",
        table_name="direct_message_revisions",
    )
    op.drop_table("direct_message_revisions")
    op.drop_column("direct_messages", "deleted_at")
    op.drop_column("direct_messages", "edited_at")
    op.drop_column("direct_messages", "revision")
    op.drop_constraint(
        "uq_direct_message_scope_id",
        "direct_messages",
        type_="unique",
    )
