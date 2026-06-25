from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Any

import structlog
from langchain_core.documents import Document
from sqlalchemy.orm import Session

from catchup.connectors.channel_talk.schemas.channel_metadata import (
    ChannelTalkManagerMetadata,
)
from catchup.db.engine import SessionLocal
from catchup.sync.ingestion.adapters.channel_talk.user_chat_author_resolver import (
    ChannelTalkUserChatAuthorResolver,
)
from catchup.sync.ingestion.adapters.channel_talk.user_chat_models import (
    ChannelTalkFetchedUserChat,
)
from catchup.sync.ingestion.adapters.channel_talk.user_chat_models import (
    ChannelTalkUserChatPreparedDocument,
)
from catchup.sync.ingestion.adapters.channel_talk.user_chat_models import (
    ChannelTalkUserChatV2BackfillSeed,
)
from catchup.sync.ingestion.vector_records import ChannelTalkUserChatV2RecordMapper

logger = structlog.get_logger(__name__)

SessionFactory = Callable[[], AbstractContextManager[Session]]


class ChannelTalkUserChatV2DocumentBuilder:
    """Build Channel Talk UserChat v2 documents from hydrated bundles."""

    def __init__(
        self,
        *,
        mapper: ChannelTalkUserChatV2RecordMapper | None = None,
        author_resolver: ChannelTalkUserChatAuthorResolver | None = None,
        session_factory: SessionFactory = SessionLocal,
    ) -> None:
        self.mapper = mapper or ChannelTalkUserChatV2RecordMapper()
        self.author_resolver = author_resolver or ChannelTalkUserChatAuthorResolver()
        self._session_factory = session_factory

    def build_from_prepared_documents(
        self,
        *,
        channel_id: str,
        bundles: tuple[ChannelTalkFetchedUserChat, ...],
        prepared_documents: tuple[ChannelTalkUserChatPreparedDocument, ...],
        managers_by_id: dict[str, ChannelTalkManagerMetadata],
    ) -> tuple[list[Document], tuple[str, ...]]:
        documents: list[Document] = []
        failed_document_ids: list[str] = []

        with self._session_factory() as db:
            for bundle, prepared in zip(bundles, prepared_documents, strict=True):
                try:
                    document = self.mapper.to_document(
                        bundle,
                        channel_id=channel_id,
                        content=prepared.page_content,
                        document_id=prepared.document_id,
                        managers_by_id=managers_by_id,
                        synced_at=prepared.logical_metadata.base.synced_at,
                    )
                    documents.append(
                        self._apply_internal_author_id_from_v2_metadata(db, document)
                    )
                except Exception as exc:
                    logger.warning(
                        "channel_talk_user_chat_v2_document_build_failed",
                        connector="channel_talk",
                        entity_type="user_chat",
                        channel_id=channel_id,
                        user_chat_id=bundle.detail.user_chat_id,
                        document_id=prepared.document_id,
                        error=str(exc),
                        exc_info=True,
                    )
                    failed_document_ids.append(prepared.document_id)

        return documents, tuple(dict.fromkeys(failed_document_ids))

    def build_from_backfill_seeds(
        self,
        *,
        channel_id: str,
        bundles: tuple[ChannelTalkFetchedUserChat, ...],
        seed_by_user_chat_id: dict[str, ChannelTalkUserChatV2BackfillSeed],
        managers_by_id: dict[str, ChannelTalkManagerMetadata],
    ) -> tuple[list[Document], list[str], tuple[str, ...]]:
        documents: list[Document] = []
        document_ids: list[str] = []
        failed_user_chat_ids: list[str] = []

        with self._session_factory() as db:
            for bundle in bundles:
                seed = seed_by_user_chat_id.get(bundle.detail.user_chat_id)
                if seed is None:
                    failed_user_chat_ids.append(bundle.detail.user_chat_id)
                    continue
                try:
                    document = self.mapper.to_document(
                        bundle,
                        channel_id=channel_id,
                        content=seed.content,
                        document_id=seed.langchain_id,
                        managers_by_id=managers_by_id,
                    )
                    documents.append(
                        self._apply_internal_author_id_from_v2_metadata(db, document)
                    )
                except Exception as exc:
                    logger.warning(
                        "channel_talk_user_chat_v2_backfill_document_build_failed",
                        connector="channel_talk",
                        entity_type="user_chat",
                        channel_id=channel_id,
                        user_chat_id=seed.record_id,
                        document_id=seed.langchain_id,
                        error=str(exc),
                        exc_info=True,
                    )
                    failed_user_chat_ids.append(seed.record_id)
                    continue
                document_ids.append(seed.langchain_id)

        return documents, document_ids, tuple(dict.fromkeys(failed_user_chat_ids))

    def _apply_internal_author_id_from_v2_metadata(
        self,
        db: Session,
        document: Document,
    ) -> Document:
        assignee_id = self._assignee_id_from_v2_metadata(document.metadata)
        internal_author_id = self.author_resolver.resolve_catchup_user_id(
            db,
            assignee_id,
        )
        if not internal_author_id:
            return document

        metadata = dict(document.metadata)
        metadata["internal_author_id"] = internal_author_id
        return Document(
            id=document.id,
            page_content=document.page_content,
            metadata=metadata,
        )

    @staticmethod
    def _assignee_id_from_v2_metadata(metadata: dict[str, Any]) -> str | None:
        domain_metadata = metadata.get("channel_talk_user_chat")
        if isinstance(domain_metadata, dict):
            assignment = domain_metadata.get("assignment")
            if isinstance(assignment, dict):
                assignee_id = assignment.get("assignee_id")
                if isinstance(assignee_id, str) and assignee_id.strip():
                    return assignee_id.strip()

        assignee = metadata.get("assignee")
        if isinstance(assignee, dict):
            assignee_id = assignee.get("id") or assignee.get("assignee_id")
            if isinstance(assignee_id, str) and assignee_id.strip():
                return assignee_id.strip()
        return None
