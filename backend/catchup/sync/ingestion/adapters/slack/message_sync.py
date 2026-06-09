from __future__ import annotations

import asyncio
from typing import Literal

from fastapi.concurrency import run_in_threadpool
from langchain_core.documents import Document
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import ValidationInfo
from pydantic import computed_field
from pydantic import field_validator

from catchup.configs.config import settings
from catchup.connectors.slack.ingestion_service import SlackIngestionService
from catchup.db.models import SyncConnector
from catchup.sync.audit import SyncAuditContext
from catchup.sync.ingestion.schemas import SyncExecutionRequest
from catchup.sync.ingestion.schemas import SyncExecutionResult
from catchup.sync.ingestion.schemas import SyncWindow
from catchup.utils.validation import require_text

SlackIncrementalEventKind = Literal["created", "updated", "deleted"]


class SlackMessageFullSyncExecutionRequest(SyncExecutionRequest):
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    connector: Literal[SyncConnector.SLACK] = SyncConnector.SLACK
    target: Literal["message"] = "message"
    channel_id: str
    channel_name: str
    sync_from_ts: str | None = None
    skip_delete: bool = True
    batch_index: int = 0
    cursor: str | None = None
    audit_context: SyncAuditContext | None = None

    @field_validator("channel_id", "channel_name")
    @classmethod
    def _validate_required_text(cls, value: str, info: ValidationInfo) -> str:
        return require_text(value, info.field_name or "field")

    def log_context(self) -> dict[str, object]:
        return {
            "channel_id": self.channel_id,
            "channel_name": self.channel_name,
            "sync_from_ts_present": bool(self.sync_from_ts),
            "skip_delete": self.skip_delete,
            "batch_index": self.batch_index,
            "cursor_present": bool(self.cursor),
        }


class SlackMessageIncrementalSyncExecutionRequest(SyncExecutionRequest):
    connector: Literal[SyncConnector.SLACK] = SyncConnector.SLACK
    target: Literal["message"] = "message"
    channel_id: str
    record_id: str
    event_kind: SlackIncrementalEventKind = "updated"
    sync_from: str | None = None
    audit_context: SyncAuditContext | None = None

    @field_validator("channel_id", "record_id")
    @classmethod
    def _validate_required_text(cls, value: str, info: ValidationInfo) -> str:
        return require_text(value, info.field_name or "field")

    @computed_field
    @property
    def is_delete_event(self) -> bool:
        return self.event_kind == "deleted"

    def log_context(self) -> dict[str, object]:
        return {
            "channel_id": self.channel_id,
            "record_id": self.record_id,
            "event_kind": self.event_kind,
        }


class SlackMessageFetchResult(BaseModel):
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    requested_count: int = 1
    documents: tuple[Document, ...] = ()
    document_ids: tuple[str, ...] = ()
    delete_document_ids: tuple[str, ...] = ()
    channel_name: str | None = None
    fetch_error_count: int = 0
    batch_index: int = 0
    is_last: bool = True
    next_cursor: str | None = None
    checkpoint: str | None = None

    @property
    def document_count(self) -> int:
        return len(self.documents)

    @property
    def next_cursor_present(self) -> bool:
        return bool(self.next_cursor)

    def connector_log_summary(self) -> dict[str, object]:
        return {
            "document_count": self.document_count,
            "fetch_error_count": self.fetch_error_count,
            "is_last": self.is_last,
            "next_cursor_present": self.next_cursor_present,
        }


class SlackMessageTransformResult(BaseModel):
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    requested_count: int = 1
    documents: tuple[Document, ...] = ()
    document_ids: tuple[str, ...] = ()
    delete_document_ids: tuple[str, ...] = ()
    channel_name: str | None = None
    error_count: int = 0

    @property
    def document_count(self) -> int:
        return len(self.documents)

    def connector_log_summary(self) -> dict[str, object]:
        return {
            "document_count": self.document_count,
            "error_count": self.error_count,
        }


class SlackMessageSummaryResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary_applied: bool = False


class SlackMessagePersistResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    persisted_count: int = 0
    deleted_count: int = 0
    error_count: int = 0
    skipped: bool = False

    def connector_log_summary(self) -> dict[str, object]:
        return {
            "persisted_count": self.persisted_count,
            "deleted_count": self.deleted_count,
            "error_count": self.error_count,
            "skipped": self.skipped,
        }


