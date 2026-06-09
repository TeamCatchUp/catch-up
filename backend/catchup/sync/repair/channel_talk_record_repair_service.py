from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from datetime import timezone
from functools import lru_cache
from typing import Protocol

import structlog
from fastapi.concurrency import run_in_threadpool

from catchup.components.embedder.constants import EmbeddingProvider
from catchup.components.embedder.factory import get_embedding_service
from catchup.components.vector_db.factory import get_pgvector_repository
from catchup.components.vector_db.pgvector.repository import PGVectorRepository
from catchup.sync.ingestion.adapters.channel_talk.article_full_sync import (
    CHANNEL_TALK_ARTICLE_LANGUAGE,
)
from catchup.sync.ingestion.adapters.channel_talk.article_incremental import (
    ChannelTalkArticleIncrementalIngestionAdapter,
)
from catchup.sync.ingestion.adapters.channel_talk.user_chat_full_sync import (
    ChannelTalkUserChatFullSyncIngestionAdapter,
)
from catchup.sync.ingestion.adapters.channel_talk.user_chat_incremental import (
    ChannelTalkUserChatIncrementalIngestionAdapter,
)
from catchup.connectors.channel_talk.core.user_chat_full_sync_fetcher import (
    ChannelTalkUserChatFullSyncFetcher,
)
from catchup.sync.ingestion.adapters.channel_talk.user_chat_models import (
    ChannelTalkUserChatFullSyncConnection,
)
from catchup.sync.ingestion.adapters.channel_talk.user_chat_models import (
    ChannelTalkUserChatSyncExecutionRequest,
)
from catchup.connectors.channel_talk.credential_loader import (
    load_channel_talk_connection,
)
from catchup.connectors.channel_talk.credential_loader import (
    load_channel_talk_document_connection,
)
from catchup.connectors.channel_talk.document_space.article_full_sync_fetcher import (
    ChannelTalkArticleFullSyncFetcher,
)
from catchup.sync.ingestion.adapters.channel_talk.article_models import (
    ChannelTalkArticleFullSyncConnection,
)
from catchup.sync.ingestion.adapters.channel_talk.article_models import (
    ChannelTalkArticleSyncExecutionRequest,
)
from catchup.connectors.channel_talk.full_sync_helper import (
    is_verified_channel_talk_document_connection,
)
from catchup.connectors.channel_talk.schemas.channel_connection import (
    ChannelTalkCredentialsRecord,
)
from catchup.connectors.channel_talk.schemas.document_article import (
    ChannelTalkDocumentArticleState,
)
from catchup.connectors.channel_talk.schemas.document_connection import (
    ChannelTalkDocumentCredentialsRecord,
)
from catchup.db.models import SyncConnector
from catchup.server.sync.schemas import SyncRecordGapItem
from catchup.server.sync.schemas import SyncRecordGapResponse
from catchup.server.sync.schemas import SyncRecordRetryItemRequest
from catchup.server.sync.schemas import SyncRecordRetryItemResponse
from catchup.server.sync.schemas import SyncRecordRetryRequest
from catchup.server.sync.schemas import SyncRecordRetryResponse
from catchup.sync.common.exceptions import SyncRequestException
from catchup.sync.common.schemas import SyncTargetType
from catchup.sync.ingestion.schemas import SyncWindow
from catchup.sync.repair.context import RecordRepairContext

logger = structlog.get_logger(__name__)

CHANNEL_TALK_USER_CHAT_RECORD_TYPE = "user_chat"
CHANNEL_TALK_DOCUMENT_ARTICLE_RECORD_TYPE = "document_article"
CHANNEL_TALK_EXPECTED_ARTICLE_GAP_STATES = (
    ChannelTalkDocumentArticleState.PUBLISHED,
    ChannelTalkDocumentArticleState.DRAFT,
)


class ChannelTalkRecordRepository(Protocol):
    async def list_channel_talk_user_chat_record_ids(
        self,
        *,
        channel_id: str,
        since: datetime | None = None,
    ) -> list[str]: ...

    async def list_channel_talk_document_article_record_ids(
        self,
        *,
        channel_id: str,
        space_id: str,
        since: datetime | None = None,
    ) -> list[str]: ...


@dataclass(slots=True, frozen=True)
class ChannelTalkTargetRef:
    channel_id: str
    target_type: SyncTargetType
    target_id: str
    target_name: str
    channel_connection: ChannelTalkCredentialsRecord
    document_connection: ChannelTalkDocumentCredentialsRecord | None = None


