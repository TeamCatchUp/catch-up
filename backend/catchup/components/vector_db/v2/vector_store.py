from __future__ import annotations

import asyncio
from collections.abc import Callable
from collections.abc import Sequence
from contextlib import AbstractContextManager

import structlog
from langchain.embeddings import Embeddings
from langchain_core.documents import Document
from langchain_postgres import PGEngine
from langchain_postgres import PGVectorStore
from sqlalchemy import inspect
from sqlalchemy import text
from sqlalchemy.orm import Session

from catchup.components.vector_db.v2.constants import KNOWLEDGE_STORE_CONTENT_COLUMN
from catchup.components.vector_db.v2.constants import KNOWLEDGE_STORE_EMBEDDING_COLUMN
from catchup.components.vector_db.v2.constants import KNOWLEDGE_STORE_ID_COLUMN
from catchup.components.vector_db.v2.constants import (
    KNOWLEDGE_STORE_METADATA_COLUMN_NAMES,
)
from catchup.components.vector_db.v2.constants import (
    KNOWLEDGE_STORE_METADATA_JSON_COLUMN,
)
from catchup.components.vector_db.v2.constants import KNOWLEDGE_STORE_TABLE_NAME
from catchup.components.vector_db.v2.constants import knowledge_store_id_column
from catchup.components.vector_db.v2.constants import knowledge_store_metadata_columns
from catchup.configs.config import settings
from catchup.db.engine import SessionLocal
from catchup.db.engine import engine as sqlalchemy_engine

logger = structlog.get_logger(__name__)


