"""add vector store

Revision ID: c2d3e4f5a6b7
Revises: b2c3d4e5f6a7
Create Date: 2026-07-06 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from alembic import op

revision: str = "c2d3e4f5a6b7"
down_revision: str | None = "b2c3d4e5f6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "vector_store",
        sa.Column("id", sa.String(length=255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(1536), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("scope_id", sa.String(length=255), nullable=False),
        sa.Column("target_id", sa.String(length=255), nullable=False),
        sa.Column("external_document_id", sa.String(length=255), nullable=False),
        sa.Column(
            "chunk_identifier",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "source IN ('slack', 'jira', 'confluence', 'github', 'channel_talk')",
            name="ck_vector_store_source",
        ),
        sa.CheckConstraint(
            "entity_type IN ("
            "'message', 'issue', 'page', 'pr', "
            "'commit', 'comment', 'user_chat', 'document_article'"
            ")",
            name="ck_vector_store_entity_type",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source",
            "entity_type",
            "scope_id",
            "target_id",
            "external_document_id",
            "chunk_identifier",
            name="uq_vector_store_logical_chunk",
        ),
    )
    op.create_index(
        "ix_vector_store_logical_document",
        "vector_store",
        ["source", "entity_type", "scope_id", "target_id", "external_document_id"],
    )
    op.create_index(
        "ix_vector_store_search_filter",
        "vector_store",
        ["scope_id", "source", "target_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_vector_store_search_filter", table_name="vector_store")
    op.drop_index("ix_vector_store_logical_document", table_name="vector_store")
    op.drop_table("vector_store")
