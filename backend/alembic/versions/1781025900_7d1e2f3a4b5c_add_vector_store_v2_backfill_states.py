"""add vector store v2 backfill states

Revision ID: 7d1e2f3a4b5c
Revises: 9e7a4b2c1d3f
Create Date: 2026-06-10 12:05:00.000000

"""

from typing import Sequence
from typing import Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7d1e2f3a4b5c"
down_revision: Union[str, Sequence[str], None] = "9e7a4b2c1d3f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "vector_store_v2_backfill_states",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("connector", sa.String(length=50), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("scope_id", sa.String(length=255), nullable=False),
        sa.Column("target_id", sa.String(length=255), nullable=False),
        sa.Column(
            "state",
            sa.String(length=32),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column(
            "expected_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "backfill_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "failed_ids",
            postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("succeeded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "state IN ('pending', 'processing', 'succeeded', 'failed')",
            name="ck_vector_store_v2_backfill_states_state",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "connector",
            "entity_type",
            "scope_id",
            "target_id",
            name="uq_vector_store_v2_backfill_states_scope_target",
        ),
    )
    op.create_index(
        "ix_vector_store_v2_backfill_states_lookup",
        "vector_store_v2_backfill_states",
        ["connector", "entity_type", "state"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_vector_store_v2_backfill_states_lookup",
        table_name="vector_store_v2_backfill_states",
    )
    op.drop_table("vector_store_v2_backfill_states")
