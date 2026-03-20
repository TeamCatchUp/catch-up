import asyncio
from builtins import ExceptionGroup
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import logging
from _collections_abc import AsyncGenerator
from typing import Any

from fastapi.concurrency import run_in_threadpool
from langchain_core.documents import Document
from slack_sdk.errors import SlackApiError
from sqlalchemy.orm import Session

from catchup.connectors.slack.client import SlackApiClientWrapper
from catchup.connectors.slack.schemas import (
    SlackUser,
)
from catchup.connectors.slack.transformers import SlackTransformer
from catchup.components.vector_db.pgvector import PGVectorRepository
from catchup.components.summarizer import SummarizeRequest, SummarizerService, get_summarizer_service
from catchup.configs.config import settings
from catchup.db.engine import SessionLocal
from catchup.db.slack import domain_repository
from catchup.sync.audit import SyncAuditContext
from catchup.sync.common.schemas import TargetSyncResult

logger = logging.getLogger(__name__)


@dataclass(slots=True, frozen=True)
class SlackSyncContext:
    channel_id: str
    channel_name: str
    sync_from_ts: str | None
    skip_delete: bool
    context_snapshot: "SlackContextSnapshot"
    audit_context: SyncAuditContext | None = None


@dataclass(slots=True, frozen=True)
class SlackRecordGapItem:
    record_type: str
    expected_count: int = 0
    stored_count: int = 0
    missing_count: int = 0
    missing_ids: list[str] = field(default_factory=list)


@dataclass(slots=True, frozen=True)
class SlackRecordGapReport:
    records: list[SlackRecordGapItem] = field(default_factory=list)


@dataclass(slots=True, frozen=True)
class SlackRecordRetryItem:
    record_type: str
    requested_ids: list[str] = field(default_factory=list)
    retried_count: int = 0
    succeeded_count: int = 0
    failed_ids: list[str] = field(default_factory=list)
    remaining_missing_ids: list[str] = field(default_factory=list)


@dataclass(slots=True, frozen=True)
class SlackRecordRetryResult:
    records: list[SlackRecordRetryItem] = field(default_factory=list)


@dataclass(slots=True, frozen=True)
class SlackContextSnapshot:
    users_by_id: dict[str, SlackUser] = field(default_factory=dict)
    workspace_domain: str | None = None
    loaded_at: datetime | None = None


@dataclass(slots=True, frozen=True)
class SlackFetchedMessage:
    message_id: str
    message_data: dict[str, Any]
    reply_payloads: list[dict[str, Any]] = field(default_factory=list)


