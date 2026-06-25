from __future__ import annotations

import structlog
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

logger = structlog.get_logger(__name__)


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
        if self._should_skip_message_subtype(sanitized_message):
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

        (
            parsed_documents,
            document_ids,
            errors,
            latest_synced_ts,
            failed_record_ids,
        ) = await self._transform_message_bundles(
            messages=fetched.parent_messages,
            channel_id=execution.channel_id,
            channel_name=fetched.channel_name or execution.channel_id,
            reply_map=fetched.reply_map,
        )
        documents = [parsed.document for parsed in parsed_documents]
        v2_documents, v2_failed_ids = await self._build_v2_documents_from_bundles(
            tuple(parsed_documents),
        )
        return SlackMessageTransformResult(
            requested_count=fetched.requested_count,
            documents=tuple(documents),
            v2_documents=tuple(v2_documents),
            document_ids=tuple(document_ids),
            channel_name=fetched.channel_name,
            error_count=fetched.fetch_error_count + errors,
            failed_record_ids=tuple(
                dict.fromkeys((*fetched.failed_record_ids, *failed_record_ids))
            ),
            v2_failed_ids=v2_failed_ids,
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
        v2_documents = self._align_v2_documents_to_v1_content(
            v1_documents=documents,
            v2_documents=list(transformed.v2_documents),
            operation="slack_message_incremental_dual_write",
        )
        return SlackMessageSummaryResult(
            summary_applied=bool(self.summarizer and documents),
            documents=tuple(documents),
            v2_documents=tuple(v2_documents),
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
            v2_failed_ids: tuple[str, ...] = ()
            if self.vector_store is not None:
                try:
                    await self.vector_store.delete(list(transformed.delete_document_ids))
                except Exception as exc:
                    logger.warning(
                        "slack_message_v2_delete_failed",
                        team_id=self.team_id,
                        channel_id=execution.channel_id,
                        document_ids=transformed.delete_document_ids,
                        error=str(exc),
                        exc_info=True,
                    )
                    v2_failed_ids = transformed.delete_document_ids
            return SlackMessagePersistResult(
                deleted_count=len(transformed.delete_document_ids),
                v2_error_count=len(v2_failed_ids),
                v2_failed_ids=v2_failed_ids,
            )

        documents = list(summary.documents)
        if not documents:
            return SlackMessagePersistResult(
                error_count=transformed.error_count,
                v2_error_count=len(transformed.v2_failed_ids),
                v2_failed_ids=transformed.v2_failed_ids,
                skipped=transformed.error_count == 0,
            )

        context = (
            "entity_type=message,"
            f"channel={transformed.channel_name or execution.channel_id},"
            "mode=incremental_exact_refresh,"
            f"doc_count={len(documents)}"
        )
        if self.vector_store is not None:
            result = await self._upsert_v1_v2_documents_dual_write(
                v1_documents=documents,
                v2_documents=list(summary.v2_documents),
                ids=list(summary.document_ids),
                audit_context=execution.audit_context,
                context=context,
            )
            v2_failed_ids = tuple(
                dict.fromkeys(
                    (*transformed.v2_failed_ids, *result.vector_failed_ids)
                )
            )
            return SlackMessagePersistResult(
                persisted_count=len(result.persisted_ids),
                error_count=transformed.error_count,
                v2_error_count=len(v2_failed_ids),
                v2_failed_ids=v2_failed_ids,
            )

        await self.repository.upsert_documents(
            documents,
            list(summary.document_ids),
            audit_context=execution.audit_context,
            context=context,
        )
        return SlackMessagePersistResult(
            persisted_count=len(documents),
            error_count=transformed.error_count,
            v2_error_count=len(transformed.v2_failed_ids),
            v2_failed_ids=transformed.v2_failed_ids,
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
            failed_count=persisted.error_count + persisted.v2_error_count,
            v2_failed_count=persisted.v2_error_count,
            v2_failed_ids=persisted.v2_failed_ids,
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
                "v2_failed_ids": list(persisted.v2_failed_ids),
            },
        )
