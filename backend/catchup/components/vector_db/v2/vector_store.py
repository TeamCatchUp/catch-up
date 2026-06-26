from __future__ import annotations

from collections.abc import Sequence

import structlog
from langchain.embeddings import Embeddings
from langchain_core.documents import Document
from langchain_postgres import PGEngine
from langchain_postgres import PGVectorStore
from sqlalchemy import inspect

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
from catchup.db.async_engine import async_engine as sqlalchemy_async_engine
from catchup.db.engine import engine as sqlalchemy_engine

logger = structlog.get_logger(__name__)


class VectorStore:
    """(v2 schema)LangChain PGVectorStore Adapter"""

    def __init__(
        self,
        *,
        embeddings: Embeddings,
        pg_engine: PGEngine | None = None,
        vector_store: PGVectorStore | None = None,
        table_name: str = KNOWLEDGE_STORE_TABLE_NAME,
    ) -> None:
        self._embeddings = embeddings
        self._pg_engine = pg_engine
        self._vector_store = vector_store
        self._table_name = table_name
        self._initialized = vector_store is not None

    async def initialize(self) -> None:
        if self._initialized:
            return

        # Bind Existing Async Engine to Vector Store PGEngine
        pg_engine = self._pg_engine or PGEngine.from_engine(sqlalchemy_async_engine)
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
                # 임베딩이 제공되지 않은 경우 LangChain에 등록된 Embedder를 사용하여 content의 내용으로 임베딩 생성
                return await store.aadd_documents(
                    documents=list(documents),
                    ids=document_ids,
                )

            embedding_rows = [list(embedding) for embedding in embeddings]
            if len(embedding_rows) != len(documents):
                raise ValueError("document and embedding counts must match")

            # 임베딩이 제공된 경우 임베딩을 그대로 사용하여 content와 함께 knowledge store에 upsert
            return await store.aadd_embeddings(
                texts=[document.page_content for document in documents],
                embeddings=embedding_rows,
                metadatas=[dict(document.metadata) for document in documents],
                ids=document_ids,
            )
        except Exception as exc:
            logger.exception(
                "upsert_failed",
                table_name=self._table_name,
                id_count=len(ids or documents),
                with_embeddings=embeddings is not None,
                error=str(exc),
            )
            raise

    async def delete(self, ids: Sequence[str]) -> int:
        """
        Document ID 기반 knowledge store row 삭제
        """
        if not ids:
            return 0
        store = self._ensure_store()
        document_ids = list(ids)
        try:
            deleted = await store.adelete(ids=document_ids)
            return len(document_ids) if deleted else 0
        except Exception as exc:
            logger.exception(
                "v2_document_delete_failed",
                table_name=self._table_name,
                id_count=len(document_ids),
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