@dataclass(slots=True, frozen=True)
class ChannelTalkRetryRecords:
    user_chat_ids: list[str] = field(default_factory=list)
    article_ids: list[str] = field(default_factory=list)


def _sort_record_ids(record_ids: set[str] | list[str]) -> list[str]:
    return sorted(record_ids)


def _build_gap_item(
    *,
    record_type: str,
    expected_ids: list[str],
    stored_ids: list[str],
) -> SyncRecordGapItem:
    missing_ids = _sort_record_ids(set(expected_ids) - set(stored_ids))
    return SyncRecordGapItem(
        record_type=record_type,
        expected_count=len(set(expected_ids)),
        stored_count=len(set(stored_ids)),
        missing_count=len(missing_ids),
        missing_ids=missing_ids,
    )


def _is_expected_article_gap_bundle(bundle) -> bool:
    state = str(bundle.state or "").strip()
    if state == ChannelTalkDocumentArticleState.PUBLISHED.value:
        return True
    return (
        state == ChannelTalkDocumentArticleState.DRAFT.value
        and bundle.published_revision is not None
    )


def _build_retry_item(
    *,
    record_type: str,
    requested_ids: list[str],
    succeeded_count: int,
    failed_ids: list[str],
    stored_ids: list[str],
) -> SyncRecordRetryItemResponse:
    return SyncRecordRetryItemResponse(
        record_type=record_type,
        requested_ids=requested_ids,
        retried_count=len(requested_ids),
        succeeded_count=succeeded_count,
        failed_ids=_sort_record_ids(set(failed_ids)),
        remaining_missing_ids=_sort_record_ids(set(requested_ids) - set(stored_ids)),
    )


def _index_retry_records(
    records: list[SyncRecordRetryItemRequest],
    *,
    target_type: SyncTargetType,
) -> ChannelTalkRetryRecords:
    user_chat_ids: list[str] = []
    article_ids: list[str] = []

    for item in records:
        if item.record_type == CHANNEL_TALK_USER_CHAT_RECORD_TYPE:
            if target_type != SyncTargetType.CHANNEL:
                raise SyncRequestException(
                    "unsupported channel_talk record_type for target",
                    code="unsupported_record_type",
                    metadata={
                        "record_type": item.record_type,
                        "target_type": target_type.value,
                    },
                )
            user_chat_ids = list(item.record_ids)
            continue

        if item.record_type == CHANNEL_TALK_DOCUMENT_ARTICLE_RECORD_TYPE:
            if target_type != SyncTargetType.SPACE:
                raise SyncRequestException(
                    "unsupported channel_talk record_type for target",
                    code="unsupported_record_type",
                    metadata={
                        "record_type": item.record_type,
                        "target_type": target_type.value,
                    },
                )
            article_ids = list(item.record_ids)
            continue

        raise SyncRequestException(
            "unsupported channel_talk record_type",
            code="unsupported_record_type",
            metadata={"record_type": item.record_type},
        )

    return ChannelTalkRetryRecords(
        user_chat_ids=user_chat_ids,
        article_ids=article_ids,
    )


