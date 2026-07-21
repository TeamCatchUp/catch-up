"""drop v2 vector store tables

Revision ID: c1d2e3f4a5b6
Revises: d4e5f6a7b8c9
Create Date: 2026-07-06 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "c1d2e3f4a5b6"
down_revision: str | None = "d4e5f6a7b8c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS knowledge_store CASCADE")
    op.execute("DROP TABLE IF EXISTS vector_store_v2_backfill_states CASCADE")


def downgrade() -> None:
    # ponytail: legacy v2 data is intentionally not recreated after cleanup.
    pass
