from __future__ import annotations

from fastapi.concurrency import run_in_threadpool

from catchup.sync.ingestion.adapters.slack.message_base import SlackMessageAdapterBase
from catchup.sync.ingestion.adapters.slack.message_models import SlackMessageFetchResult
from catchup.sync.ingestion.adapters.slack.message_models import (
    SlackMessageIncrementalSyncExecutionRequest,
)
from catchup.sync.ingestion.adapters.slack.message_models import (
    SlackMessagePersistResult,
)
from catchup.sync.ingestion.adapters.slack.message_models import (
    SlackMessageSummaryResult,
)
from catchup.sync.ingestion.adapters.slack.message_models import (
    SlackMessageSyncExecutionResult,
)
from catchup.sync.ingestion.adapters.slack.message_models import (
    SlackMessageTransformResult,
)
from catchup.sync.ingestion.schemas import SyncWindow


class SlackMessageIncrementalSyncAdapter(SlackMessageAdapterBase):
    """Slack exact-message incremental sync adapter."""

    async def fetch(
        self,
        *,
        execution: SlackMessageIncrementalSyncExecutionRequest,
        sync_window: SyncWindow,
    ) -> SlackMessageFetchResult:
        _ = sync_window
        doc_id = (
            f"slack:message:{execution.tenant_id}:"
            f"{execution.channel_id}:{execution.record_id}"
        )
        if execution.is_delete_event:
            return SlackMessageFetchResult(delete_document_ids=(doc_id,))

        channel_name = await run_in_threadpool(
            self._load_channel_context_db,
            execution.channel_id,
        )
        try:
            message_data = await self.client.get_message(
                channel=execution.channel_id,
                ts=execution.record_id,
            )
        except Exception as exc:
            error_code = self._extract_slack_error_code(exc)
            if error_code in self._SKIPPABLE_ERRORS:
                return SlackMessageFetchResult(delete_document_ids=(doc_id,))
            raise

        if not message_data:
            return SlackMessageFetchResult(delete_document_ids=(doc_id,))

        sanitized_message = self._sanitize_message_payload(message_data)
        if self._should_skip_message(sanitized_message):
            return SlackMessageFetchResult(delete_document_ids=(doc_id,))

        if sanitized_message.get("reply_count", 0) > 0:
            replies = await self._fetch_thread_replies(
                channel_id=execution.channel_id,
                thread_ts=execution.record_id,
            )
            reply_map = {execution.record_id: replies}
        else:
            reply_map = {}

        return SlackMessageFetchResult(
            requested_count=1,
            parent_messages=(sanitized_message,),
            reply_map=reply_map,
            channel_name=channel_name,
        )

    async def transform(
        self,
        *,
        execution: SlackMessageIncrementalSyncExecutionRequest,
        sync_window: SyncWindow,
        fetched: SlackMessageFetchResult,
    ) -> SlackMessageTransformResult:
        _ = sync_window
        if fetched.delete_document_ids:
            return SlackMessageTransformResult(
                requested_count=fetched.requested_count,
                delete_document_ids=fetched.delete_document_ids,
                channel_name=fetched.channel_name,
                error_count=fetched.fetch_error_count,
            )

        documents, document_ids, errors, latest_synced_ts = await self._transform_messages(
            messages=fetched.parent_messages,
            channel_id=execution.channel_id,
            channel_name=fetched.channel_name or execution.channel_id,
            reply_map=fetched.reply_map,
        )
        return SlackMessageTransformResult(
            requested_count=fetched.requested_count,
            documents=tuple(documents),
            document_ids=tuple(document_ids),
            channel_name=fetched.channel_name,
            error_count=fetched.fetch_error_count + errors,
            latest_synced_ts=latest_synced_ts,
        )

    async def summarize(
        self,
        *,
        execution: SlackMessageIncrementalSyncExecutionRequest,
        sync_window: SyncWindow,
        transformed: SlackMessageTransformResult,
    ) -> SlackMessageSummaryResult:
        _ = sync_window
        documents = list(transformed.documents)
        channel_name = transformed.channel_name or execution.channel_id
        if self.summarizer and documents:
            documents = await self._summarize_documents(
                documents,
                channel_name=channel_name,
                audit_context=execution.audit_context,
            )
        return SlackMessageSummaryResult(
            summary_applied=bool(self.summarizer and documents),
            documents=tuple(documents),
            document_ids=tuple(doc.id for doc in documents),
        )

    async def persist(
        self,
        *,
        execution: SlackMessageIncrementalSyncExecutionRequest,
        sync_window: SyncWindow,
        transformed: SlackMessageTransformResult,
        summary: SlackMessageSummaryResult,
    ) -> SlackMessagePersistResult:
        _ = sync_window
        if transformed.delete_document_ids:
            await self.repository.delete_documents(list(transformed.delete_document_ids))
            return SlackMessagePersistResult(
                deleted_count=len(transformed.delete_document_ids)
            )

        documents = list(summary.documents)
        if not documents:
            return SlackMessagePersistResult(
                error_count=transformed.error_count,
                skipped=transformed.error_count == 0,
            )

        await self.repository.upsert_documents(
            documents,
            list(summary.document_ids),
            audit_context=execution.audit_context,
            context=(
                "entity_type=message,"
                f"channel={transformed.channel_name or execution.channel_id},"
                "mode=incremental_exact_refresh,"
                f"doc_count={len(documents)}"
            ),
        )
        return SlackMessagePersistResult(
            persisted_count=len(documents),
            error_count=transformed.error_count,
        )

    def build_result(
        self,
        *,
        execution: SlackMessageIncrementalSyncExecutionRequest,
        sync_window: SyncWindow,
        fetched: SlackMessageFetchResult,
        transformed: SlackMessageTransformResult,
        summary: SlackMessageSummaryResult,
        persisted: SlackMessagePersistResult,
    ) -> SlackMessageSyncExecutionResult:
        _ = execution, sync_window, summary
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
            checkpoint=transformed.latest_synced_ts,
            metadata={
                "batch_index": fetched.batch_index,
                "is_last": fetched.is_last,
                "next_cursor": fetched.next_cursor,
                "checkpoint": transformed.latest_synced_ts,
            },
        )
