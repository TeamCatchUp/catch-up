from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Any

import structlog
from langchain_core.documents import Document
from sqlalchemy.orm import Session

from catchup.db.engine import SessionLocal
from catchup.sync.ingestion.adapters.channel_talk.article_author_resolver import (
    ChannelTalkArticleAuthorResolver,
)
from catchup.sync.ingestion.adapters.channel_talk.article_models import (
    ChannelTalkArticlePreparedDocument,
)
from catchup.sync.ingestion.adapters.channel_talk.article_models import (
    ChannelTalkArticleV2BackfillSeed,
)
from catchup.sync.ingestion.vector_records import (
    ChannelTalkDocumentArticleV2RecordMapper,
)

logger = structlog.get_logger(__name__)

SessionFactory = Callable[[], AbstractContextManager[Session]]


class ChannelTalkArticleV2DocumentBuilder:
    """Build Channel Talk Article v2 documents from prepared article chunks."""

    def __init__(
        self,
        *,
        mapper: ChannelTalkDocumentArticleV2RecordMapper | None = None,
        author_resolver: ChannelTalkArticleAuthorResolver | None = None,
        session_factory: SessionFactory = SessionLocal,
    ) -> None:
        self.mapper = mapper or ChannelTalkDocumentArticleV2RecordMapper()
        self.author_resolver = author_resolver or ChannelTalkArticleAuthorResolver()
        self._session_factory = session_factory

    def build_from_prepared_documents(
        self,
        *,
        prepared_documents: tuple[ChannelTalkArticlePreparedDocument, ...],
    ) -> tuple[list[Document], tuple[str, ...]]:
        documents: list[Document] = []
        failed_document_ids: list[str] = []

        with self._session_factory() as db:
            for prepared in prepared_documents:
                try:
                    document = self.mapper.to_document(
                        prepared,
                        content=prepared.page_content,
                        document_id=prepared.document_id,
                        synced_at=prepared.logical_metadata.base.synced_at,
                    )
                    documents.append(
                        self._apply_internal_author_id_from_v2_metadata(db, document)
                    )
                except Exception as exc:
                    logger.warning(
                        "channel_talk_document_article_v2_document_build_failed",
                        connector="channel_talk",
                        entity_type="document_article",
                        article_id=prepared.article_id,
                        document_id=prepared.document_id,
                        error=str(exc),
                        exc_info=True,
                    )
                    failed_document_ids.append(prepared.document_id)

        return documents, tuple(dict.fromkeys(failed_document_ids))

    def build_from_backfill_seeds(
        self,
        *,
        prepared_documents: tuple[ChannelTalkArticlePreparedDocument, ...],
        seed_by_document_id: dict[str, ChannelTalkArticleV2BackfillSeed],
    ) -> tuple[list[Document], list[str], tuple[str, ...]]:
        documents: list[Document] = []
        document_ids: list[str] = []
        failed_document_ids: list[str] = []
        prepared_by_id = {
            prepared.document_id: prepared for prepared in prepared_documents
        }

        with self._session_factory() as db:
            for document_id, seed in seed_by_document_id.items():
                prepared = prepared_by_id.get(document_id)
                if prepared is None:
                    failed_document_ids.append(seed.langchain_id)
                    continue
                try:
                    document = self.mapper.to_document(
                        prepared,
                        content=seed.content,
                        document_id=seed.langchain_id,
                        synced_at=prepared.logical_metadata.base.synced_at,
                    )
                    documents.append(
                        self._apply_internal_author_id_from_v2_metadata(db, document)
                    )
                    document_ids.append(seed.langchain_id)
                except Exception as exc:
                    logger.warning(
                        "channel_talk_document_article_v2_backfill_document_build_failed",
                        connector="channel_talk",
                        entity_type="document_article",
                        article_id=seed.record_id,
                        document_id=seed.langchain_id,
                        error=str(exc),
                        exc_info=True,
                    )
                    failed_document_ids.append(seed.langchain_id)

        return documents, document_ids, tuple(dict.fromkeys(failed_document_ids))

    def _apply_internal_author_id_from_v2_metadata(
        self,
        db: Session,
        document: Document,
    ) -> Document:
        author_id = self._author_id_from_v2_metadata(document.metadata)
        internal_author_id = self.author_resolver.resolve_catchup_user_id(
            db,
            author_id,
        )
        if not internal_author_id:
            return document

        metadata = dict(document.metadata)
        metadata["internal_author_id"] = internal_author_id
        domain_metadata = metadata.get("channel_talk_document_article")
        if isinstance(domain_metadata, dict):
            domain_metadata = dict(domain_metadata)
            author = domain_metadata.get("author")
            if isinstance(author, dict):
                author = dict(author)
                author["internal_user_id"] = internal_author_id
                domain_metadata["author"] = author
                metadata["channel_talk_document_article"] = domain_metadata
        return Document(
            id=document.id,
            page_content=document.page_content,
            metadata=metadata,
        )

    @staticmethod
    def _author_id_from_v2_metadata(metadata: dict[str, Any]) -> str | None:
        domain_metadata = metadata.get("channel_talk_document_article")
        if isinstance(domain_metadata, dict):
            author = domain_metadata.get("author")
            if isinstance(author, dict):
                author_id = author.get("external_user_id")
                if isinstance(author_id, str) and author_id.strip():
                    return author_id.strip()
        return None
