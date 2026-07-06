from __future__ import annotations

from langchain_postgres import Column

VECTOR_STORE_TABLE_NAME = "vector_store"
VECTOR_STORE_ID_COLUMN = "id"
VECTOR_STORE_CONTENT_COLUMN = "content"
VECTOR_STORE_EMBEDDING_COLUMN = "embedding"

VECTOR_STORE_METADATA_COLUMN_NAMES = [
    "source",
    "entity_type",
    "scope_id",
    "target_id",
    "external_document_id",
    "chunk_identifier",
    "created_at",
    "updated_at",
]

# TODO : KNOWLEDGE STORE 관련 코드 삭제 후 제거
KNOWLEDGE_STORE_TABLE_NAME = VECTOR_STORE_TABLE_NAME
KNOWLEDGE_STORE_ID_COLUMN = VECTOR_STORE_ID_COLUMN
KNOWLEDGE_STORE_CONTENT_COLUMN = VECTOR_STORE_CONTENT_COLUMN
KNOWLEDGE_STORE_EMBEDDING_COLUMN = VECTOR_STORE_EMBEDDING_COLUMN
KNOWLEDGE_STORE_METADATA_JSON_COLUMN = "metadata"
KNOWLEDGE_STORE_METADATA_COLUMN_NAMES = VECTOR_STORE_METADATA_COLUMN_NAMES


def vector_store_metadata_columns() -> list[Column]:
    return [
        Column("source", "VARCHAR(50)", nullable=False),
        Column("entity_type", "VARCHAR(64)", nullable=False),
        Column("scope_id", "VARCHAR(255)", nullable=False),
        Column("target_id", "VARCHAR(255)", nullable=False),
        Column("external_document_id", "VARCHAR(255)", nullable=False),
        Column("chunk_identifier", "INTEGER DEFAULT 0", nullable=False),
        Column("created_at", "TIMESTAMPTZ", nullable=False),
        Column("updated_at", "TIMESTAMPTZ", nullable=False),
    ]


def vector_store_id_column() -> Column:
    return Column(
        VECTOR_STORE_ID_COLUMN,
        "VARCHAR(255)",
        nullable=False,
    )


def knowledge_store_metadata_columns() -> list[Column]:
    return vector_store_metadata_columns()


def knowledge_store_id_column() -> Column:
    return vector_store_id_column()
