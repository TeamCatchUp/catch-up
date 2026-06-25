from __future__ import annotations

from langchain_postgres import Column

KNOWLEDGE_STORE_TABLE_NAME = "knowledge_store"
KNOWLEDGE_STORE_ID_COLUMN = "document_id"
KNOWLEDGE_STORE_CONTENT_COLUMN = "content"
KNOWLEDGE_STORE_EMBEDDING_COLUMN = "embedding"
KNOWLEDGE_STORE_METADATA_JSON_COLUMN = "metadata"

KNOWLEDGE_STORE_METADATA_COLUMN_NAMES = [
    "source",
    "entity_type",
    "record_id",
    "scope_type",
    "scope_id",
    "target_type",
    "target_id",
    "target_name",
    "internal_author_id",
    "title",
    "body",
    "data",
    "url",
    "created_at",
    "updated_at",
    "synced_at",
]


def knowledge_store_metadata_columns() -> list[Column]:
    return [
        Column("source", "VARCHAR(50)", nullable=False),
        Column("entity_type", "VARCHAR(64)", nullable=False),
        Column("record_id", "VARCHAR(255)", nullable=False),
        Column("scope_type", "VARCHAR(64)", nullable=False),
        Column("scope_id", "VARCHAR(255)", nullable=False),
        Column("target_type", "VARCHAR(64)", nullable=False),
        Column("target_id", "VARCHAR(255)", nullable=False),
        Column("target_name", "VARCHAR(255)", nullable=False),
        Column("internal_author_id", "VARCHAR(128)"),
        Column("title", "TEXT", nullable=False),
        Column("body", "TEXT", nullable=False),
        Column("data", "JSONB"),
        Column("url", "TEXT", nullable=False),
        Column("created_at", "TIMESTAMPTZ", nullable=False),
        Column("updated_at", "TIMESTAMPTZ", nullable=False),
        Column("synced_at", "TIMESTAMPTZ", nullable=False),
    ]


def knowledge_store_id_column() -> Column:
    return Column(
        KNOWLEDGE_STORE_ID_COLUMN,
        "VARCHAR(255)",
        nullable=False,
    )
