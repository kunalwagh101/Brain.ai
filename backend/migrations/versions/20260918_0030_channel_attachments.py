"""Add governed native channel attachments.

Revision ID: 20260918_0030
Revises: 20260918_0029
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260918_0030"
down_revision: str | None = "20260918_0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "evidence_sources",
        sa.Column("native_channel_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_evidence_source_native_channel",
        "evidence_sources",
        "native_channels",
        ["native_channel_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_evidence_sources_native_channel_id",
        "evidence_sources",
        ["native_channel_id"],
        unique=False,
    )

    op.drop_constraint(
        "ck_native_message_body_chars",
        "native_messages",
        type_="check",
    )
    op.create_check_constraint(
        "ck_native_message_body_chars",
        "native_messages",
        "body_char_count >= 0",
    )
    op.drop_constraint(
        "ck_native_message_revision_body_chars",
        "native_message_revisions",
        type_="check",
    )
    op.create_check_constraint(
        "ck_native_message_revision_body_chars",
        "native_message_revisions",
        "body_char_count >= 0",
    )

    op.create_table(
        "native_message_attachments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("channel_id", sa.Uuid(), nullable=False),
        sa.Column("message_id", sa.Uuid(), nullable=False),
        sa.Column("evidence_source_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
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
            name="fk_native_message_attachment_message_scope",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["evidence_source_id"],
            ["evidence_sources.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "message_id",
            "evidence_source_id",
            name="uq_native_message_attachment_message_source",
        ),
    )
    op.create_index(
        "ix_native_message_attachment_org_channel_message",
        "native_message_attachments",
        ["organization_id", "channel_id", "message_id"],
        unique=False,
    )


def downgrade() -> None:
    bind = op.get_bind()
    attachment_only_messages = bind.execute(
        sa.text(
            "SELECT COUNT(*) FROM native_messages "
            "WHERE body_char_count = 0"
        )
    ).scalar_one()
    attachment_only_revisions = bind.execute(
        sa.text(
            "SELECT COUNT(*) FROM native_message_revisions "
            "WHERE body_char_count = 0"
        )
    ).scalar_one()
    if attachment_only_messages or attachment_only_revisions:
        raise RuntimeError(
            "Cannot downgrade channel attachments while attachment-only messages exist; "
            "export or migrate those messages first. Evidence sources are not deleted automatically."
        )

    op.drop_index(
        "ix_native_message_attachment_org_channel_message",
        table_name="native_message_attachments",
    )
    op.drop_table("native_message_attachments")

    op.drop_constraint(
        "ck_native_message_revision_body_chars",
        "native_message_revisions",
        type_="check",
    )
    op.create_check_constraint(
        "ck_native_message_revision_body_chars",
        "native_message_revisions",
        "body_char_count > 0",
    )
    op.drop_constraint(
        "ck_native_message_body_chars",
        "native_messages",
        type_="check",
    )
    op.create_check_constraint(
        "ck_native_message_body_chars",
        "native_messages",
        "body_char_count > 0",
    )

    op.drop_index(
        "ix_evidence_sources_native_channel_id",
        table_name="evidence_sources",
    )
    op.drop_constraint(
        "fk_evidence_source_native_channel",
        "evidence_sources",
        type_="foreignkey",
    )
    op.drop_column("evidence_sources", "native_channel_id")
