import asyncio
from builtins import ExceptionGroup
from dataclasses import dataclass
import logging
from _collections_abc import AsyncGenerator
from typing import Any

from langchain_core.documents import Document
from slack_sdk.errors import SlackApiError
from sqlalchemy.orm import Session

from catchup.connectors.slack.client import SlackApiClientWrapper
from catchup.connectors.slack.schemas import (
    SlackThreadReply,
    SlackUser,
)
from catchup.connectors.slack.transformers import SlackTransformer
from catchup.components.vector_db.pgvector import PGVectorRepository
from catchup.components.summarizer import SummarizeRequest, SummarizerService, get_summarizer_service
from catchup.configs.config import settings
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
    audit_context: SyncAuditContext | None = None


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
        self.transformer: SlackTransformer | None = None
        self.repository = repository
        self.summarizer: SummarizerService | None = None
        self.user_cache: dict[str, SlackUser] = {}
        self.workspace_domain: str | None = None
        self._initialized = False

    async def initialize(self) -> None:
        if self._initialized:
            return

        logger.info("[SLACK][INGESTION] Initializing service: team_id=%s", self.team_id)

        self.transformer = SlackTransformer(self.user_cache)
        if self.enable_summarization:
            self.summarizer = get_summarizer_service()
            logger.info("[SLACK][INGESTION] Summarization enabled")

        self.repository.ensure_initialized()

        self._initialized = True
        logger.info("[SLACK][INGESTION] Service initialized: team_id=%s", self.team_id)

    def _ensure_initialized(self) -> None:
        if not self._initialized or self.transformer is None:
            raise RuntimeError(
                "SlackIngestionService not initialized. "
                "Call await service.initialize() first."
            )

    def _load_context_from_db(self, db: Session) -> None:
        """메시지 변환에 필요한 user cache/workspace domain을 DB에서 로드한다."""
        try:
            users = domain_repository.get_users_by_team(db, self.team_id, include_deleted=True)
            self.user_cache.clear()
            self.user_cache.update(
                {
                    user.user_id: SlackUser(
                        id=user.user_id,
                        name=user.name,
                        real_name=user.real_name,
                        display_name=user.display_name,
                    )
                    for user in users
                }
            )

            if not self.workspace_domain:
                workspace = domain_repository.get_workspace(db, self.team_id)
                if workspace:
                    self.workspace_domain = workspace.domain

            logger.info(
                "[SLACK][INGESTION] Context loaded: team_id=%s, users=%s, domain=%s",
                self.team_id,
                len(self.user_cache),
                self.workspace_domain,
            )
        except Exception as exc:
            logger.error(
                "[SLACK][INGESTION] Failed to load context: team_id=%s, error=%s",
                self.team_id,
                exc,
                exc_info=True,
            )

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

    def _build_permalink(self, channel_id: str, ts: str) -> str | None:
        if not self.workspace_domain:
            return None
        return f"https://{self.workspace_domain}.slack.com/archives/{channel_id}/p{ts.replace('.', '')}"

    def _pick_latest_ts(self, current: str | None, candidate: str | None) -> str | None:
        if not candidate:
            return current
        if not current:
            return candidate
        try:
            return candidate if float(candidate) > float(current) else current
        except (TypeError, ValueError):
            return current

    async def list_syncable_channels(self) -> list[dict[str, str]]:
        self._ensure_initialized()
        return await self._get_syncable_channels()

    async def sync_channel_messages(
        self,
        *,
        channel_id: str,
        channel_name: str,
        sync_from_ts: str | None,
        db: Session | None = None,
        skip_delete: bool = False,
        audit_context: SyncAuditContext | None = None,
    ) -> TargetSyncResult:
        self._ensure_initialized()
        if db is not None:
            self._load_context_from_db(db)
        sync_ctx = SlackSyncContext(
            channel_id=channel_id,
            channel_name=channel_name,
            sync_from_ts=sync_from_ts,
            skip_delete=skip_delete,
            audit_context=audit_context,
        )
        return await self._sync_channel_messages(
            sync_ctx=sync_ctx,
        )

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
        db: Session,
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

        channel = domain_repository.get_channel(db, channel_id)
        channel_name = channel.name if channel is not None else channel_id
        return await self.sync_channel_messages(
            channel_id=channel_id,
            channel_name=channel_name,
            sync_from_ts=sync_from,
            db=db,
            skip_delete=False,
            audit_context=audit_context,
        )

    async def _fetch_channel_pages(
        self,
        *,
        channel_id: str,
        channel_name: str,
        sync_from_ts: str | None,
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
                thread_replies_list = await asyncio.gather(
                    *[
                        self._fetch_thread_replies(channel_id=channel_id, thread_ts=msg.get("ts"))
                        for msg in thread_messages
                    ]
                )
                reply_map = {
                    msg.get("ts"): replies
                    for msg, replies in zip(thread_messages, thread_replies_list)
                }
            else:
                reply_map = {}

            batch_documents = []
            batch_doc_ids = []
            errors = 0
            batch_latest_synced_ts: str | None = None

            for msg_data in messages:
                if self._should_skip_message(msg_data):
                    continue

                try:
                    message_ts = msg_data.get("ts")
                    replies = reply_map.get(msg_data.get("ts"), [])
                    permalink = self._build_permalink(channel_id, msg_data.get("ts"))
                    message = self.transformer.parse_message(
                        msg_data,
                        channel_id,
                        channel_name,
                        permalink,
                        replies,
                    )
                    doc = self.transformer.transform_message(message, self.team_id)
                    batch_documents.append(doc)
                    batch_doc_ids.append(doc.id)

                    if message_ts:
                        batch_latest_synced_ts = self._pick_latest_ts(
                            batch_latest_synced_ts,
                            message_ts,
                        )
                except Exception as exc:
                    logger.warning(
                        "[SLACK][INGESTION] Failed to transform message: team_id=%s, channel_id=%s, ts=%s, error=%s",
                        self.team_id,
                        channel_id,
                        msg_data.get("ts"),
                        exc,
                    )
                    errors += 1

            if batch_documents:
                yield batch_documents, batch_doc_ids, errors, batch_latest_synced_ts

            if not response.get("has_more"):
                break
            cursor = response.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break

    async def _fetch_thread_replies(
        self,
        *,
        channel_id: str,
        thread_ts: str,
    ) -> list[SlackThreadReply]:
        replies: list[SlackThreadReply] = []
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
                replies.append(self.transformer.parse_reply(msg))

            cursor = response.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break

        return replies

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
