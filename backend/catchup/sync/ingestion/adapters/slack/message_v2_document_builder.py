from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager

import structlog
from langchain_core.documents import Document
from sqlalchemy.orm import Session

from catchup.db.engine import SessionLocal
from catchup.sync.ingestion.adapters.slack.message_author_resolver import (
    SlackMessageAuthorResolver,
)
from catchup.sync.ingestion.adapters.slack.message_models import (
    ParsedSlackMessageDocument,
)
from catchup.sync.ingestion.adapters.slack.message_models import (
    SlackMessageV2BackfillSeed,
)
from catchup.sync.ingestion.vector_records.slack_message_mapper import (
    SlackMessageV2RecordMapper,
)

logger = structlog.get_logger(__name__)

SessionFactory = Callable[[], AbstractContextManager[Session]]


class SlackMessageV2DocumentBuilder:
    """Build Slack Message v2 documents with author resolution isolated from adapters."""

    def __init__(
        self,
        *,
        mapper: SlackMessageV2RecordMapper | None = None,
        author_resolver: SlackMessageAuthorResolver | None = None,
        session_factory: SessionFactory = SessionLocal,
    ) -> None:
        self.mapper = mapper or SlackMessageV2RecordMapper()
        self.author_resolver = author_resolver or SlackMessageAuthorResolver()
        self._session_factory = session_factory

    def build_from_parsed_documents(
        self,
        parsed_documents: tuple[ParsedSlackMessageDocument, ...],
        *,
        team_id: str,
    ) -> tuple[list[Document], tuple[str, ...]]:
        documents: list[Document] = []
        failed_document_ids: list[str] = []

        with self._session_factory() as db:
            for parsed in parsed_documents:
                try:
                    documents.append(
                        self._build_document(
                            db,
                            parsed,
                            team_id=team_id,
                            content=parsed.document.page_content,
                            document_id=parsed.document.id,
                        )
                    )
                except Exception as exc:
                    logger.warning(
                        "slack_message_v2_document_build_failed",
                        team_id=team_id,
                        channel_id=parsed.message.channel_id,
                        message_ts=parsed.message.ts,
                        document_id=parsed.document.id,
                        error=str(exc),
                        exc_info=True,
                    )
                    failed_document_ids.append(parsed.document.id)

        return documents, tuple(dict.fromkeys(failed_document_ids))

    def build_from_backfill_seeds(
        self,
        parsed_documents: tuple[ParsedSlackMessageDocument, ...],
        *,
        team_id: str,
        seed_by_message_ts: dict[str, SlackMessageV2BackfillSeed],
    ) -> tuple[list[Document], list[str], tuple[str, ...]]:
        documents: list[Document] = []
        document_ids: list[str] = []
        failed_message_ts_values: list[str] = []

        with self._session_factory() as db:
            for parsed in parsed_documents:
                seed = seed_by_message_ts.get(parsed.message.ts)
                if seed is None:
                    failed_message_ts_values.append(parsed.message.ts)
                    continue
                try:
                    documents.append(
                        self._build_document(
                            db,
                            parsed,
                            team_id=team_id,
                            content=seed.content,
                            document_id=seed.langchain_id,
                        )
                    )
                except Exception as exc:
                    logger.warning(
                        "slack_message_v2_backfill_document_build_failed",
                        team_id=team_id,
                        channel_id=parsed.message.channel_id,
                        message_ts=seed.record_id,
                        document_id=seed.langchain_id,
                        error=str(exc),
                        exc_info=True,
                    )
                    failed_message_ts_values.append(seed.record_id)
                    continue
                document_ids.append(seed.langchain_id)

        return documents, document_ids, _dedupe(tuple(failed_message_ts_values))

    def _build_document(
        self,
        db: Session,
        parsed: ParsedSlackMessageDocument,
        *,
        team_id: str,
        content: str,
        document_id: str,
    ) -> Document:
        internal_author_id = self.author_resolver.resolve_catchup_user_id(
            db,
            parsed.message.user_id,
        )
        document = self.mapper.to_document(
            parsed.message,
            team_id=team_id,
            content=content,
            internal_author_id=internal_author_id,
        )
        if document.id == document_id:
            return document
        return Document(
            id=document_id,
            page_content=document.page_content,
            metadata=dict(document.metadata),
        )


def _dedupe(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))
