from __future__ import annotations

import asyncio

from catchup.configs.config import settings
from catchup.sync.ingestion.adapters.slack.message_base import SlackMessageAdapterBase
from catchup.sync.ingestion.adapters.slack.message_models import SlackMessageFetchResult
from catchup.sync.ingestion.adapters.slack.message_models import (
    SlackMessageFullSyncExecutionRequest,
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


class SlackMessageFullSyncAdapter(SlackMessageAdapterBase):
    """Slack channel message full-sync adapter for one parent-message page."""

    async def fetch(
        self,
        *,
        execution: SlackMessageFullSyncExecutionRequest,
        sync_window: SyncWindow,
    ) -> SlackMessageFetchResult:
        response = await self.client.get_conversation_history(
            channel=execution.channel_id,
            oldest=f"{sync_window.window_start.timestamp():.6f}",
            cursor=execution.cursor,
            limit=settings.SLACK_MESSAGE_BATCH_SIZE,
        )
        parent_messages = tuple(
            self._sanitize_message_payload(message)
            for message in response.get("messages", [])
        )
        thread_messages = [
            msg
            for msg in parent_messages
            if not self._should_skip_message(msg) and msg.get("reply_count", 0) > 0
        ]

        if thread_messages:
            thread_replies_list = await asyncio.gather(
                *[
                    self._fetch_thread_replies(
                        channel_id=execution.channel_id,
                        thread_ts=msg.get("ts"),
                    )
                    for msg in thread_messages
                ]
            )
            reply_map = {
                str(msg.get("ts")): replies
                for msg, replies in zip(thread_messages, thread_replies_list)
                if msg.get("ts")
            }
        else:
            reply_map = {}

        next_cursor = response.get("response_metadata", {}).get("next_cursor")
        has_more = bool(response.get("has_more") and next_cursor)
        return SlackMessageFetchResult(
            requested_count=1,
            parent_messages=parent_messages,
            reply_map=reply_map,
            channel_name=execution.channel_name,
            batch_index=execution.batch_index,
            is_last=not has_more,
            next_cursor=next_cursor if has_more else None,
        )

    async def transform(
        self,
        *,
        execution: SlackMessageFullSyncExecutionRequest,
        sync_window: SyncWindow,
        fetched: SlackMessageFetchResult,
    ) -> SlackMessageTransformResult:
        _ = sync_window
        documents, document_ids, errors, latest_synced_ts = await self._transform_messages(
            messages=fetched.parent_messages,
            channel_id=execution.channel_id,
            channel_name=execution.channel_name,
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
        execution: SlackMessageFullSyncExecutionRequest,
        sync_window: SyncWindow,
        transformed: SlackMessageTransformResult,
    ) -> SlackMessageSummaryResult:
        _ = sync_window
        documents = list(transformed.documents)
        if self.summarizer and documents:
            documents = await self._summarize_documents(
                documents,
                channel_name=execution.channel_name,
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
        execution: SlackMessageFullSyncExecutionRequest,
        sync_window: SyncWindow,
        transformed: SlackMessageTransformResult,
        summary: SlackMessageSummaryResult,
    ) -> SlackMessagePersistResult:
        _ = sync_window
        documents = list(summary.documents)
        document_ids = list(summary.document_ids)
        if not documents:
            return SlackMessagePersistResult(error_count=transformed.error_count)

        if not execution.skip_delete:
            await self.repository.delete_documents(document_ids)

        embeddings = await self.repository.generate_embeddings(
            documents,
            audit_context=execution.audit_context,
            context=(
                f"entity_type=message,channel={execution.channel_name},"
                f"batch={execution.batch_index},doc_count={len(documents)}"
            ),
        )
        await self.repository.store_with_embeddings(
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

    def build_result(
        self,
        *,
        execution: SlackMessageFullSyncExecutionRequest,
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
