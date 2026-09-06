"""Add tenant-scoped typed work graph.

Revision ID: 20260906_0008
Revises: 20260906_0007
Create Date: 2026-09-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260906_0008"
down_revision: str | None = "20260906_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    node_type = sa.Enum(
        "PERSON",
        "PROJECT",
        "TRACK",
        "WORK_ITEM",
        "EVIDENCE",
        name="workgraphnodetype",
        native_enum=False,
        length=32,
    )
    edge_type = sa.Enum(
        "PERFORMED",
        "RESOLVES_TO",
        "CONTAINS",
        "SUPPORTED_BY",
        "DEPENDS_ON",
        "RELATED_TO",
        name="workgraphedgetype",
        native_enum=False,
        length=32,
    )
    edge_source = sa.Enum(
        "CANONICAL",
        "IDENTITY",
        "MANUAL",
        "INFERENCE",
        name="workgraphedgesource",
        native_enum=False,
        length=24,
    )
    evidence_state = sa.Enum(
        "VERIFIED",
        "INFERRED",
        name="workgraphevidencestate",
        native_enum=False,
        length=16,
    )

    op.create_table(
        "work_graph_nodes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("node_type", node_type, nullable=False),
        sa.Column("stable_key", sa.String(length=512), nullable=False),
        sa.Column("display_name", sa.String(length=512), nullable=True),
        sa.Column("canonical_event_id", sa.Uuid(), nullable=True),
        sa.Column("source_identity_id", sa.Uuid(), nullable=True),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column(
            "source_visibility",
            sa.String(length=32),
            server_default="organization",
            nullable=False,
        ),
        sa.Column("source_acl", sa.JSON(), nullable=False),
        sa.Column("attributes", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
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
        sa.ForeignKeyConstraint(
            ["source_identity_id"],
            ["source_identities.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "stable_key",
            name="uq_work_graph_node_org_key",
        ),
        sa.UniqueConstraint(
            "canonical_event_id",
            name="uq_work_graph_node_canonical_event",
        ),
    )
    op.create_index(
        "ix_work_graph_nodes_organization_id",
        "work_graph_nodes",
        ["organization_id"],
    )
    op.create_index(
        "ix_work_graph_nodes_canonical_event_id",
        "work_graph_nodes",
        ["canonical_event_id"],
    )
    op.create_index(
        "ix_work_graph_nodes_source_identity_id",
        "work_graph_nodes",
        ["source_identity_id"],
    )
    op.create_index(
        "ix_work_graph_nodes_user_id",
        "work_graph_nodes",
        ["user_id"],
    )
    op.create_index(
        "ix_work_graph_nodes_org_type",
        "work_graph_nodes",
        ["organization_id", "node_type"],
    )

    op.create_table(
        "work_graph_edges",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("source_node_id", sa.Uuid(), nullable=False),
        sa.Column("target_node_id", sa.Uuid(), nullable=False),
        sa.Column("edge_type", edge_type, nullable=False),
        sa.Column("source_kind", edge_source, nullable=False),
        sa.Column("evidence_state", evidence_state, nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("provenance_key", sa.String(length=512), nullable=False),
        sa.Column("provenance", sa.JSON(), nullable=False),
        sa.Column("canonical_event_id", sa.Uuid(), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "confidence >= 0.0 AND confidence <= 1.0",
            name="ck_work_graph_edge_confidence",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_node_id"],
            ["work_graph_nodes.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["target_node_id"],
            ["work_graph_nodes.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["canonical_event_id"],
            ["canonical_events.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "provenance_key",
            name="uq_work_graph_edge_org_provenance",
        ),
    )
    op.create_index(
        "ix_work_graph_edges_organization_id",
        "work_graph_edges",
        ["organization_id"],
    )
    op.create_index(
        "ix_work_graph_edges_canonical_event_id",
        "work_graph_edges",
        ["canonical_event_id"],
    )
    op.create_index(
        "ix_work_graph_edges_org_source",
        "work_graph_edges",
        ["organization_id", "source_node_id"],
    )
    op.create_index(
        "ix_work_graph_edges_org_target",
        "work_graph_edges",
        ["organization_id", "target_node_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_work_graph_edges_org_target", table_name="work_graph_edges")
    op.drop_index("ix_work_graph_edges_org_source", table_name="work_graph_edges")
    op.drop_index(
        "ix_work_graph_edges_canonical_event_id",
        table_name="work_graph_edges",
    )
    op.drop_index(
        "ix_work_graph_edges_organization_id",
        table_name="work_graph_edges",
    )
    op.drop_table("work_graph_edges")

    op.drop_index("ix_work_graph_nodes_org_type", table_name="work_graph_nodes")
    op.drop_index("ix_work_graph_nodes_user_id", table_name="work_graph_nodes")
    op.drop_index(
        "ix_work_graph_nodes_source_identity_id",
        table_name="work_graph_nodes",
    )
    op.drop_index(
        "ix_work_graph_nodes_canonical_event_id",
        table_name="work_graph_nodes",
    )
    op.drop_index(
        "ix_work_graph_nodes_organization_id",
        table_name="work_graph_nodes",
    )
    op.drop_table("work_graph_nodes")
