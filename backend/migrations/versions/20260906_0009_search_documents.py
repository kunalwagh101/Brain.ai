"""Add canonical evidence search documents.

Revision ID: 20260906_0009
Revises: 20260906_0008
Create Date: 2026-09-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260906_0009"
down_revision: str | None = "20260906_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "search_documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("canonical_event_id", sa.Uuid(), nullable=False),
        sa.Column("source_provider", sa.String(length=40), nullable=False),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("object_type", sa.String(length=64), nullable=False),
        sa.Column("search_text", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["canonical_event_id"],
            ["canonical_events.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "canonical_event_id",
            name="uq_search_document_canonical_event",
        ),
    )
    op.create_index(
        "ix_search_documents_organization_id",
        "search_documents",
        ["organization_id"],
    )
    op.create_index(
        "ix_search_documents_org_provider",
        "search_documents",
        ["organization_id", "source_provider"],
    )

    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            "CREATE INDEX ix_search_documents_fts "
            "ON search_documents USING GIN "
            "(to_tsvector('simple', search_text))"
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP INDEX IF EXISTS ix_search_documents_fts")
    op.drop_index("ix_search_documents_org_provider", table_name="search_documents")
    op.drop_index("ix_search_documents_organization_id", table_name="search_documents")
    op.drop_table("search_documents")
