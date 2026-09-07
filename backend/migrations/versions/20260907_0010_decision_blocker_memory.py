"""decision and blocker memory

Revision ID: 20260907_0010
Revises: 20260907_0009
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260907_0010"
down_revision: str | None = "20260907_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "decision_memory_candidates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("canonical_event_id", sa.Uuid(), nullable=False),
        sa.Column("search_document_id", sa.Uuid(), nullable=True),
        sa.Column("work_graph_node_id", sa.Uuid(), nullable=True),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("extraction_method", sa.String(length=32), nullable=False),
        sa.Column("extraction_version", sa.String(length=64), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
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
            "confidence >= 0.0 AND confidence <= 1.0",
            name="ck_decision_memory_confidence",
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
        sa.ForeignKeyConstraint(
            ["search_document_id"],
            ["search_documents.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["work_graph_node_id"],
            ["work_graph_nodes.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "canonical_event_id",
            "kind",
            "fingerprint",
            name="uq_decision_memory_org_event_kind_fingerprint",
        ),
    )
    op.create_index(
        "ix_decision_memory_org_kind_state",
        "decision_memory_candidates",
        ["organization_id", "kind", "state"],
    )
    op.create_index(
        "ix_decision_memory_org_created",
        "decision_memory_candidates",
        ["organization_id", "created_at"],
    )
    op.create_index(
        "ix_decision_memory_search_document",
        "decision_memory_candidates",
        ["search_document_id"],
    )
    op.create_index(
        "ix_decision_memory_canonical_event",
        "decision_memory_candidates",
        ["canonical_event_id"],
    )

    op.create_table(
        "decision_memory_extractions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("search_document_id", sa.Uuid(), nullable=False),
        sa.Column("extraction_version", sa.String(length=64), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("candidate_count", sa.Integer(), nullable=False),
        sa.Column(
            "processed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["search_document_id"],
            ["search_documents.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "search_document_id",
            name="uq_decision_memory_extraction_search_document",
        ),
    )
    op.create_index(
        "ix_decision_memory_extractions_org_processed",
        "decision_memory_extractions",
        ["organization_id", "processed_at"],
    )

    op.create_table(
        "decision_memory_reviews",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("candidate_id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(length=16), nullable=False),
        sa.Column("previous_state", sa.String(length=16), nullable=False),
        sa.Column("new_state", sa.String(length=16), nullable=False),
        sa.Column("previous_summary", sa.Text(), nullable=False),
        sa.Column("new_summary", sa.Text(), nullable=False),
        sa.Column("reason", sa.String(length=1000), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["decision_memory_candidates.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_decision_memory_reviews_candidate_created",
        "decision_memory_reviews",
        ["candidate_id", "created_at"],
    )
    op.create_index(
        "ix_decision_memory_reviews_org_created",
        "decision_memory_reviews",
        ["organization_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("decision_memory_reviews")
    op.drop_table("decision_memory_extractions")
    op.drop_table("decision_memory_candidates")
