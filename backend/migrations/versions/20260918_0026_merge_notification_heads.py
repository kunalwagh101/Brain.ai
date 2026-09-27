"""Merge the two notification migration branches.

Revision ID: 20260918_0026
Revises: 20260917_0025, 20260918_0025

This is a graph-only merge. Both parent migrations remain immutable so databases
that have applied either parent can converge safely on one Alembic head.
"""

from collections.abc import Sequence

revision: str = "20260918_0026"
down_revision: tuple[str, str] = ("20260917_0025", "20260918_0025")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    return None


def downgrade() -> None:
    return None
