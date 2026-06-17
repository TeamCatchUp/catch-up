from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import structlog
from langchain_core.documents import Document

from catchup.sync.ingestion.document_builders.confluence import (
    ConfluenceTransformResult,
)
from catchup.sync.ingestion.document_builders.confluence import (
    ConfluenceV2PreparedChunk,
)
from catchup.sync.ingestion.vector_records import ConfluenceV2RecordMapper

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class ConfluenceV2BackfillSeed:
    langchain_id: str
    content: str
    record_id: str


class ConfluenceV2DocumentBuilder:
    """Build Confluence v2 documents from prepared chunk transformer output."""

    def __init__(self, *, mapper: ConfluenceV2RecordMapper | None = None) -> None:
        self.mapper = mapper or ConfluenceV2RecordMapper()

    def build_from_transform_results(
        self,
        *,
        cloud_id: str,
        transform_results: tuple[ConfluenceTransformResult, ...],
    ) -> tuple[list[Document], tuple[str, ...]]:
        documents: list[Document] = []
        failed_ids: list[str] = []
        for transform_result in transform_results:
            for prepared in transform_result.v2_prepared_chunks:
                try:
                    documents.append(
                        self.mapper.to_document(
                            prepared,
                            cloud_id=cloud_id,
                            content=prepared.page_content,
                            document_id=prepared.document_id,
                        )
                    )
                except Exception as exc:
                    logger.warning(
                        "confluence_v2_document_build_failed",
                        connector="confluence",
                        entity_type=prepared.entity_type,
                        content_id=prepared.content_id,
                        document_id=prepared.document_id,
                        error=str(exc),
                        exc_info=True,
                    )
                    failed_ids.append(prepared.document_id)
        return documents, tuple(dict.fromkeys(failed_ids))

    def build_from_backfill_seeds(
        self,
        *,
        cloud_id: str,
        prepared_chunks: tuple[ConfluenceV2PreparedChunk, ...],
        seed_by_langchain_id: Mapping[str, ConfluenceV2BackfillSeed],
    ) -> tuple[list[Document], list[str], tuple[str, ...]]:
        documents: list[Document] = []
        document_ids: list[str] = []
        failed_ids: list[str] = []
        prepared_by_id = {
            prepared.document_id: prepared for prepared in prepared_chunks
        }
        for langchain_id, seed in seed_by_langchain_id.items():
            prepared = prepared_by_id.get(langchain_id)
            if prepared is None:
                failed_ids.append(langchain_id)
                continue
            try:
                documents.append(
                    self.mapper.to_document(
                        prepared,
                        cloud_id=cloud_id,
                        content=seed.content,
                        document_id=seed.langchain_id,
                    )
                )
                document_ids.append(seed.langchain_id)
            except Exception as exc:
                logger.warning(
                    "confluence_v2_backfill_document_build_failed",
                    connector="confluence",
                    entity_type=prepared.entity_type,
                    content_id=prepared.content_id,
                    document_id=seed.langchain_id,
                    error=str(exc),
                    exc_info=True,
                )
                failed_ids.append(seed.langchain_id)
        return documents, document_ids, tuple(dict.fromkeys(failed_ids))
