"""Generic file and transcript evidence sources.

Revision ID: 20260910_0017
Revises: 20260910_0016
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260910_0017"
down_revision: str | None = "20260910_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "evidence_sources",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("integration_connection_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("filename", sa.String(length=512), nullable=False),
        sa.Column("media_type", sa.String(length=128), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("byte_size", sa.BigInteger(), nullable=False),
        sa.Column("raw_content", sa.LargeBinary(), nullable=True),
        sa.Column("source_visibility", sa.String(length=32), nullable=False),
        sa.Column("source_acl", sa.JSON(), nullable=False),
        sa.Column("chunk_count", sa.Integer(), nullable=False),
        sa.Column("extracted_char_count", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("last_error_code", sa.String(length=128), nullable=True),
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
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("byte_size >= 1", name="ck_evidence_source_positive_bytes"),
        sa.CheckConstraint("chunk_count >= 0", name="ck_evidence_source_chunk_count"),
        sa.CheckConstraint(
            "extracted_char_count >= 0",
            name="ck_evidence_source_extracted_char_count",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["integration_connection_id"],
            ["integration_connections.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "idempotency_key",
            name="uq_evidence_source_org_idempotency",
        ),
    )
    op.create_index(
        "ix_evidence_source_org_status_created",
        "evidence_sources",
        ["organization_id", "status", "created_at"],
    )
    op.create_index(
        "ix_evidence_source_org_sha",
        "evidence_sources",
        ["organization_id", "content_sha256"],
    )


def downgrade() -> None:
    op.drop_index("ix_evidence_source_org_sha", table_name="evidence_sources")
    op.drop_index("ix_evidence_source_org_status_created", table_name="evidence_sources")
    op.drop_table("evidence_sources")
