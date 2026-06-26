from __future__ import annotations

import structlog
from fastapi.concurrency import run_in_threadpool
from langchain_core.documents import Document

from catchup.sync.ingestion.adapters.slack.message_base import SlackMessageAdapterBase
from catchup.sync.ingestion.adapters.slack.message_models import (
    ParsedSlackMessageDocument,
)
from catchup.sync.ingestion.adapters.slack.message_models import SlackMessageFetchResult
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
from catchup.sync.ingestion.adapters.slack.message_models import (
    SlackMessageV2BackfillExecutionRequest,
)
from catchup.sync.ingestion.adapters.slack.message_models import (
    SlackMessageV2BackfillSeed,
)
from catchup.sync.ingestion.schemas import SyncWindow

logger = structlog.get_logger(__name__)


class SlackMessageV2BackfillAdapter(SlackMessageAdapterBase):
    """Backfill Slack Message v2 records by hydrating v1 seeds through Slack API."""

    async def fetch(
        self,
        *,
        execution: SlackMessageV2BackfillExecutionRequest,
        sync_window: SyncWindow,
    ) -> SlackMessageFetchResult:
        _ = sync_window
        parent_messages: list[dict] = []
        reply_map = {}
        failed_record_ids: list[str] = []

        for seed in execution.seeds:
            try:
                message_data = await self.client.get_message(
                    channel=execution.channel_id,
                    ts=seed.record_id,
                )
                if not message_data:
                    failed_record_ids.append(seed.record_id)
                    continue

                sanitized_message = self._sanitize_message_payload(message_data)
                if self._should_skip_message_subtype(sanitized_message):
                    failed_record_ids.append(seed.record_id)
                    continue

                parent_messages.append(sanitized_message)
                if sanitized_message.get("reply_count", 0) > 0:
                    reply_map[seed.record_id] = await self._fetch_thread_replies(
                        channel_id=execution.channel_id,
                        thread_ts=seed.record_id,
                    )
            except Exception as exc:
                logger.warning(
                    "slack_message_v2_backfill_hydrate_failed",
                    team_id=self.team_id,
                    channel_id=execution.channel_id,
                    message_ts=seed.record_id,
                    error=str(exc),
                    exc_info=True,
                )
                failed_record_ids.append(seed.record_id)

        return SlackMessageFetchResult(
            requested_count=len(execution.seeds),
            parent_messages=tuple(parent_messages),
            reply_map=reply_map,
            failed_record_ids=tuple(dict.fromkeys(failed_record_ids)),
            channel_name=execution.channel_name,
            fetch_error_count=len(set(failed_record_ids)),
        )

    async def transform(
        self,
        *,
        execution: SlackMessageV2BackfillExecutionRequest,
        sync_window: SyncWindow,
        fetched: SlackMessageFetchResult,
    ) -> SlackMessageTransformResult:
        _ = sync_window
        seed_by_record_id = _seed_by_record_id(execution.seeds)
        seed_langchain_id_by_record_id = {
            seed.record_id: seed.langchain_id for seed in execution.seeds
        }
        (
            parsed_documents,
            _,
            errors,
            latest_synced_ts,
            parsed_failed_record_ids,
        ) = await self._transform_message_bundles(
            messages=fetched.parent_messages,
            channel_id=execution.channel_id,
            channel_name=execution.channel_name,
            reply_map=fetched.reply_map,
        )

        v2_documents, document_ids, transform_failed_ids = await run_in_threadpool(
            self._build_seeded_v2_documents_blocking,
            tuple(parsed_documents),
            seed_by_record_id,
        )

        failed_record_ids = _dedupe(
            (
                *fetched.failed_record_ids,
                *parsed_failed_record_ids,
                *transform_failed_ids,
            )
        )
        v2_failed_ids = _dedupe(
            tuple(
                seed_langchain_id_by_record_id.get(record_id, record_id)
                for record_id in (
                    *fetched.failed_record_ids,
                    *parsed_failed_record_ids,
                    *transform_failed_ids,
                )
            )
        )

        return SlackMessageTransformResult(
            requested_count=fetched.requested_count,
            v2_documents=tuple(v2_documents),
            document_ids=tuple(document_ids),
            error_count=len(failed_record_ids) + errors,
            failed_record_ids=failed_record_ids,
            v2_failed_ids=v2_failed_ids,
            channel_name=fetched.channel_name,
            latest_synced_ts=latest_synced_ts,
        )

    async def summarize(
        self,
        *,
        execution: SlackMessageV2BackfillExecutionRequest,
        sync_window: SyncWindow,
        transformed: SlackMessageTransformResult,
    ) -> SlackMessageSummaryResult:
        _ = execution, sync_window
        return SlackMessageSummaryResult(
            summary_applied=False,
            v2_documents=transformed.v2_documents,
            document_ids=transformed.document_ids,
        )

    async def persist(
        self,
        *,
        execution: SlackMessageV2BackfillExecutionRequest,
        sync_window: SyncWindow,
        transformed: SlackMessageTransformResult,
        summary: SlackMessageSummaryResult,
    ) -> SlackMessagePersistResult:
        _ = sync_window
        seed_by_langchain_id = _seed_by_langchain_id(execution.seeds)
        document_ids = list(summary.document_ids)
        v2_documents = list(summary.v2_documents)
        upstream_v2_failed_ids = tuple(transformed.v2_failed_ids)

        if not document_ids:
            return SlackMessagePersistResult(
                error_count=len(transformed.failed_record_ids),
                v2_error_count=len(upstream_v2_failed_ids),
                v2_failed_ids=upstream_v2_failed_ids,
            )

        if self.vector_store is None:
            v2_failed_ids = _dedupe((*upstream_v2_failed_ids, *document_ids))
            return SlackMessagePersistResult(
                error_count=len(transformed.failed_record_ids) + len(document_ids),
                v2_error_count=len(v2_failed_ids),
                v2_failed_ids=v2_failed_ids,
            )

        embeddings = [seed_by_langchain_id[doc_id].embedding for doc_id in document_ids]
        try:
            persisted_ids = await self.vector_store.upsert_documents(
                v2_documents,
                ids=document_ids,
                embeddings=embeddings,
            )
        except Exception as exc:
            logger.warning(
                "slack_message_v2_backfill_upsert_failed",
                team_id=self.team_id,
                channel_id=execution.channel_id,
                document_ids=document_ids,
                error=str(exc),
                exc_info=True,
            )
            v2_failed_ids = _dedupe((*upstream_v2_failed_ids, *document_ids))
            return SlackMessagePersistResult(
                error_count=len(transformed.failed_record_ids) + len(document_ids),
                v2_error_count=len(v2_failed_ids),
                v2_failed_ids=v2_failed_ids,
            )

        persisted_id_set = {str(persisted_id) for persisted_id in persisted_ids or []}
        write_failed_ids = tuple(
            doc_id for doc_id in document_ids if doc_id not in persisted_id_set
        )
        metadata_check_ids = [
            doc_id for doc_id in document_ids if doc_id in persisted_id_set
        ]
        if self.v2_knowledge_repository is None:
            metadata_failed_ids = tuple(metadata_check_ids)
        else:
            metadata_failed_ids = (
                await self.v2_knowledge_repository.find_missing_metadata_namespace_ids(
                    metadata_check_ids,
                    namespace="slack_message",
                )
            )
        if metadata_failed_ids:
            logger.warning(
                "slack_message_v2_backfill_metadata_missing_after_persist",
                connector="slack",
                entity_type="message",
                scope_id=self.team_id,
                target_id=execution.channel_id,
                namespace="slack_message",
                missing_metadata_ids=list(metadata_failed_ids),
                persisted_id_count=len(metadata_check_ids),
                missing_count=len(metadata_failed_ids),
            )
        failed_document_ids = _dedupe((*write_failed_ids, *metadata_failed_ids))
        v2_failed_ids = _dedupe((*upstream_v2_failed_ids, *failed_document_ids))
        return SlackMessagePersistResult(
            persisted_count=len(document_ids) - len(failed_document_ids),
            error_count=len(transformed.failed_record_ids) + len(failed_document_ids),
            v2_error_count=len(v2_failed_ids),
            v2_failed_ids=v2_failed_ids,
        )

    def build_result(
        self,
        *,
        execution: SlackMessageV2BackfillExecutionRequest,
        sync_window: SyncWindow,
        fetched: SlackMessageFetchResult,
        transformed: SlackMessageTransformResult,
        summary: SlackMessageSummaryResult,
        persisted: SlackMessagePersistResult,
    ) -> SlackMessageSyncExecutionResult:
        _ = sync_window
        failed_langchain_ids = _dedupe(
            (
                *_langchain_ids_for_record_ids(
                    execution.seeds,
                    transformed.failed_record_ids,
                ),
                *persisted.v2_failed_ids,
            )
        )
        v2_failed_ids = _dedupe((*transformed.v2_failed_ids, *persisted.v2_failed_ids))
        return SlackMessageSyncExecutionResult(
            tenant_id=execution.tenant_id,
            target="message_v2_backfill",
            persisted_count=persisted.persisted_count,
            deleted_count=persisted.deleted_count,
            failed_count=len(failed_langchain_ids),
            v2_failed_count=len(v2_failed_ids),
            v2_failed_ids=v2_failed_ids,
            skipped=persisted.skipped,
            fetched=fetched,
            transformed=transformed,
            summary=summary,
            persisted=persisted,
            metadata={
                "channel_id": execution.channel_id,
                "channel_name": execution.channel_name,
                "requested_count": len(execution.seeds),
                "failed_ids": list(failed_langchain_ids),
                "failed_record_ids": list(transformed.failed_record_ids),
                "v2_failed_ids": list(v2_failed_ids),
            },
        )

    def _build_seeded_v2_documents_blocking(
        self,
        parsed_documents: tuple[ParsedSlackMessageDocument, ...],
        seed_by_record_id: dict[str, SlackMessageV2BackfillSeed],
    ) -> tuple[list[Document], list[str], tuple[str, ...]]:
        return self.message_v2_document_builder.build_from_backfill_seeds(
            parsed_documents,
            team_id=self.team_id,
            seed_by_message_ts=seed_by_record_id,
        )


def _seed_by_record_id(
    seeds: tuple[SlackMessageV2BackfillSeed, ...],
) -> dict[str, SlackMessageV2BackfillSeed]:
    return {seed.record_id: seed for seed in seeds}


def _seed_by_langchain_id(
    seeds: tuple[SlackMessageV2BackfillSeed, ...],
) -> dict[str, SlackMessageV2BackfillSeed]:
    return {seed.langchain_id: seed for seed in seeds}


def _langchain_ids_for_record_ids(
    seeds: tuple[SlackMessageV2BackfillSeed, ...],
    record_ids: tuple[str, ...],
) -> tuple[str, ...]:
    seeds_by_record_id = _seed_by_record_id(seeds)
    return tuple(
        seeds_by_record_id[record_id].langchain_id
        if record_id in seeds_by_record_id
        else record_id
        for record_id in record_ids
    )


def _dedupe(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))
