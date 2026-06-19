"""add v2 backfill retry metadata

Revision ID: a1b2c3d4e5f6
Revises: 7d1e2f3a4b5c
Create Date: 2026-06-18 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "7d1e2f3a4b5c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "vector_store_v2_backfill_states",
        sa.Column(
            "failure_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column(
        "vector_store_v2_backfill_states",
        sa.Column("last_error_type", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "vector_store_v2_backfill_states",
        sa.Column("last_error_message", sa.Text(), nullable=True),
    )
    op.add_column(
        "vector_store_v2_backfill_states",
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_vector_store_v2_backfill_states_retry_lookup",
        "vector_store_v2_backfill_states",
        ["connector", "entity_type", "state", "next_retry_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_vector_store_v2_backfill_states_retry_lookup",
        table_name="vector_store_v2_backfill_states",
    )
    op.drop_column("vector_store_v2_backfill_states", "next_retry_at")
    op.drop_column("vector_store_v2_backfill_states", "last_error_message")
    op.drop_column("vector_store_v2_backfill_states", "last_error_type")
    op.drop_column("vector_store_v2_backfill_states", "failure_count")
