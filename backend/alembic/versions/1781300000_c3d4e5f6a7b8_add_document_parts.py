"""add document parts

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-07-06 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "c3d4e5f6a7b8"
down_revision: str | None = "b2c3d4e5f6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "document_parts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("vector_store_id", sa.String(length=255), nullable=False),
        sa.Column("part_type", sa.String(length=64), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("anchor_part_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "part_type IN ("
            "'title', 'body', 'comment', 'review_comment', "
            "'diff_hunk', 'commit_message'"
            ")",
            name="ck_document_parts_part_type",
        ),
        sa.ForeignKeyConstraint(
            ["anchor_part_id"],
            ["document_parts.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["vector_store_id"],
            ["vector_store.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_document_parts_anchor_part_id",
        "document_parts",
        ["anchor_part_id"],
    )
    op.create_index(
        "ix_document_parts_vector_store_id",
        "document_parts",
        ["vector_store_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_document_parts_vector_store_id", table_name="document_parts")
    op.drop_index("ix_document_parts_anchor_part_id", table_name="document_parts")
    op.drop_table("document_parts")
