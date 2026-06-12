from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field

import structlog
from langchain_core.documents import Document

from catchup.components.vector_db.pgvector import PGVectorRepository
from catchup.components.vector_db.v2 import VectorStore
from catchup.sync.audit import SyncAuditContext

logger = structlog.get_logger(__name__)


@dataclass(slots=True, frozen=True)
class DualWriteResult:
    persisted_ids: list[str] = field(default_factory=list)
    vector_failed_ids: tuple[str, ...] = ()


def apply_page_content_to_vector_content(
    *,
    source_documents: list[Document],
    vector_documents: list[Document],
    connector: str,
    entity_type: str,
    operation: str,
) -> list[Document]:
    if not vector_documents:
        return []

    source_by_id = {doc.id: doc for doc in source_documents}
    missing_source_ids = [
        doc.id for doc in vector_documents if doc.id not in source_by_id
    ]
    if missing_source_ids:
        logger.error(
            "dual_write_document_alignment_failed",
            connector=connector,
            operation=operation,
            entity_type=entity_type,
            source_count=len(source_documents),
            vector_count=len(vector_documents),
            missing_source_ids=missing_source_ids,
        )

    return [
        Document(
            id=vector_document.id,
            page_content=source_by_id[vector_document.id].page_content,
            metadata=dict(vector_document.metadata),
        )
        for vector_document in vector_documents
        if vector_document.id in source_by_id
    ]


class DualWriter:
    """Persist source documents and mirror matching rows into vector store."""

    def __init__(
        self,
        *,
        repository: PGVectorRepository,
        vector_store: VectorStore | None,
    ) -> None:
        self._repository = repository
        self._vector_store = vector_store

    async def upsert_documents(
        self,
        *,
        source_documents: list[Document],
        vector_documents: list[Document],
        ids: list[str],
        audit_context: SyncAuditContext | None,
        context: str,
    ) -> DualWriteResult:
        if self._vector_store is None or not vector_documents:
            persisted_ids = await self._repository.upsert_documents(
                source_documents,
                ids,
                audit_context=audit_context,
                context=context,
            )
            return DualWriteResult(persisted_ids=persisted_ids)

        embeddings = await self._repository.generate_embeddings(
            source_documents,
            audit_context=audit_context,
            context=context,
        )
        await self._repository.delete_documents(ids)
        result_ids = await self._repository.store_with_embeddings(
            source_documents,
            embeddings,
            ids,
            audit_context=audit_context,
            context=context,
        )

        vector_failed_ids: tuple[str, ...] = ()
        try:
            embedding_by_id = dict(zip(ids, embeddings, strict=True))
            vector_ids = [doc.id for doc in vector_documents]
            vector_embeddings = [embedding_by_id[doc_id] for doc_id in vector_ids]
            await self._vector_store.upsert_documents(
                vector_documents,
                ids=vector_ids,
                embeddings=vector_embeddings,
            )
        except Exception:
            vector_failed_ids = tuple(doc.id for doc in vector_documents)

        return DualWriteResult(
            persisted_ids=result_ids,
            vector_failed_ids=vector_failed_ids,
        )
