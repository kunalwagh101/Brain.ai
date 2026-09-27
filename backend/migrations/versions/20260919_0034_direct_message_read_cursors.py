"""Add participant DM read cursors.

Revision ID: 20260919_0034
Revises: 20260919_0033
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260919_0034"
down_revision: str | None = "20260919_0033"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_direct_conversation_sequence_bounds",
        "direct_conversations",
        type_="check",
    )
    op.add_column(
        "direct_conversations",
        sa.Column(
            "participant_a_last_read_sequence",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
    )
    op.add_column(
        "direct_conversations",
        sa.Column(
            "participant_b_last_read_sequence",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
    )
    op.execute(
        "UPDATE direct_conversations "
        "SET participant_a_last_read_sequence = participant_a_visible_from_sequence - 1, "
        "participant_b_last_read_sequence = participant_b_visible_from_sequence - 1"
    )
    op.create_check_constraint(
        "ck_direct_conversation_sequence_bounds",
        "direct_conversations",
        "next_message_sequence >= 1 "
        "AND participant_a_visible_from_sequence >= 1 "
        "AND participant_b_visible_from_sequence >= 1 "
        "AND participant_a_visible_from_sequence <= next_message_sequence "
        "AND participant_b_visible_from_sequence <= next_message_sequence "
        "AND participant_a_last_read_sequence >= participant_a_visible_from_sequence - 1 "
        "AND participant_b_last_read_sequence >= participant_b_visible_from_sequence - 1 "
        "AND participant_a_last_read_sequence < next_message_sequence "
        "AND participant_b_last_read_sequence < next_message_sequence",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_direct_conversation_sequence_bounds",
        "direct_conversations",
        type_="check",
    )
    op.drop_column("direct_conversations", "participant_b_last_read_sequence")
    op.drop_column("direct_conversations", "participant_a_last_read_sequence")
    op.create_check_constraint(
        "ck_direct_conversation_sequence_bounds",
        "direct_conversations",
        "next_message_sequence >= 1 "
        "AND participant_a_visible_from_sequence >= 1 "
        "AND participant_b_visible_from_sequence >= 1 "
        "AND participant_a_visible_from_sequence <= next_message_sequence "
        "AND participant_b_visible_from_sequence <= next_message_sequence",
    )
