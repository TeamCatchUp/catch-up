"""SourceVersion 저장 테이블을 추가한다.

Revision ID: add2c4093ca0
Revises: c1d2e3f4a5b6
Create Date: 2026-07-24 05:13:43.883280
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "add2c4093ca0"
down_revision: str | Sequence[str] | None = "c1d2e3f4a5b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """SourceVersion 저장 테이블을 생성한다."""
    op.create_table(
        "source_versions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("scope_id", sa.String(length=255), nullable=False),
        sa.Column("target_id", sa.String(length=255), nullable=False),
        sa.Column(
            "external_document_id",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column("change_kind", sa.String(length=16), nullable=False),
        sa.Column(
            "source_version_key",
            sa.String(length=512),
            nullable=False,
        ),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("canonical_url", sa.Text(), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("content_type", sa.String(length=255), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=True),
        sa.Column(
            "source_updated_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "observed_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "idempotency_key",
            sa.String(length=512),
            nullable=False,
        ),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "("
            "change_kind = 'deleted' "
            "AND content IS NULL "
            "AND content_type IS NULL "
            "AND content_hash IS NULL"
            ") OR ("
            "change_kind IN ('created', 'updated') "
            "AND content IS NOT NULL "
            "AND content_type IS NOT NULL "
            "AND content_hash IS NOT NULL"
            ")",
            name="ck_source_versions_content_by_change_kind",
        ),
        sa.CheckConstraint(
            "change_kind IN ('created', 'updated', 'deleted')",
            name="ck_source_versions_change_kind",
        ),
        sa.CheckConstraint(
            "char_length(payload_hash) = 64",
            name="ck_source_versions_payload_hash_length",
        ),
        sa.CheckConstraint(
            "content_hash IS NULL OR char_length(content_hash) = 64",
            name="ck_source_versions_content_hash_length",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workspace_id",
            "idempotency_key",
            name="uq_source_versions_workspace_idempotency_key",
        ),
        sa.UniqueConstraint(
            "workspace_id",
            "source_type",
            "entity_type",
            "scope_id",
            "target_id",
            "external_document_id",
            "source_version_key",
            name="uq_source_versions_logical_version",
        ),
    )
    op.create_index(
        "idx_source_versions_source_latest",
        "source_versions",
        [
            "workspace_id",
            "source_type",
            "entity_type",
            "scope_id",
            "target_id",
            "external_document_id",
            "source_updated_at",
            "observed_at",
            "created_at",
        ],
        unique=False,
    )


def downgrade() -> None:
    """SourceVersion 저장 테이블을 제거한다."""
    op.drop_index(
        "idx_source_versions_source_latest",
        table_name="source_versions",
    )
    op.drop_table("source_versions")
