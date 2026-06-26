from __future__ import annotations

from typing import Any

import structlog
from fastapi.concurrency import run_in_threadpool
from langchain_core.documents import Document
from slack_sdk.errors import SlackApiError

from catchup.components.summarizer import SummarizerService
from catchup.components.vector_db.pgvector import PGVectorRepository
from catchup.components.vector_db.v2 import V2KnowledgeRepository
from catchup.components.vector_db.v2 import VectorStore
from catchup.connectors.slack.client import SlackApiClientWrapper
from catchup.connectors.slack.client import SlackConnectorApiError
from catchup.connectors.slack.schemas import SlackThreadReply
from catchup.connectors.slack.schemas import SlackUser
from catchup.db.engine import SessionLocal
from catchup.db.slack import domain_repository
from catchup.sync.audit import SyncAuditContext
from catchup.sync.ingestion.adapters.base import BaseIngestionAdapter
from catchup.sync.ingestion.adapters.slack.message_models import (
    ParsedSlackMessageDocument,
)
from catchup.sync.ingestion.adapters.slack.message_v2_document_builder import (
    SlackMessageV2DocumentBuilder,
)
from catchup.sync.ingestion.document_builders.slack import SlackTransformer
from catchup.sync.ingestion.dual_write import apply_page_content_to_vector_content

logger = structlog.get_logger(__name__)

CATCH_UP_ANSWER_PLACEHOLDER = "[CATCH_UP_ANSWER]"


