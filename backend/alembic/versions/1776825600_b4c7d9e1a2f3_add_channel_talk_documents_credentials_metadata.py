"""add_channel_talk_documents_credentials_metadata

Revision ID: b4c7d9e1a2f3
Revises: 61e30cd579bf
Create Date: 2026-04-25 00:00:00.000000

"""
from typing import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b4c7d9e1a2f3"
down_revision: Union[str, Sequence[str], None] = "61e30cd579bf"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "channel_talk_document_credentials",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("channel_id", sa.String(length=128), nullable=False),
        sa.Column("space_id", sa.String(length=128), nullable=False),
        sa.Column("space_name", sa.String(length=255), nullable=False),
        sa.Column("access_key", sa.String(length=512), nullable=False),
        sa.Column("access_secret", sa.String(length=512), nullable=False),
        sa.Column("credential_last_verified_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("association_status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "association_status IN ('api_verified', 'local_trusted', 'unverified', 'failed')",
            name="ck_channel_talk_document_credentials_association_status",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "channel_id",
            name="uq_channel_talk_document_credentials_channel_id",
        ),
        sa.UniqueConstraint(
            "space_id",
            name="uq_channel_talk_document_credentials_space_id",
        ),
    )

    op.create_table(
        "channel_talk_document_spaces",
        sa.Column("channel_id", sa.String(length=128), nullable=False),
        sa.Column("space_id", sa.String(length=128), nullable=False),
        sa.Column("space_name", sa.String(length=255), nullable=False),
        sa.Column("synced_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("channel_id", "space_id"),
    )
    op.create_table(
        "channel_talk_document_authors",
        sa.Column("channel_id", sa.String(length=128), nullable=False),
        sa.Column("space_id", sa.String(length=128), nullable=False),
        sa.Column("author_id", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("avatar_url", sa.String(length=500), nullable=True),
        sa.Column("synced_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("channel_id", "space_id", "author_id"),
    )
    op.create_index(
        op.f("ix_channel_talk_document_authors_email"),
        "channel_talk_document_authors",
        ["email"],
        unique=False,
    )
    op.create_table(
        "channel_talk_document_nav_nodes",
        sa.Column("channel_id", sa.String(length=128), nullable=False),
        sa.Column("space_id", sa.String(length=128), nullable=False),
        sa.Column("nav_node_id", sa.String(length=128), nullable=False),
        sa.Column("parent_node_id", sa.String(length=128), nullable=True),
        sa.Column("node_type", sa.String(length=64), nullable=True),
        sa.Column("entity_type", sa.String(length=64), nullable=True),
        sa.Column("entity_id", sa.String(length=128), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("rank", sa.Integer(), nullable=True),
        sa.Column("language", sa.String(length=32), nullable=True),
        sa.Column("synced_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("channel_id", "space_id", "nav_node_id"),
    )
    op.create_index(
        "idx_channel_talk_document_nav_entity",
        "channel_talk_document_nav_nodes",
        ["channel_id", "space_id", "entity_type", "entity_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_channel_talk_document_nav_nodes_entity_id"),
        "channel_talk_document_nav_nodes",
        ["entity_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_channel_talk_document_nav_nodes_parent_node_id"),
        "channel_talk_document_nav_nodes",
        ["parent_node_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_channel_talk_document_nav_nodes_parent_node_id"), table_name="channel_talk_document_nav_nodes")
    op.drop_index(op.f("ix_channel_talk_document_nav_nodes_entity_id"), table_name="channel_talk_document_nav_nodes")
    op.drop_index("idx_channel_talk_document_nav_entity", table_name="channel_talk_document_nav_nodes")
    op.drop_table("channel_talk_document_nav_nodes")
    op.drop_index(op.f("ix_channel_talk_document_authors_email"), table_name="channel_talk_document_authors")
    op.drop_table("channel_talk_document_authors")
    op.drop_table("channel_talk_document_spaces")
    op.drop_table("channel_talk_document_credentials")