class ChannelTalkRecordRepairService:
    def __init__(
        self,
        *,
        repository: ChannelTalkRecordRepository | None = None,
        user_chat_fetcher: ChannelTalkUserChatFullSyncFetcher | None = None,
        article_fetcher: ChannelTalkArticleFullSyncFetcher | None = None,
        user_chat_incremental_adapter: ChannelTalkUserChatIncrementalIngestionAdapter
        | None = None,
        article_incremental_adapter: ChannelTalkArticleIncrementalIngestionAdapter
        | None = None,
    ) -> None:
        self._repository = repository
        self._user_chat_fetcher = user_chat_fetcher
        self._article_fetcher = article_fetcher
        self._user_chat_incremental_adapter = user_chat_incremental_adapter
        self._article_incremental_adapter = article_incremental_adapter

    async def get_record_gaps(
        self,
        *,
        repair_context: RecordRepairContext,
    ) -> SyncRecordGapResponse:
        target = await self._get_target_ref(repair_context=repair_context)
        if target.target_type == SyncTargetType.CHANNEL:
            records = [await self._build_user_chat_gap_item(target, repair_context)]
        elif target.target_type == SyncTargetType.SPACE:
            records = [await self._build_article_gap_item(target, repair_context)]
        else:
            raise SyncRequestException(
                "unsupported channel_talk target_type",
                code="unsupported_target_type",
                metadata={"target_type": target.target_type.value},
            )

        return SyncRecordGapResponse(
            connector=SyncConnector.CHANNEL_TALK,
            scope_id=repair_context.scope_id,
            target_id=repair_context.target_id,
            target_name=target.target_name,
            records=records,
        )

    async def retry_records(
        self,
        *,
        request: SyncRecordRetryRequest,
        repair_context: RecordRepairContext,
    ) -> SyncRecordRetryResponse:
        target = await self._get_target_ref(repair_context=repair_context)
        retry_records = _index_retry_records(
            request.records,
            target_type=target.target_type,
        )
        result_items: list[SyncRecordRetryItemResponse] = []

        if retry_records.user_chat_ids:
            result_items.append(
                await self._retry_user_chats(
                    target=target,
                    repair_context=repair_context,
                    user_chat_ids=retry_records.user_chat_ids,
                )
            )

        if retry_records.article_ids:
            result_items.append(
                await self._retry_articles(
                    target=target,
                    repair_context=repair_context,
                    article_ids=retry_records.article_ids,
                )
            )

        return SyncRecordRetryResponse(
            connector=SyncConnector.CHANNEL_TALK,
            scope_id=repair_context.scope_id,
            target_id=repair_context.target_id,
            target_name=target.target_name,
            records=result_items,
        )

    async def _build_user_chat_gap_item(
        self,
        target: ChannelTalkTargetRef,
        repair_context: RecordRepairContext,
    ) -> SyncRecordGapItem:
        sync_window = self._build_sync_window(repair_context.sync_from_dt)
        connection = ChannelTalkUserChatFullSyncConnection.from_credentials_record(
            target.channel_connection
        )
        fetched = await self._get_user_chat_fetcher().fetch_user_chats(
            connection=connection,
            states=ChannelTalkUserChatFullSyncIngestionAdapter._default_fetch_states(),
            sync_window=sync_window,
        )
        expected_ids = [
            bundle.detail.user_chat_id
            for bundle in fetched.bundles
        ]
        stored_ids = await self._list_user_chat_record_ids(
            channel_id=target.channel_id,
            since=repair_context.sync_from_dt,
        )
        return _build_gap_item(
            record_type=CHANNEL_TALK_USER_CHAT_RECORD_TYPE,
            expected_ids=expected_ids,
            stored_ids=stored_ids,
        )

    async def _build_article_gap_item(
        self,
        target: ChannelTalkTargetRef,
        repair_context: RecordRepairContext,
    ) -> SyncRecordGapItem:
        document_connection = self._require_document_connection(target)
        sync_window = self._build_sync_window(repair_context.sync_from_dt)
        fetched = await self._get_article_fetcher().fetch_articles(
            connection=ChannelTalkArticleFullSyncConnection.from_credentials_record(
                document_connection
            ),
            language=CHANNEL_TALK_ARTICLE_LANGUAGE,
            sync_window=sync_window,
            states=CHANNEL_TALK_EXPECTED_ARTICLE_GAP_STATES,
        )
        expected_ids = [
            bundle.article_id
            for bundle in fetched.bundles
            if _is_expected_article_gap_bundle(bundle)
        ]
        stored_ids = await self._list_article_record_ids(
            channel_id=target.channel_id,
            space_id=target.target_id,
            since=repair_context.sync_from_dt,
        )
        return _build_gap_item(
            record_type=CHANNEL_TALK_DOCUMENT_ARTICLE_RECORD_TYPE,
            expected_ids=expected_ids,
            stored_ids=stored_ids,
        )

    async def _retry_user_chats(
        self,
        *,
        target: ChannelTalkTargetRef,
        repair_context: RecordRepairContext,
        user_chat_ids: list[str],
    ) -> SyncRecordRetryItemResponse:
        sync_window = self._build_sync_window(repair_context.sync_from_dt)
        execution = ChannelTalkUserChatSyncExecutionRequest(
            tenant_id=target.channel_id,
            audit_context=None,
        )
        failed_ids: list[str] = []
        succeeded_count = 0
        adapter = self._get_user_chat_incremental_adapter()

        for user_chat_id in user_chat_ids:
            try:
                persisted = await adapter.sync_user_chat_by_id(
                    execution=execution,
                    user_chat_id=user_chat_id,
                    sync_window=sync_window,
                )
                if persisted.persisted_count > 0:
                    succeeded_count += 1
            except Exception as exc:
                logger.warning(
                    "channel_talk_repair_user_chat_retry_failed",
                    channel_id=target.channel_id,
                    user_chat_id=user_chat_id,
                    error=str(exc),
                    exc_info=True,
                )
                failed_ids.append(user_chat_id)

        stored_ids = await self._list_user_chat_record_ids(
            channel_id=target.channel_id,
            since=repair_context.sync_from_dt,
        )
        return _build_retry_item(
            record_type=CHANNEL_TALK_USER_CHAT_RECORD_TYPE,
            requested_ids=user_chat_ids,
            succeeded_count=succeeded_count,
            failed_ids=failed_ids,
            stored_ids=stored_ids,
        )

    async def _retry_articles(
        self,
        *,
        target: ChannelTalkTargetRef,
        repair_context: RecordRepairContext,
        article_ids: list[str],
    ) -> SyncRecordRetryItemResponse:
        document_connection = self._require_document_connection(target)
        sync_window = self._build_sync_window(repair_context.sync_from_dt)
        execution = ChannelTalkArticleSyncExecutionRequest(
            tenant_id=target.channel_id,
            channel_connection=target.channel_connection,
            document_connection=document_connection,
            audit_context=None,
        )
        failed_ids: list[str] = []
        succeeded_count = 0
        adapter = self._get_article_incremental_adapter()

        for article_id in article_ids:
            try:
                persisted = await adapter.sync_article_by_id(
                    execution=execution,
                    article_id=article_id,
                    sync_window=sync_window,
                )
                if persisted.persisted_count > 0:
                    succeeded_count += 1
            except Exception as exc:
                logger.warning(
                    "channel_talk_repair_document_article_retry_failed",
                    channel_id=target.channel_id,
                    space_id=target.target_id,
                    article_id=article_id,
                    error=str(exc),
                    exc_info=True,
                )
                failed_ids.append(article_id)

        stored_ids = await self._list_article_record_ids(
            channel_id=target.channel_id,
            space_id=target.target_id,
            since=repair_context.sync_from_dt,
        )
        return _build_retry_item(
            record_type=CHANNEL_TALK_DOCUMENT_ARTICLE_RECORD_TYPE,
            requested_ids=article_ids,
            succeeded_count=succeeded_count,
            failed_ids=failed_ids,
            stored_ids=stored_ids,
        )

    async def _list_user_chat_record_ids(
        self,
        *,
        channel_id: str,
        since: datetime,
    ) -> list[str]:
        repository = await self._get_repository()
        return await repository.list_channel_talk_user_chat_record_ids(
            channel_id=channel_id,
            since=since,
        )

    async def _list_article_record_ids(
        self,
        *,
        channel_id: str,
        space_id: str,
        since: datetime,
    ) -> list[str]:
        repository = await self._get_repository()
        return await repository.list_channel_talk_document_article_record_ids(
            channel_id=channel_id,
            space_id=space_id,
            since=since,
        )

    async def _get_target_ref(
        self,
        *,
        repair_context: RecordRepairContext,
    ) -> ChannelTalkTargetRef:
        channel_id = repair_context.scope_id.strip()
        target_id = repair_context.target_id.strip()
        if not channel_id:
            raise SyncRequestException("scope_id is required", code="invalid_scope_id")
        if not target_id:
            raise SyncRequestException("target_id is required", code="invalid_target_id")

        channel_connection = await run_in_threadpool(
            load_channel_talk_connection,
            channel_id,
        )
        if channel_connection is None:
            raise SyncRequestException(
                "channel_talk is not connected for the requested channel",
                code="target_not_found",
                metadata={"scope_id": repair_context.scope_id},
            )
        if channel_connection.channel_id != channel_id:
            raise SyncRequestException(
                "Stored Channel Talk credentials do not match the requested channel",
                code="target_not_found",
                metadata={"scope_id": repair_context.scope_id},
            )

        if repair_context.target_type == SyncTargetType.CHANNEL:
            if target_id != channel_id:
                raise SyncRequestException(
                    "Stored Channel Talk credentials do not match the requested channel target",
                    code="target_not_found",
                    metadata={
                        "scope_id": repair_context.scope_id,
                        "target_id": repair_context.target_id,
                    },
                )
            return ChannelTalkTargetRef(
                channel_id=channel_id,
                target_type=repair_context.target_type,
                target_id=target_id,
                target_name=channel_connection.channel_name or repair_context.target_name,
                channel_connection=channel_connection,
            )

        if repair_context.target_type == SyncTargetType.SPACE:
            document_connection = await run_in_threadpool(
                load_channel_talk_document_connection,
                channel_id,
                target_id,
            )
            if document_connection is None:
                raise SyncRequestException(
                    "channel_talk documents is not connected for the requested channel",
                    code="target_not_found",
                    metadata={
                        "scope_id": repair_context.scope_id,
                        "target_id": repair_context.target_id,
                    },
                )
            if document_connection.channel_id != channel_id:
                raise SyncRequestException(
                    "Stored Channel Talk Documents credentials do not match the requested channel",
                    code="target_not_found",
                    metadata={"scope_id": repair_context.scope_id},
                )
            if not is_verified_channel_talk_document_connection(
                document_connection,
                channel_id=channel_id,
            ):
                raise SyncRequestException(
                    "channel_talk documents credentials are not API verified for the requested channel",
                    code="target_not_found",
                    metadata={"scope_id": repair_context.scope_id},
                )
            if document_connection.space_id != target_id:
                raise SyncRequestException(
                    "Stored Channel Talk Documents credentials do not match the requested space",
                    code="target_not_found",
                    metadata={"target_id": repair_context.target_id},
                )
            return ChannelTalkTargetRef(
                channel_id=channel_id,
                target_type=repair_context.target_type,
                target_id=target_id,
                target_name=document_connection.space_name or repair_context.target_name,
                channel_connection=channel_connection,
                document_connection=document_connection,
            )

        raise SyncRequestException(
            "unsupported channel_talk target_type",
            code="unsupported_target_type",
            metadata={"target_type": repair_context.target_type.value},
        )

    async def _get_repository(self) -> ChannelTalkRecordRepository:
        if self._repository is None:
            repository = self._build_repository()
            try:
                repository.ensure_initialized()
            except RuntimeError:
                await repository.initialize(None)
            self._repository = repository
        return self._repository

    def _get_user_chat_fetcher(self) -> ChannelTalkUserChatFullSyncFetcher:
        if self._user_chat_fetcher is None:
            self._user_chat_fetcher = ChannelTalkUserChatFullSyncFetcher()
        return self._user_chat_fetcher

    def _get_article_fetcher(self) -> ChannelTalkArticleFullSyncFetcher:
        if self._article_fetcher is None:
            self._article_fetcher = ChannelTalkArticleFullSyncFetcher()
        return self._article_fetcher

    def _get_user_chat_incremental_adapter(
        self,
    ) -> ChannelTalkUserChatIncrementalIngestionAdapter:
        if self._user_chat_incremental_adapter is None:
            self._user_chat_incremental_adapter = (
                ChannelTalkUserChatIncrementalIngestionAdapter()
            )
        return self._user_chat_incremental_adapter

    def _get_article_incremental_adapter(
        self,
    ) -> ChannelTalkArticleIncrementalIngestionAdapter:
        if self._article_incremental_adapter is None:
            self._article_incremental_adapter = (
                ChannelTalkArticleIncrementalIngestionAdapter()
            )
        return self._article_incremental_adapter

    @staticmethod
    def _require_document_connection(
        target: ChannelTalkTargetRef,
    ) -> ChannelTalkDocumentCredentialsRecord:
        if target.document_connection is None:
            raise SyncRequestException(
                "channel_talk documents credentials are missing",
                code="target_not_found",
                metadata={"target_id": target.target_id},
            )
        return target.document_connection

    @staticmethod
    def _build_sync_window(window_start: datetime) -> SyncWindow:
        return SyncWindow(
            window_start=window_start,
            window_end=datetime.now(timezone.utc),
        )

    @staticmethod
    def _build_repository() -> PGVectorRepository:
        return get_pgvector_repository(
            embeddings=get_embedding_service(
                EmbeddingProvider.AWS_BEDROCK
            ).get_embedder()
        )


@lru_cache(maxsize=1)
def get_channel_talk_record_repair_service() -> ChannelTalkRecordRepairService:
    return ChannelTalkRecordRepairService()