class VectorStore:
    """Thin LangChain PGVectorStore adapter for the v2 knowledge store."""

    def __init__(
        self,
        *,
        embeddings: Embeddings,
        pg_engine: PGEngine | None = None,
        vector_store: PGVectorStore | None = None,
        table_name: str = KNOWLEDGE_STORE_TABLE_NAME,
        session_factory: Callable[[], AbstractContextManager[Session]] = SessionLocal,
    ) -> None:
        self._embeddings = embeddings
        self._pg_engine = pg_engine
        self._vector_store = vector_store
        self._table_name = table_name
        self._session_factory = session_factory
        self._initialized = vector_store is not None

    async def initialize(self) -> None:
        if self._initialized:
            return

        pg_engine = self._pg_engine or PGEngine.from_connection_string(
            settings.sqlalchemy_database_url,
            pool_size=settings.DB_ASYNC_POOL_SIZE,
            max_overflow=settings.DB_ASYNC_MAX_OVERFLOW,
            pool_pre_ping=settings.DB_POOL_PRE_PING,
        )
        self._pg_engine = pg_engine

        if not self._table_exists():
            await pg_engine.ainit_vectorstore_table(
                table_name=self._table_name,
                vector_size=settings.PGVECTOR_EMBEDDING_DIMENSIONS,
                id_column=knowledge_store_id_column(),
                content_column=KNOWLEDGE_STORE_CONTENT_COLUMN,
                embedding_column=KNOWLEDGE_STORE_EMBEDDING_COLUMN,
                metadata_columns=knowledge_store_metadata_columns(),
                metadata_json_column=KNOWLEDGE_STORE_METADATA_JSON_COLUMN,
                store_metadata=True,
                overwrite_existing=False,
            )
            logger.info(
                "pgvector_v2_table_created",
                table_name=self._table_name,
            )

        self._vector_store = await PGVectorStore.create(
            engine=pg_engine,
            table_name=self._table_name,
            embedding_service=self._embeddings,
            id_column=KNOWLEDGE_STORE_ID_COLUMN,
            content_column=KNOWLEDGE_STORE_CONTENT_COLUMN,
            embedding_column=KNOWLEDGE_STORE_EMBEDDING_COLUMN,
            metadata_columns=KNOWLEDGE_STORE_METADATA_COLUMN_NAMES,
            metadata_json_column=KNOWLEDGE_STORE_METADATA_JSON_COLUMN,
        )
        self._initialized = True
        logger.info(
            "v2_vector_store_initialized",
            table_name=self._table_name,
        )

    async def upsert_documents(
        self,
        documents: Sequence[Document],
        *,
        ids: Sequence[str] | None = None,
        embeddings: Sequence[Sequence[float]] | None = None,
    ) -> list[str]:
        if not documents:
            return []

        try:
            document_ids = self._resolve_ids(documents, ids)
            store = self._ensure_store()
            if embeddings is None:
                return await store.aadd_documents(
                    documents=list(documents),
                    ids=document_ids,
                )

            embedding_rows = [list(embedding) for embedding in embeddings]
            if len(embedding_rows) != len(documents):
                raise ValueError("document and embedding counts must match")

            return await store.aadd_embeddings(
                texts=[document.page_content for document in documents],
                embeddings=embedding_rows,
                metadatas=[dict(document.metadata) for document in documents],
                ids=document_ids,
            )
        except Exception as exc:
            logger.exception(
                "v2_vector_store_upsert_failed",
                table_name=self._table_name,
                id_count=len(ids or documents),
                with_embeddings=embeddings is not None,
                error=str(exc),
            )
            raise

    async def delete(self, ids: Sequence[str]) -> int:
        if not ids:
            return 0
        store = self._ensure_store()
        document_ids = list(ids)
        try:
            deleted = await store.adelete(ids=document_ids)
            return len(document_ids) if deleted else 0
        except Exception as exc:
            logger.exception(
                "v2_vector_store_delete_failed",
                table_name=self._table_name,
                id_count=len(document_ids),
                error=str(exc),
            )
            raise

    async def delete_by_id_prefix(self, prefix: str) -> int:
        normalized_prefix = prefix.strip()
        if not normalized_prefix:
            return 0
        return await asyncio.to_thread(self._delete_by_id_prefix_sync, normalized_prefix)

    async def find_missing_metadata_namespace_ids(
        self,
        ids: Sequence[str],
        *,
        namespace: str,
    ) -> tuple[str, ...]:
        document_ids = [str(document_id) for document_id in ids]
        if not document_ids:
            return ()
        if not namespace.strip():
            raise ValueError("metadata namespace is required")

        return await asyncio.to_thread(
            self._find_missing_metadata_namespace_ids_sync,
            document_ids,
            namespace,
        )

    def _find_missing_metadata_namespace_ids_sync(
        self,
        ids: list[str],
        namespace: str,
    ) -> tuple[str, ...]:
        params = {
            f"id_{index}": document_id for index, document_id in enumerate(ids)
        }
        placeholders = ", ".join(
            f"(CAST(:id_{index} AS varchar))" for index in range(len(ids))
        )
        statement = text(
            f"""
            WITH requested(document_id) AS (
                VALUES {placeholders}
            )
            SELECT requested.document_id
            FROM requested
            LEFT JOIN {self._table_name} store
              ON store.{KNOWLEDGE_STORE_ID_COLUMN} = requested.document_id
            WHERE store.{KNOWLEDGE_STORE_ID_COLUMN} IS NULL
               OR COALESCE(
                    store.{KNOWLEDGE_STORE_METADATA_JSON_COLUMN}::jsonb,
                    '{{}}'::jsonb
                  ) = '{{}}'::jsonb
               OR NOT jsonb_exists(
                    COALESCE(
                        store.{KNOWLEDGE_STORE_METADATA_JSON_COLUMN}::jsonb,
                        '{{}}'::jsonb
                    ),
                    :namespace
                  )
            """
        )
        try:
            with self._session_factory() as db:
                rows = db.execute(
                    statement,
                    {**params, "namespace": namespace},
                )
                return tuple(str(row[0]) for row in rows)
        except Exception as exc:
            logger.exception(
                "v2_vector_store_metadata_namespace_check_failed",
                table_name=self._table_name,
                id_count=len(ids),
                namespace=namespace,
                error=str(exc),
            )
            raise

    def _delete_by_id_prefix_sync(self, prefix: str) -> int:
        statement = text(
            f"""
            DELETE FROM {self._table_name}
            WHERE {KNOWLEDGE_STORE_ID_COLUMN} LIKE :id_prefix ESCAPE '\\'
            """
        )
        try:
            with self._session_factory() as db:
                result = db.execute(
                    statement,
                    {"id_prefix": f"{_escape_like_prefix(prefix)}%"},
                )
                db.commit()
                return int(result.rowcount or 0)
        except Exception as exc:
            logger.exception(
                "v2_vector_store_delete_by_id_prefix_failed",
                table_name=self._table_name,
                prefix=prefix,
                error=str(exc),
            )
            raise

    def _ensure_store(self) -> PGVectorStore:
        if not self._initialized or self._vector_store is None:
            raise RuntimeError(
                "VectorStore not initialized. Call await vector_store.initialize() first."
            )
        return self._vector_store

    def _table_exists(self) -> bool:
        return inspect(sqlalchemy_engine).has_table(self._table_name)

    @staticmethod
    def _resolve_ids(
        documents: Sequence[Document],
        ids: Sequence[str] | None,
    ) -> list[str]:
        if ids is not None:
            if len(ids) != len(documents):
                raise ValueError("document and id counts must match")
            return list(ids)

        resolved_ids = [document.id for document in documents]
        if any(document_id is None for document_id in resolved_ids):
            raise ValueError("document ids are required")
        return [str(document_id) for document_id in resolved_ids]


def _escape_like_prefix(prefix: str) -> str:
    return (
        prefix.replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )
