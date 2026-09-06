"""permission-aware search projection and pgvector

Revision ID: 20260907_0009
Revises: 20260906_0008
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.search_models import Vector

revision: str = "20260907_0009"
down_revision: str | None = "20260906_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "search_documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("canonical_event_id", sa.Uuid(), nullable=False),
        sa.Column("integration_connection_id", sa.Uuid(), nullable=False),
        sa.Column("work_graph_node_id", sa.Uuid(), nullable=True),
        sa.Column("source_provider", sa.String(length=40), nullable=False),
        sa.Column("source_visibility", sa.String(length=32), nullable=False),
        sa.Column("source_acl", sa.JSON(), nullable=False),
        sa.Column("channel_id", sa.String(length=64), nullable=True),
        sa.Column("repository_id", sa.String(length=255), nullable=True),
        sa.Column("object_type", sa.String(length=64), nullable=False),
        sa.Column("object_external_id", sa.String(length=512), nullable=False),
        sa.Column("title", sa.String(length=1024), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("provenance", sa.JSON(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("embedding", Vector(), nullable=True),
        sa.Column("embedding_model", sa.String(length=255), nullable=True),
        sa.Column("embedding_status", sa.String(length=16), nullable=False),
        sa.Column("embedding_attempts", sa.Integer(), nullable=False),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "search_vector",
            postgresql.TSVECTOR(),
            sa.Computed(
                "to_tsvector('simple', coalesce(title, '') || ' ' || coalesce(content, ''))",
                persisted=True,
            ),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(["canonical_event_id"], ["canonical_events.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["integration_connection_id"], ["integration_connections.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["work_graph_node_id"], ["work_graph_nodes.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("canonical_event_id", name="uq_search_document_canonical_event"),
    )
    op.create_index("ix_search_documents_org_created", "search_documents", ["organization_id", "created_at"])
    op.create_index("ix_search_documents_org_provider", "search_documents", ["organization_id", "source_provider"])
    op.create_index("ix_search_documents_embedding_status", "search_documents", ["embedding_status", "next_retry_at"])
    op.create_index("ix_search_documents_org_object", "search_documents", ["organization_id", "integration_connection_id", "source_provider", "object_type", "object_external_id"])
    op.create_index("ix_search_documents_channel_id", "search_documents", ["channel_id"])
    op.create_index("ix_search_documents_repository_id", "search_documents", ["repository_id"])
    op.create_index("ix_search_documents_work_graph_node_id", "search_documents", ["work_graph_node_id"])
    op.create_index("ix_search_documents_search_vector", "search_documents", ["search_vector"], postgresql_using="gin")


def downgrade() -> None:
    op.drop_index("ix_search_documents_search_vector", table_name="search_documents")
    op.drop_table("search_documents")
    # The vector extension can be shared by other database objects; downgrade does not drop it.