class SlackMessageSyncExecutionResult(SyncExecutionResult):
    connector: Literal[SyncConnector.SLACK] = SyncConnector.SLACK
    target: Literal["message"] = "message"
    persisted_count: int = 0
    deleted_count: int = 0
    failed_count: int = 0
    skipped: bool = False
    fetched: SlackMessageFetchResult
    transformed: SlackMessageTransformResult
    summary: SlackMessageSummaryResult
    persisted: SlackMessagePersistResult
    batch_index: int = 0
    is_last: bool = True
    next_cursor: str | None = None
    checkpoint: str | None = None

    def connector_log_summary(self) -> dict[str, object]:
        return {
            "persisted_count": self.persisted_count,
            "deleted_count": self.deleted_count,
            "failed_count": self.failed_count,
            "skipped": self.skipped,
            "is_last": self.is_last,
        }


class SlackMessageSyncAdapter:
    """
    Bounded Slack message execution adapter.

    One adapter execution handles exactly one channel target or one claimed incremental message event.
    """

    def __init__(self, *, service: SlackIngestionService) -> None:
        self._service = service
        self._context_loaded = False

    async def fetch(
        self,
        *,
        execution: SlackMessageFullSyncExecutionRequest
        | SlackMessageIncrementalSyncExecutionRequest,
        sync_window: SyncWindow,
    ) -> SlackMessageFetchResult:
        _ = sync_window
        if isinstance(execution, SlackMessageFullSyncExecutionRequest):
            return await self._fetch_full_sync_page(execution)
        return await self._fetch_incremental_record(execution)

    async def transform(
        self,
        *,
        execution: SlackMessageFullSyncExecutionRequest
        | SlackMessageIncrementalSyncExecutionRequest,
        sync_window: SyncWindow,
        fetched: SlackMessageFetchResult,
    ) -> SlackMessageTransformResult:
        _ = execution, sync_window
        return SlackMessageTransformResult(
            requested_count=fetched.requested_count,
            documents=fetched.documents,
            document_ids=fetched.document_ids,
            delete_document_ids=fetched.delete_document_ids,
            channel_name=fetched.channel_name,
            error_count=fetched.fetch_error_count,
        )

    async def summarize(
        self,
        *,
        execution: SlackMessageFullSyncExecutionRequest
        | SlackMessageIncrementalSyncExecutionRequest,
        sync_window: SyncWindow,
        transformed: SlackMessageTransformResult,
    ) -> SlackMessageSummaryResult:
        _ = execution, sync_window, transformed
        return SlackMessageSummaryResult()

    async def persist(
        self,
        *,
        execution: SlackMessageFullSyncExecutionRequest
        | SlackMessageIncrementalSyncExecutionRequest,
        sync_window: SyncWindow,
        transformed: SlackMessageTransformResult,
        summary: SlackMessageSummaryResult,
    ) -> SlackMessagePersistResult:
        _ = sync_window, summary
        if isinstance(execution, SlackMessageFullSyncExecutionRequest):
            return await self._persist_full_sync_page(
                execution=execution,
                transformed=transformed,
            )

        return await self._persist_incremental_record(
            execution=execution,
            transformed=transformed,
        )

    def build_result(
        self,
        *,
        execution: SlackMessageFullSyncExecutionRequest
        | SlackMessageIncrementalSyncExecutionRequest,
        sync_window: SyncWindow,
        fetched: SlackMessageFetchResult,
        transformed: SlackMessageTransformResult,
        summary: SlackMessageSummaryResult,
        persisted: SlackMessagePersistResult,
    ) -> SlackMessageSyncExecutionResult:
        _ = sync_window
        return SlackMessageSyncExecutionResult(
            tenant_id=execution.tenant_id,
            persisted_count=persisted.persisted_count,
            deleted_count=persisted.deleted_count,
            failed_count=persisted.error_count,
            skipped=persisted.skipped,
            fetched=fetched,
            transformed=transformed,
            summary=summary,
            persisted=persisted,
            batch_index=fetched.batch_index,
            is_last=fetched.is_last,
            next_cursor=fetched.next_cursor,
            checkpoint=fetched.checkpoint,
            metadata={
                "batch_index": fetched.batch_index,
                "is_last": fetched.is_last,
                "next_cursor": fetched.next_cursor,
                "checkpoint": fetched.checkpoint,
            },
        )

    async def _persist_full_sync_page(
        self,
        *,
        execution: SlackMessageFullSyncExecutionRequest,
        transformed: SlackMessageTransformResult,
    ) -> SlackMessagePersistResult:
        documents = list(transformed.documents)
        document_ids = list(transformed.document_ids)
        if not documents:
            return SlackMessagePersistResult(error_count=transformed.error_count)

        if self._service.summarizer:
            documents = await self._service._summarize_documents(
                documents,
                channel_name=execution.channel_name,
                audit_context=execution.audit_context,
            )
            document_ids = [doc.id for doc in documents]

        if not execution.skip_delete:
            await self._service.repository.delete_documents(document_ids)

        embeddings = await self._service.repository.generate_embeddings(
            documents,
            audit_context=execution.audit_context,
            context=(
                f"entity_type=message,channel={execution.channel_name},"
                f"batch={execution.batch_index},doc_count={len(documents)}"
            ),
        )
        await self._service.repository.store_with_embeddings(
            documents,
            embeddings,
            document_ids,
            audit_context=execution.audit_context,
            context=(
                f"entity_type=message,channel={execution.channel_name},"
                f"batch={execution.batch_index},doc_count={len(documents)}"
            ),
        )
        return SlackMessagePersistResult(
            persisted_count=len(documents),
            error_count=transformed.error_count,
        )

    async def _fetch_full_sync_page(
        self,
        execution: SlackMessageFullSyncExecutionRequest,
    ) -> SlackMessageFetchResult:
        if not self._context_loaded:
            await run_in_threadpool(self._service._load_ingestion_context_db)
            self._context_loaded = True

        response = await self._service.client.get_conversation_history(
            channel=execution.channel_id,
            oldest=execution.sync_from_ts,
            cursor=execution.cursor,
            limit=settings.SLACK_MESSAGE_BATCH_SIZE,
        )
        messages = [
            self._service._sanitize_message_payload(message)
            for message in response.get("messages", [])
        ]
        thread_messages = [
            msg
            for msg in messages
            if not self._service._should_skip_message(msg) and msg.get("reply_count", 0) > 0
        ]

        if thread_messages:
            thread_replies_list = await asyncio.gather(
                *[
                    self._service._fetch_thread_replies(
                        channel_id=execution.channel_id,
                        thread_ts=msg.get("ts"),
                    )
                    for msg in thread_messages
                ]
            )
            reply_map = {
                msg.get("ts"): replies
                for msg, replies in zip(thread_messages, thread_replies_list)
            }
        else:
            reply_map = {}

        documents, document_ids, errors, latest_synced_ts = await run_in_threadpool(
            self._service._transform_message_batch_blocking,
            messages,
            execution.channel_id,
            execution.channel_name,
            reply_map,
        )
        next_cursor = response.get("response_metadata", {}).get("next_cursor")
        has_more = bool(response.get("has_more") and next_cursor)
        return SlackMessageFetchResult(
            requested_count=1,
            documents=tuple(documents),
            document_ids=tuple(document_ids),
            channel_name=execution.channel_name,
            fetch_error_count=errors,
            batch_index=execution.batch_index,
            is_last=not has_more,
            next_cursor=next_cursor if has_more else None,
            checkpoint=latest_synced_ts,
        )

    async def _fetch_incremental_record(
        self,
        execution: SlackMessageIncrementalSyncExecutionRequest,
    ) -> SlackMessageFetchResult:
        doc_id = f"slack:message:{execution.tenant_id}:{execution.channel_id}:{execution.record_id}"
        if execution.is_delete_event:
            return SlackMessageFetchResult(delete_document_ids=(doc_id,))

        channel_name = await run_in_threadpool(
            self._service._load_channel_context_db,
            execution.channel_id,
        )
        try:
            document = await self._service._fetch_message_document(
                channel_id=execution.channel_id,
                channel_name=channel_name,
                message_id=execution.record_id,
            )
        except Exception as exc:
            error_code = self._service._extract_slack_error_code(exc)
            if error_code in self._service._SKIPPABLE_ERRORS:
                return SlackMessageFetchResult(delete_document_ids=(doc_id,))
            raise

        if document is None:
            return SlackMessageFetchResult(delete_document_ids=(doc_id,))
        return SlackMessageFetchResult(
            documents=(document,),
            document_ids=(document.id,),
            channel_name=channel_name,
        )

    async def _persist_incremental_record(
        self,
        *,
        execution: SlackMessageIncrementalSyncExecutionRequest,
        transformed: SlackMessageTransformResult,
    ) -> SlackMessagePersistResult:
        if transformed.delete_document_ids:
            await self._service.repository.delete_documents(list(transformed.delete_document_ids))
            return SlackMessagePersistResult(deleted_count=len(transformed.delete_document_ids))

        documents = list(transformed.documents)
        if not documents:
            return SlackMessagePersistResult(skipped=True)

        if self._service.summarizer:
            documents = await self._service._summarize_documents(
                documents,
                channel_name=transformed.channel_name or execution.channel_id,
                audit_context=execution.audit_context,
            )
        await self._service.repository.upsert_documents(
            documents,
            [doc.id for doc in documents],
            audit_context=execution.audit_context,
            context=(
                "entity_type=message,"
                f"channel={transformed.channel_name or execution.channel_id},"
                "mode=incremental_exact_refresh,"
                f"doc_count={len(documents)}"
            ),
        )
        return SlackMessagePersistResult(persisted_count=len(documents))