class SlackIngestionService:
    """
    Redis Event 단위 Slack 수집/요약/임베딩/저장 서비스.
    """

    def __init__(
        self,
        repository: PGVectorRepository,
        team_id: str,
        access_token: str,
        enable_summarization: bool = True,
    ):
        self.team_id = team_id
        self.enable_summarization = enable_summarization
        self.client = SlackApiClientWrapper(access_token, team_id)
        self.repository = repository
        self.summarizer: SummarizerService | None = None
        self.user_cache: dict[str, SlackUser] = {}
        self.workspace_domain: str | None = None
        self._context_loaded_at: datetime | None = None
        self._context_ttl = timedelta(minutes=5)
        self._initialized = False

    async def initialize(self) -> None:
        if self._initialized:
            return

        logger.info("[SLACK][INGESTION] Initializing service: team_id=%s", self.team_id)

        if self.enable_summarization:
            self.summarizer = get_summarizer_service()
            logger.info("[SLACK][INGESTION] Summarization enabled")

        self.repository.ensure_initialized()

        self._initialized = True
        logger.info("[SLACK][INGESTION] Service initialized: team_id=%s", self.team_id)

    def _ensure_initialized(self) -> None:
        if not self._initialized:
            raise RuntimeError(
                "SlackIngestionService not initialized. "
                "Call await service.initialize() first."
            )

    def _load_context_from_db_sync(self, db: Session) -> SlackContextSnapshot:
        """메시지 변환에 필요한 context snapshot을 DB에서 읽는다."""
        # 리팩토링: context load 실패는 삼키지 않고 상위 sync 경로로 그대로 전파한다.
        users = domain_repository.get_users_by_team(db, self.team_id, include_deleted=True)
        workspace = domain_repository.get_workspace(db, self.team_id)
        loaded_at = datetime.now(timezone.utc)
        snapshot = SlackContextSnapshot(
            users_by_id={
                user.user_id: SlackUser(
                    id=user.user_id,
                    name=user.name,
                    real_name=user.real_name,
                    display_name=user.display_name,
                )
                for user in users
            },
            workspace_domain=workspace.domain if workspace else None,
            loaded_at=loaded_at,
        )
        logger.info(
            "[SLACK][INGESTION] Context snapshot loaded: team_id=%s, users=%s, domain=%s",
            self.team_id,
            len(snapshot.users_by_id),
            snapshot.workspace_domain,
        )
        return snapshot

    _SKIP_SUBTYPES = frozenset(
        {
            "channel_join",
            "channel_leave",
            "group_join",
            "group_leave",
        }
    )

    def _should_skip_message(self, msg_data: dict[str, Any]) -> bool:
        if msg_data.get("subtype") in self._SKIP_SUBTYPES:
            return True
        text = msg_data.get("text", "")
        return len(text) <= 10

    @staticmethod
    def _build_permalink(workspace_domain: str | None, channel_id: str, ts: str) -> str | None:
        if not workspace_domain:
            return None
        return f"https://{workspace_domain}.slack.com/archives/{channel_id}/p{ts.replace('.', '')}"

    def _pick_latest_ts(self, current: str | None, candidate: str | None) -> str | None:
        if not candidate:
            return current
        if not current:
            return candidate
        try:
            return candidate if float(candidate) > float(current) else current
        except (TypeError, ValueError):
            return current

    def _resolve_sync_from_ts(
        self,
        sync_days: int | None,
    ) -> str:
        days = sync_days if sync_days is not None else settings.DEFAULT_SYNC_DAYS
        return f"{(datetime.now(timezone.utc) - timedelta(days=days)).timestamp():.6f}"

    @staticmethod
    def _sync_ts_to_datetime(sync_from_ts: str | None) -> datetime | None:
        if not sync_from_ts:
            return None

        try:
            return datetime.fromtimestamp(float(sync_from_ts), tz=timezone.utc)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _extract_record_ids_from_doc_ids(doc_ids: list[str]) -> list[str]:
        record_ids: list[str] = []
        for doc_id in doc_ids:
            if not doc_id or ":" not in doc_id:
                continue
            record_ids.append(doc_id.rsplit(":", 1)[-1])
        return record_ids

    @staticmethod
    def _sort_record_ids(record_ids: set[str]) -> list[str]:
        def _key(value: str) -> tuple[int, float | str]:
            try:
                return (0, float(value))
            except ValueError:
                return (1, value)

        return sorted(record_ids, key=_key)

    def _build_gap_item(
        self,
        *,
        expected_ids: list[str],
        stored_ids: list[str],
        stored_count: int,
    ) -> SlackRecordGapItem:
        missing_ids = self._sort_record_ids(set(expected_ids) - set(stored_ids))
        return SlackRecordGapItem(
            record_type="message",
            expected_count=len(expected_ids),
            stored_count=stored_count,
            missing_count=len(missing_ids),
            missing_ids=missing_ids,
        )

    def _load_context_from_local_db_sync(self) -> SlackContextSnapshot:
        with SessionLocal() as db:
            return self._load_context_from_db_sync(db)

    def _apply_context_snapshot(self, snapshot: SlackContextSnapshot) -> None:
        self.user_cache = dict(snapshot.users_by_id)
        self.workspace_domain = snapshot.workspace_domain
        self._context_loaded_at = snapshot.loaded_at

    def _get_context_snapshot(self) -> SlackContextSnapshot:
        return SlackContextSnapshot(
            users_by_id=dict(self.user_cache),
            workspace_domain=self.workspace_domain,
            loaded_at=self._context_loaded_at,
        )

    def _should_refresh_context(self) -> bool:
        if not self.user_cache or not self.workspace_domain:
            return True
        if self._context_loaded_at is None:
            return True
        return datetime.now(timezone.utc) - self._context_loaded_at > self._context_ttl

    async def _ensure_context_snapshot_loaded_async(self) -> SlackContextSnapshot:
        # 리팩토링: sync 시작 시 shared mutable cache 대신 snapshot 복사본을 사용한다.
        if self._should_refresh_context():
            snapshot = await run_in_threadpool(self._load_context_from_local_db_sync)
            self._apply_context_snapshot(snapshot)
        return self._get_context_snapshot()

    def _load_channel_name_from_local_db(self, channel_id: str) -> str:
        with SessionLocal() as db:
            channel = domain_repository.get_channel(db, channel_id)
        return channel.name if channel is not None else channel_id

    async def list_syncable_channels(self) -> list[dict[str, str]]:
        self._ensure_initialized()
        return await self._get_syncable_channels()

    async def build_record_gap_report(
        self,
        *,
        channel_id: str,
        channel_name: str,
        sync_from_ts: str | None = None,
        sync_days: int | None = None,
    ) -> SlackRecordGapReport:
        self._ensure_initialized()
        resolved_sync_from_ts = sync_from_ts or self._resolve_sync_from_ts(sync_days)
        since = self._sync_ts_to_datetime(resolved_sync_from_ts)

        expected_ids, stored_doc_ids = await asyncio.gather(
            self._collect_syncable_message_ids(
                channel_id=channel_id,
                sync_from_ts=resolved_sync_from_ts,
            ),
            self.repository.list_slack_record_ids(
                team_id=self.team_id,
                channel_id=channel_id,
                entity_type="message",
                since=since,
            ),
        )

        return SlackRecordGapReport(
            records=[
                self._build_gap_item(
                    expected_ids=expected_ids,
                    stored_ids=self._extract_record_ids_from_doc_ids(stored_doc_ids),
                    stored_count=len(stored_doc_ids),
                )
            ]
        )

    async def retry_missing_records(
        self,
        *,
        channel_id: str,
        channel_name: str,
        sync_from_ts: str | None = None,
        sync_days: int | None = None,
        message_ids: list[str] | None = None,
    ) -> SlackRecordRetryResult:
        self._ensure_initialized()
        requested_ids = list(message_ids or [])
        if not requested_ids:
            return SlackRecordRetryResult(records=[])

        context_snapshot = await self._ensure_context_snapshot_loaded_async()
        documents, failed_ids = await self._fetch_message_documents(
            channel_id=channel_id,
            channel_name=channel_name,
            message_ids=requested_ids,
            context_snapshot=context_snapshot,
        )

        succeeded_count = 0
        if documents:
            try:
                upsert_documents = documents
                if self.summarizer:
                    upsert_documents = await self._summarize_documents(
                        documents,
                        channel_name=channel_name,
                        audit_context=None,
                    )
                await self.repository.upsert_documents(
                    upsert_documents,
                    [doc.id for doc in upsert_documents],
                    audit_context=None,
                    context=f"entity_type=message,channel={channel_name},mode=partial_retry,doc_count={len(upsert_documents)}",
                )
                succeeded_count = len(upsert_documents)
            except Exception as exc:
                logger.error(
                    "[SLACK][REPAIR] Failed to upsert message docs: team_id=%s, channel_id=%s, error=%s",
                    self.team_id,
                    channel_id,
                    exc,
                    exc_info=True,
                )
                failed_ids.extend(
                    self._extract_record_ids_from_doc_ids([doc.id for doc in documents])
                )

        return SlackRecordRetryResult(
            records=[
                SlackRecordRetryItem(
                    record_type="message",
                    requested_ids=requested_ids,
                    retried_count=len(requested_ids),
                    succeeded_count=succeeded_count,
                    failed_ids=self._sort_record_ids(set(failed_ids)),
                )
            ]
        )

    async def sync_channel_messages(
        self,
        *,
        channel_id: str,
        channel_name: str,
        sync_from_ts: str | None,
        skip_delete: bool = False,
        audit_context: SyncAuditContext | None = None,
    ) -> TargetSyncResult:
        self._ensure_initialized()
        context_snapshot = await self._ensure_context_snapshot_loaded_async()
        sync_ctx = SlackSyncContext(
            channel_id=channel_id,
            channel_name=channel_name,
            sync_from_ts=sync_from_ts,
            skip_delete=skip_delete,
            context_snapshot=context_snapshot,
            audit_context=audit_context,
        )
        return await self._sync_channel_messages(
            sync_ctx=sync_ctx,
        )

    def _build_message_document(
        self,
        transformer: SlackTransformer,
        *,
        channel_id: str,
        channel_name: str,
        msg_data: dict[str, Any],
        reply_payloads: list[dict[str, Any]],
        context_snapshot: SlackContextSnapshot,
    ) -> Document:
        message_ts = msg_data.get("ts", "")
        permalink = self._build_permalink(
            context_snapshot.workspace_domain,
            channel_id,
            message_ts,
        )
        replies = [transformer.parse_reply(reply) for reply in reply_payloads]
        message = transformer.parse_message(
            msg_data,
            channel_id,
            channel_name,
            permalink,
            replies,
        )
        return transformer.transform_message(message, self.team_id)

    def _build_message_batch_sync(
        self,
        channel_id: str,
        channel_name: str,
        message_batch: list[dict[str, Any]],
        reply_map: dict[str, list[dict[str, Any]]],
        context_snapshot: SlackContextSnapshot,
    ) -> tuple[list[Document], list[str], int, str | None]:
        transformer = SlackTransformer(context_snapshot.users_by_id)
        documents: list[Document] = []
        doc_ids: list[str] = []
        error_count = 0
        latest_synced_ts: str | None = None

        for msg_data in message_batch:
            if self._should_skip_message(msg_data):
                continue

            try:
                message_ts = msg_data.get("ts")
                document = self._build_message_document(
                    transformer,
                    channel_id=channel_id,
                    channel_name=channel_name,
                    msg_data=msg_data,
                    reply_payloads=reply_map.get(message_ts, []),
                    context_snapshot=context_snapshot,
                )
                documents.append(document)
                doc_ids.append(document.id)
                latest_synced_ts = self._pick_latest_ts(latest_synced_ts, message_ts)
            except Exception as exc:
                logger.warning(
                    "[SLACK][INGESTION] Failed to build message doc: team_id=%s, channel_id=%s, ts=%s, error=%s",
                    self.team_id,
                    channel_id,
                    msg_data.get("ts"),
                    exc,
                )
                error_count += 1

        return documents, doc_ids, error_count, latest_synced_ts

    def _build_message_documents_sync(
        self,
        channel_id: str,
        channel_name: str,
        message_items: list[SlackFetchedMessage],
        context_snapshot: SlackContextSnapshot,
    ) -> tuple[list[Document], list[str]]:
        transformer = SlackTransformer(context_snapshot.users_by_id)
        documents: list[Document] = []
        failed_ids: list[str] = []

        for item in message_items:
            try:
                documents.append(
                    self._build_message_document(
                        transformer,
                        channel_id=channel_id,
                        channel_name=channel_name,
                        msg_data=item.message_data,
                        reply_payloads=item.reply_payloads,
                        context_snapshot=context_snapshot,
                    )
                )
            except Exception as exc:
                logger.warning(
                    "[SLACK][REPAIR] Failed to build message doc: team_id=%s, channel_id=%s, ts=%s, error=%s",
                    self.team_id,
                    channel_id,
                    item.message_id,
                    exc,
                )
                failed_ids.append(item.message_id)

        return documents, failed_ids

    async def _get_syncable_channels(self) -> list[dict[str, str]]:
        channels: list[dict[str, str]] = []
        cursor: str | None = None

        while True:
            response = await self.client.list_conversations(
                types="public_channel,private_channel",
                cursor=cursor,
            )
            for channel in response.get("channels", []):
                channel_id = channel.get("id")
                channels.append(
                    {
                        "id": channel_id,
                        "name": channel.get("name", channel_id),
                    }
                )

            cursor = response.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break

        return channels

    async def _sync_channel_messages(
        self,
        *,
        sync_ctx: SlackSyncContext,
    ) -> TargetSyncResult:
        """단일 이벤트 단위: fetch -> summarize -> embed -> store."""
        skippable_errors = {"not_in_channel", "channel_not_found", "missing_scope"}

        fetch_q: asyncio.Queue = asyncio.Queue(maxsize=2)
        embed_q: asyncio.Queue = asyncio.Queue(maxsize=2)
        store_q: asyncio.Queue = asyncio.Queue(maxsize=2)

        async def _fetch_stage() -> None:
            async for batch in self._fetch_channel_pages(
                channel_id=sync_ctx.channel_id,
                channel_name=sync_ctx.channel_name,
                sync_from_ts=sync_ctx.sync_from_ts,
                context_snapshot=sync_ctx.context_snapshot,
            ):
                await fetch_q.put(batch)
            await fetch_q.put(None)

        async def _summarize_stage() -> None:
            while (batch := await fetch_q.get()) is not None:
                batch_docs, batch_ids, batch_errors, batch_latest_synced_ts = batch
                if self.summarizer:
                    batch_docs = await self._summarize_documents(
                        batch_docs,
                        channel_name=sync_ctx.channel_name,
                        audit_context=sync_ctx.audit_context,
                    )
                await embed_q.put(
                    (batch_docs, batch_ids, batch_errors, batch_latest_synced_ts)
                )
            await embed_q.put(None)

        async def _embed_stage() -> None:
            while (batch := await embed_q.get()) is not None:
                batch_docs, batch_ids, batch_errors, batch_latest_synced_ts = batch
                embeddings = await self.repository.generate_embeddings(
                    batch_docs,
                    audit_context=sync_ctx.audit_context,
                    context=(
                        f"entity_type=message,channel={sync_ctx.channel_name},"
                        f"doc_count={len(batch_docs)}"
                    ),
                )
                await store_q.put(
                    (
                        batch_docs,
                        batch_ids,
                        batch_errors,
                        embeddings,
                        batch_latest_synced_ts,
                    )
                )
            await store_q.put(None)

        async def _store_stage() -> tuple[int, int, str | None]:
            synced_count = 0
            errors = 0
            latest_synced_ts: str | None = None
            while (batch := await store_q.get()) is not None:
                (
                    batch_docs,
                    batch_ids,
                    batch_errors,
                    embeddings,
                    batch_latest_synced_ts,
                ) = batch

                errors += batch_errors
                if not sync_ctx.skip_delete:
                    await self.repository.delete_documents(batch_ids)
                await self.repository.store_with_embeddings(
                    batch_docs,
                    embeddings,
                    batch_ids,
                    audit_context=sync_ctx.audit_context,
                    context=(
                        f"entity_type=message,channel={sync_ctx.channel_name},"
                        f"doc_count={len(batch_docs)}"
                    ),
                )

                synced_count += len(batch_docs)
                latest_synced_ts = self._pick_latest_ts(
                    latest_synced_ts,
                    batch_latest_synced_ts,
                )

            return synced_count, errors, latest_synced_ts

        try:
            async with asyncio.TaskGroup() as tg:
                tg.create_task(_fetch_stage())
                tg.create_task(_summarize_stage())
                tg.create_task(_embed_stage())
                store_task = tg.create_task(_store_stage())

            synced_count, errors, _latest_synced_ts = store_task.result()

        except ExceptionGroup as eg:
            for exc in eg.exceptions:
                if isinstance(exc, SlackApiError):
                    if exc.response.get("error", "") in skippable_errors:
                        logger.info(
                            "[SLACK][INGESTION] Skipped channel: team_id=%s, channel=%s(%s), reason=%s",
                            self.team_id,
                            sync_ctx.channel_name,
                            sync_ctx.channel_id,
                            exc.response.get("error"),
                        )
                        return TargetSyncResult(skipped=True)

            raise eg.exceptions[0] from None

        logger.debug(
            "[SLACK][INGESTION] Channel synced: team_id=%s, channel=%s(%s), synced=%s, errors=%s",
            self.team_id,
            sync_ctx.channel_name,
            sync_ctx.channel_id,
            synced_count,
            errors,
        )
        return TargetSyncResult(
            synced_count=synced_count,
            error_count=errors,
        )

    async def incremental_sync(
        self,
        *,
        channel_id: str,
        record_id: str,
        event_kind: str,
        sync_from: str | None,
        audit_context: SyncAuditContext | None = None,
    ) -> TargetSyncResult:
        normalized_event_kind = event_kind.strip().lower()
        if normalized_event_kind == "deleted":
            doc_id = f"slack:message:{self.team_id}:{channel_id}:{record_id}"
            await self.repository.delete_documents([doc_id])
            return TargetSyncResult(synced_count=1)

        channel_name = await run_in_threadpool(
            self._load_channel_name_from_local_db,
            channel_id,
        )
        return await self.sync_channel_messages(
            channel_id=channel_id,
            channel_name=channel_name,
            sync_from_ts=sync_from,
            skip_delete=False,
            audit_context=audit_context,
        )

    async def _fetch_channel_pages(
        self,
        *,
        channel_id: str,
        channel_name: str,
        sync_from_ts: str | None,
        context_snapshot: SlackContextSnapshot,
    ) -> AsyncGenerator[tuple[list[Document], list[str], int, str | None], None]:
        cursor = None

        while True:
            response = await self.client.get_conversation_history(
                channel=channel_id,
                oldest=sync_from_ts,
                cursor=cursor,
                limit=settings.SLACK_MESSAGE_BATCH_SIZE,
            )

            messages = response.get("messages", [])
            thread_messages = [
                msg
                for msg in messages
                if not self._should_skip_message(msg) and msg.get("reply_count", 0) > 0
            ]

            if thread_messages:
                thread_reply_payloads = await asyncio.gather(
                    *[
                        self._fetch_thread_reply_payloads(
                            channel_id=channel_id,
                            thread_ts=msg.get("ts"),
                        )
                        for msg in thread_messages
                    ]
                )
                reply_map = {
                    msg.get("ts"): replies
                    for msg, replies in zip(thread_messages, thread_reply_payloads)
                }
            else:
                reply_map = {}

            # 리팩토링: message parse/transform은 batch helper를 통해 event loop 밖으로 내린다.
            batch_documents, batch_doc_ids, errors, batch_latest_synced_ts = await run_in_threadpool(
                self._build_message_batch_sync,
                channel_id,
                channel_name,
                messages,
                reply_map,
                context_snapshot,
            )

            if batch_documents:
                yield batch_documents, batch_doc_ids, errors, batch_latest_synced_ts

            if not response.get("has_more"):
                break
            cursor = response.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break

    async def _collect_syncable_message_ids(
        self,
        *,
        channel_id: str,
        sync_from_ts: str | None,
    ) -> list[str]:
        message_ids: list[str] = []
        cursor: str | None = None

        while True:
            response = await self.client.get_conversation_history(
                channel=channel_id,
                oldest=sync_from_ts,
                cursor=cursor,
                limit=settings.SLACK_MESSAGE_BATCH_SIZE,
            )

            for message in response.get("messages", []):
                if self._should_skip_message(message):
                    continue
                message_ts = message.get("ts")
                if message_ts:
                    message_ids.append(message_ts)

            if not response.get("has_more"):
                break

            cursor = response.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break

        return message_ids

    async def _fetch_message_documents(
        self,
        *,
        channel_id: str,
        channel_name: str,
        message_ids: list[str],
        context_snapshot: SlackContextSnapshot,
    ) -> tuple[list[Document], list[str]]:
        fetched_messages: list[SlackFetchedMessage] = []
        failed_ids: list[str] = []

        async def _fetch_one(message_id: str) -> tuple[str, SlackFetchedMessage | None, bool]:
            try:
                message_item = await self._fetch_message_item(
                    channel_id=channel_id,
                    message_id=message_id,
                )
                return message_id, message_item, message_item is None
            except Exception as exc:
                logger.warning(
                    "[SLACK][REPAIR] Failed to fetch message: team_id=%s, channel_id=%s, ts=%s, error=%s",
                    self.team_id,
                    channel_id,
                    message_id,
                    exc,
                )
                return message_id, None, True

        batch_size = max(1, settings.SLACK_SYNC_MAX_CONCURRENT_REQUESTS)
        for start in range(0, len(message_ids), batch_size):
            batch_ids = message_ids[start : start + batch_size]
            results = await asyncio.gather(*[_fetch_one(message_id) for message_id in batch_ids])

            for message_id, message_item, failed in results:
                if failed or message_item is None:
                    failed_ids.append(message_id)
                    continue
                fetched_messages.append(message_item)

        # 리팩토링: retry도 main sync와 같은 message builder 계층을 재사용한다.
        documents, build_failed_ids = await run_in_threadpool(
            self._build_message_documents_sync,
            channel_id,
            channel_name,
            fetched_messages,
            context_snapshot,
        )
        failed_ids.extend(build_failed_ids)
        return documents, self._sort_record_ids(set(failed_ids))

    async def _fetch_message_item(
        self,
        *,
        channel_id: str,
        message_id: str,
    ) -> SlackFetchedMessage | None:
        message_data = await self.client.get_message(
            channel=channel_id,
            ts=message_id,
        )
        if not message_data or self._should_skip_message(message_data):
            return None

        reply_payloads: list[dict[str, Any]] = []
        if message_data.get("reply_count", 0) > 0:
            reply_payloads = await self._fetch_thread_reply_payloads(
                channel_id=channel_id,
                thread_ts=message_id,
            )

        return SlackFetchedMessage(
            message_id=message_id,
            message_data=message_data,
            reply_payloads=reply_payloads,
        )

    async def _fetch_thread_reply_payloads(
        self,
        *,
        channel_id: str,
        thread_ts: str,
    ) -> list[dict[str, Any]]:
        reply_payloads: list[dict[str, Any]] = []
        cursor = None

        while True:
            response = await self.client.get_conversation_replies(
                channel=channel_id,
                ts=thread_ts,
                cursor=cursor,
            )
            messages = response.get("messages", [])

            # 첫 번째 메시지는 parent이므로 skip
            for msg in messages[1:]:
                if self._should_skip_message(msg):
                    continue
                reply_payloads.append(msg)

            cursor = response.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break

        return reply_payloads

    async def _summarize_documents(
        self,
        documents: list[Document],
        *,
        channel_name: str,
        audit_context: SyncAuditContext | None = None,
    ) -> list[Document]:
        if not self.summarizer or not documents:
            return documents

        requests = []
        for doc in documents:
            content = doc.metadata.get("contextual_content", doc.page_content)
            entity_type = doc.metadata.get("entity_type", "message")
            source_type = f"slack_{entity_type}"
            requests.append(SummarizeRequest(content=content, source_type=source_type))

        summarized = await self.summarizer.summarize_batch(
            requests,
            audit_context=audit_context,
            context=(
                f"entity_type=message,channel={channel_name},"
                f"doc_count={len(documents)}"
            ),
        )

        for doc, summary in zip(documents, summarized):
            doc.page_content = summary

        logger.debug(
            "[SLACK][INGESTION] Summarized docs: team_id=%s, count=%s",
            self.team_id,
            len(documents),
        )
        return documents