class SlackMessageAdapterBase(
    BaseIngestionAdapter[str, SlackApiClientWrapper, SlackTransformer]
):

    _SKIP_SUBTYPES = frozenset(
        {
            "channel_join",
            "channel_leave",
            "group_join",
            "group_leave",
        }
    )
    _SKIPPABLE_ERRORS = frozenset(
        {
            "not_in_channel",
            "channel_not_found",
            "missing_scope",
        }
    )

    def __init__(
        self,
        *,
        team_id: str,
        client: SlackApiClientWrapper,
        repository: PGVectorRepository,
        bot_user_id: str | None = None,
        summarizer: SummarizerService | None = None,
        transformer: SlackTransformer | None = None,
        vector_store: VectorStore | None = None,
        v2_knowledge_repository: V2KnowledgeRepository | None = None,
        v2_document_builder: SlackMessageV2DocumentBuilder | None = None,
    ) -> None:
        self.user_cache: dict[str, SlackUser] = {}
        transformer = transformer or SlackTransformer(self.user_cache)
        super().__init__(
            scope_id=team_id,
            client=client,
            repository=repository,
            summarizer=summarizer,
            transformer=transformer,
            vector_store=vector_store,
            v2_knowledge_repository=v2_knowledge_repository,
        )
        self.team_id = team_id
        self.bot_user_id = bot_user_id
        self.workspace_domain: str | None = None
        self.message_v2_document_builder = (
            v2_document_builder or SlackMessageV2DocumentBuilder()
        )

    def _load_ingestion_context_from_db(self, db) -> None:
        users = domain_repository.get_users_by_team(
            db,
            self.team_id,
            include_deleted=True,
        )
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
            "slack_message_adapter_context_loaded",
            team_id=self.team_id,
            user_count=len(self.user_cache),
            workspace_domain=self.workspace_domain,
        )

    def _load_ingestion_context(self) -> None:
        with SessionLocal() as db:
            self._load_ingestion_context_from_db(db)

    def _load_channel_context_db(
        self,
        channel_id: str,
    ) -> str:
        with SessionLocal() as db:
            self._load_ingestion_context_from_db(db)
            channel = domain_repository.get_channel(db, channel_id)
            return channel.name if channel is not None else channel_id

    @staticmethod
    def _extract_slack_error_code(exc: Exception) -> str | None:
        if isinstance(exc, SlackConnectorApiError):
            error_code = exc.metadata.get("error")
            return str(error_code) if error_code else None

        if isinstance(exc, SlackApiError):
            error_code = exc.response.get("error")
            return str(error_code) if error_code else None

        return None

    def _should_skip_message_subtype(self, msg_data: dict[str, Any]) -> bool:
        return msg_data.get("subtype") in self._SKIP_SUBTYPES

    def _sanitize_message_payload(
        self,
        msg_data: dict[str, Any],
    ) -> dict[str, Any]:
        if not self.bot_user_id or msg_data.get("user") != self.bot_user_id:
            return msg_data

        sanitized = dict(msg_data)
        sanitized["text"] = CATCH_UP_ANSWER_PLACEHOLDER
        sanitized["blocks"] = []
        sanitized["attachments"] = []
        sanitized["files"] = []
        return sanitized

    def _build_permalink(self, channel_id: str, ts: str) -> str | None:
        if not self.workspace_domain:
            return None
        return (
            f"https://{self.workspace_domain}.slack.com/archives/"
            f"{channel_id}/p{ts.replace('.', '')}"
        )

    @staticmethod
    def _pick_latest_ts(current: str | None, candidate: str | None) -> str | None:
        if not candidate:
            return current
        if not current:
            return candidate
        try:
            return candidate if float(candidate) > float(current) else current
        except (TypeError, ValueError):
            return current

    def _transform_message_bundle_blocking(
        self,
        message_data: dict[str, Any],
        channel_id: str,
        channel_name: str,
        permalink: str | None,
        replies: list[SlackThreadReply],
    ) -> ParsedSlackMessageDocument:
        message = self.transformer.parse_message(
            message_data,
            channel_id,
            channel_name,
            permalink,
            replies,
        )
        document = self.transformer.transform_message(message, self.team_id)
        return ParsedSlackMessageDocument(message=message, document=document)

    def _transform_message_batch_blocking(
        self,
        messages: tuple[dict[str, Any], ...],
        channel_id: str,
        channel_name: str,
        reply_map: dict[str, tuple[SlackThreadReply, ...]],
    ) -> tuple[list[Document], list[str], int, str | None]:
        (
            parsed_documents,
            document_ids,
            errors,
            latest_synced_ts,
            _failed_record_ids,
        ) = self._transform_message_bundle_batch_blocking(
            messages,
            channel_id,
            channel_name,
            reply_map,
        )
        return (
            [parsed.document for parsed in parsed_documents],
            document_ids,
            errors,
            latest_synced_ts,
        )

    def _transform_message_bundle_batch_blocking(
        self,
        messages: tuple[dict[str, Any], ...],
        channel_id: str,
        channel_name: str,
        reply_map: dict[str, tuple[SlackThreadReply, ...]],
    ) -> tuple[
        list[ParsedSlackMessageDocument],
        list[str],
        int,
        str | None,
        tuple[str, ...],
    ]:
        parsed_documents: list[ParsedSlackMessageDocument] = []
        batch_doc_ids: list[str] = []
        failed_record_ids: list[str] = []
        errors = 0
        batch_latest_synced_ts: str | None = None

        for msg_data in messages:
            sanitized_msg_data = self._sanitize_message_payload(msg_data)
            if self._should_skip_message_subtype(sanitized_msg_data):
                continue

            try:
                message_ts = sanitized_msg_data.get("ts")
                replies = list(reply_map.get(sanitized_msg_data.get("ts"), ()))
                permalink = (
                    self._build_permalink(channel_id, message_ts)
                    if message_ts
                    else None
                )
                parsed = self._transform_message_bundle_blocking(
                    sanitized_msg_data,
                    channel_id,
                    channel_name,
                    permalink,
                    replies,
                )
                parsed_documents.append(parsed)
                batch_doc_ids.append(parsed.document.id)

                if message_ts:
                    batch_latest_synced_ts = self._pick_latest_ts(
                        batch_latest_synced_ts,
                        message_ts,
                    )
            except Exception as exc:
                logger.warning(
                    "slack_message_transform_failed",
                    team_id=self.team_id,
                    channel_id=channel_id,
                    message_ts=msg_data.get("ts"),
                    error=str(exc),
                    exc_info=True,
                )
                errors += 1
                message_ts = msg_data.get("ts")
                if message_ts:
                    failed_record_ids.append(str(message_ts))

        return (
            parsed_documents,
            batch_doc_ids,
            errors,
            batch_latest_synced_ts,
            tuple(dict.fromkeys(failed_record_ids)),
        )

    def _build_v2_documents_from_bundles_blocking(
        self,
        parsed_documents: tuple[ParsedSlackMessageDocument, ...],
    ) -> tuple[list[Document], tuple[str, ...]]:
        if not self.vector_store:
            return [], ()
        return self.message_v2_document_builder.build_from_parsed_documents(
            parsed_documents,
            team_id=self.team_id,
        )

    async def _fetch_thread_replies(
        self,
        *,
        channel_id: str,
        thread_ts: str | None,
    ) -> tuple[SlackThreadReply, ...]:
        if not thread_ts:
            return ()

        replies: list[SlackThreadReply] = []
        cursor = None

        while True:
            response = await self.client.get_conversation_replies(
                channel=channel_id,
                ts=thread_ts,
                cursor=cursor,
            )
            messages = response.get("messages", [])

            for msg in messages[1:]:
                sanitized_reply = self._sanitize_message_payload(msg)
                if self._should_skip_message_subtype(sanitized_reply):
                    continue
                replies.append(self.transformer.parse_reply(sanitized_reply))

            cursor = response.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break

        return tuple(replies)

    async def _summarize_documents(
        self,
        documents: list[Document],
        *,
        channel_name: str,
        audit_context: SyncAuditContext | None = None,
    ) -> list[Document]:
        return await self._summarize_documents_with_context(
            documents,
            source_type_prefix="slack",
            default_entity_type="message",
            audit_context=audit_context,
            context=(
                f"entity_type=message,channel={channel_name},"
                f"doc_count={len(documents)}"
            ),
            log_event="slack_documents_summarized",
            log_fields={
                "team_id": self.team_id,
                "channel_name": channel_name,
            },
        )

    async def _transform_messages(
        self,
        *,
        messages: tuple[dict[str, Any], ...],
        channel_id: str,
        channel_name: str,
        reply_map: dict[str, tuple[SlackThreadReply, ...]],
    ) -> tuple[list[Document], list[str], int, str | None]:
        return await run_in_threadpool(
            self._transform_message_batch_blocking,
            messages,
            channel_id,
            channel_name,
            reply_map,
        )

    async def _transform_message_bundles(
        self,
        *,
        messages: tuple[dict[str, Any], ...],
        channel_id: str,
        channel_name: str,
        reply_map: dict[str, tuple[SlackThreadReply, ...]],
    ) -> tuple[
        list[ParsedSlackMessageDocument],
        list[str],
        int,
        str | None,
        tuple[str, ...],
    ]:
        return await run_in_threadpool(
            self._transform_message_bundle_batch_blocking,
            messages,
            channel_id,
            channel_name,
            reply_map,
        )

    async def _build_v2_documents_from_bundles(
        self,
        parsed_documents: tuple[ParsedSlackMessageDocument, ...],
    ) -> tuple[list[Document], tuple[str, ...]]:
        return await run_in_threadpool(
            self._build_v2_documents_from_bundles_blocking,
            parsed_documents,
        )

    @staticmethod
    def _align_v2_documents_to_v1_content(
        *,
        v1_documents: list[Document],
        v2_documents: list[Document],
        operation: str,
    ) -> list[Document]:
        return apply_page_content_to_vector_content(
            source_documents=v1_documents,
            vector_documents=v2_documents,
            connector="slack",
            entity_type="message",
            operation=operation,
        )
