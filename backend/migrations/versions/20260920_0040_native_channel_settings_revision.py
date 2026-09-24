"""Add optimistic native-channel settings revision.

Revision ID: 20260920_0040
Revises: 20260920_0039
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260920_0040"
down_revision: str | None = "20260920_0039"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "native_channels",
        sa.Column(
            "settings_revision",
            sa.Integer(),
            server_default="1",
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_native_channel_settings_revision_positive",
        "native_channels",
        "settings_revision >= 1",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_native_channel_settings_revision_positive",
        "native_channels",
        type_="check",
    )
    op.drop_column("native_channels", "settings_revision")
