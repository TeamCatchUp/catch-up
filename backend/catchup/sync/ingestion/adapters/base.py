from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from typing import Generic
from typing import TypeVar

import structlog
from langchain_core.documents import Document

from catchup.components.summarizer import SummarizeRequest
from catchup.components.summarizer import SummarizerService
from catchup.components.vector_db.pgvector import PGVectorRepository
from catchup.components.vector_db.v2 import VectorStore
from catchup.sync.audit import SyncAuditContext
from catchup.sync.ingestion.dual_write import DualWriter
from catchup.sync.ingestion.dual_write import DualWriteResult

logger = structlog.get_logger(__name__)

ScopeIdT = TypeVar("ScopeIdT", str, int)
ClientT = TypeVar("ClientT")
TransformerT = TypeVar("TransformerT")


class BaseIngestionAdapter(Generic[ScopeIdT, ClientT, TransformerT]):
    """Common dependencies for adapters sharing this summarization contract.

    The stored id is the connector scope, such as a GitHub installation or
    Slack team. Per-run targets, such as repositories or channels, belong to
    execution objects instead of this base class.
    """

    def __init__(
        self,
        *,
        scope_id: ScopeIdT,
        client: ClientT,
        repository: PGVectorRepository,
        summarizer: SummarizerService | None = None,
        transformer: TransformerT,
        vector_store: VectorStore | None = None,
    ) -> None:
        self.scope_id = scope_id
        self.client = client
        self.repository = repository
        self.summarizer = summarizer
        self.transformer = transformer
        self.vector_store = vector_store

    async def _summarize_documents_with_context(
        self,
        documents: list[Document],
        *,
        source_type_prefix: str,
        default_entity_type: str,
        context: str,
        audit_context: SyncAuditContext | None = None,
        log_event: str,
        log_fields: Mapping[str, Any],
    ) -> list[Document]:
        if not self.summarizer or not documents:
            return documents

        requests = []
        for doc in documents:
            content = doc.metadata.get("contextual_content", doc.page_content)
            entity_type = doc.metadata.get("entity_type", default_entity_type)
            source_type = f"{source_type_prefix}_{entity_type}"
            requests.append(SummarizeRequest(content=content, source_type=source_type))

        summarized = await self.summarizer.summarize_batch(
            requests,
            audit_context=audit_context,
            context=context,
        )

        for doc, summary in zip(documents, summarized):
            doc.page_content = summary

        logger.debug(
            log_event,
            **log_fields,
            doc_count=len(documents),
        )
        return documents

    async def _upsert_v1_v2_documents_dual_write(
        self,
        *,
        v1_documents: list[Document],
        v2_documents: list[Document],
        ids: list[str],
        vector_source_ids: list[str] | None = None,
        audit_context: SyncAuditContext | None,
        context: str,
    ) -> DualWriteResult:
        return await DualWriter(
            repository=self.repository,
            vector_store=self.vector_store,
        ).upsert_documents(
            source_documents=v1_documents,
            vector_documents=v2_documents,
            ids=ids,
            vector_source_ids=vector_source_ids,
            audit_context=audit_context,
            context=context,
        )
