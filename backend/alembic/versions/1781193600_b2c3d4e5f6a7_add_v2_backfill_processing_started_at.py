"""add v2 backfill processing lease timestamp

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-06-19 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: str | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "vector_store_v2_backfill_states",
        sa.Column("processing_started_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_vector_store_v2_backfill_states_processing_lookup",
        "vector_store_v2_backfill_states",
        ["connector", "entity_type", "state", "processing_started_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_vector_store_v2_backfill_states_processing_lookup",
        table_name="vector_store_v2_backfill_states",
    )
    op.drop_column("vector_store_v2_backfill_states", "processing_started_at")
