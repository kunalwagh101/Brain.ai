"""Add author-safe Brain message lifecycle history.

Revision ID: 20260918_0028
Revises: 20260918_0027
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260918_0028"
down_revision: str | None = "20260918_0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "native_messages",
        sa.Column("revision", sa.Integer(), server_default="1", nullable=False),
    )
    op.add_column(
        "native_messages",
        sa.Column("edited_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "native_messages",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_check_constraint(
        "ck_native_message_revision_positive",
        "native_messages",
        "revision >= 1",
    )

    op.create_table(
        "native_message_revisions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("channel_id", sa.Uuid(), nullable=False),
        sa.Column("message_id", sa.Uuid(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=16), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("body_sha256", sa.String(length=64), nullable=False),
        sa.Column("body_char_count", sa.Integer(), nullable=False),
        sa.Column("changed_by_user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "revision >= 1",
            name="ck_native_message_revision_snapshot_positive",
        ),
        sa.CheckConstraint(
            "body_char_count > 0",
            name="ck_native_message_revision_body_chars",
        ),
        sa.CheckConstraint(
            "action IN ('edit', 'retract')",
            name="ck_native_message_revision_action",
        ),
        sa.ForeignKeyConstraint(
            ["changed_by_user_id"],
            ["users.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "channel_id", "message_id"],
            [
                "native_messages.organization_id",
                "native_messages.channel_id",
                "native_messages.id",
            ],
            name="fk_native_message_revision_message_scope",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "message_id",
            "revision",
            name="uq_native_message_revision_message_revision",
        ),
    )
    op.create_index(
        "ix_native_message_revision_org_message_created",
        "native_message_revisions",
        ["organization_id", "message_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_native_message_revision_org_message_created",
        table_name="native_message_revisions",
    )
    op.drop_table("native_message_revisions")

    op.drop_constraint(
        "ck_native_message_revision_positive",
        "native_messages",
        type_="check",
    )
    op.drop_column("native_messages", "deleted_at")
    op.drop_column("native_messages", "edited_at")
    op.drop_column("native_messages", "revision")
