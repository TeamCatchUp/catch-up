from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime
from datetime import timezone
from decimal import Decimal

import structlog
from sqlalchemy import text
from sqlalchemy.orm import Session

from catchup.components.vector_db.v2.constants import KNOWLEDGE_STORE_CONTENT_COLUMN
from catchup.components.vector_db.v2.constants import KNOWLEDGE_STORE_EMBEDDING_COLUMN
from catchup.components.vector_db.v2.constants import KNOWLEDGE_STORE_ID_COLUMN
from catchup.components.vector_db.v2.constants import (
    KNOWLEDGE_STORE_METADATA_JSON_COLUMN,
)
from catchup.components.vector_db.v2.constants import KNOWLEDGE_STORE_TABLE_NAME
from catchup.configs.config import settings
from catchup.db.engine import SessionLocal
from catchup.sync.backfill.concurrency import run_bounded_targets
from catchup.sync.backfill.state import BackfillCompletionDecision
from catchup.sync.backfill.state import backfill_candidate_state_predicate
from catchup.sync.backfill.state import build_failure_metadata
from catchup.sync.backfill.state import build_mark_finished_statement
from catchup.sync.backfill.state import build_mark_processing_statement
from catchup.sync.backfill.state import count_backfill_completion_failures
from catchup.sync.backfill.state import decide_backfill_completion
from catchup.sync.ingestion.adapters.slack import SlackMessageV2BackfillAdapter
from catchup.sync.ingestion.adapters.slack import SlackMessageV2BackfillExecutionRequest
from catchup.sync.ingestion.adapters.slack import SlackMessageV2BackfillSeed
from catchup.sync.ingestion.factories.slack import (
    create_slack_message_v2_backfill_adapter,
)
from catchup.sync.ingestion.pipeline import run_sync_ingestion
from catchup.sync.ingestion.schemas import SyncExecutionResult
from catchup.sync.ingestion.schemas import SyncWindow

SessionFactory = Callable[[], AbstractContextManager[Session]]
BackfillAdapterFactory = Callable[[str], Awaitable[SlackMessageV2BackfillAdapter]]
SEED_INSERT_BATCH_SIZE = 100
HYDRATE_PIPELINE_BATCH_SIZE = 50

logger = structlog.get_logger(__name__)


@dataclass(slots=True, frozen=True)
class SlackMessageV1Seed:
    langchain_id: str
    record_id: str
    content: str
    embedding: list[float]


@dataclass(slots=True, frozen=True)
class SlackMessageV1Target:
    scope_id: str
    target_id: str
    target_name: str
    expected_count: int
    pending_count: int


@dataclass(slots=True, frozen=True)
class SlackMessageV2BackfillResult:
    scanned: int
    succeeded: int
    skipped: int
    failed: int


@dataclass(slots=True, frozen=True)
class SlackMessageV2Cursor:
    record_ts: Decimal
    langchain_id: str


class SlackMessageV2BackfillService:
    def __init__(
        self,
        *,
        adapter_factory: BackfillAdapterFactory = create_slack_message_v2_backfill_adapter,
        session_factory: SessionFactory = SessionLocal,
        collection_name: str = settings.PGVECTOR_COLLECTION_NAME,
    ) -> None:
        self._adapter_factory = adapter_factory
        self._session_factory = session_factory
        self._collection_name = collection_name

    async def backfill_batch(
        self,
        *,
        limit: int,
        locked_by: str | None = None,
    ) -> SlackMessageV2BackfillResult:
        del locked_by
        targets = await asyncio.to_thread(self._fetch_candidate_targets_sync, limit)
        logger.info(
            "slack_message_v2_backfill_candidate_targets_fetched",
            connector="slack",
            entity_type="message",
            limit=limit,
            target_count=len(targets),
        )
        succeeded = 0
        skipped = 0
        failed = 0

        async def _process_target(target) -> None:
            nonlocal succeeded, skipped, failed
            adapters: dict[str, SlackMessageV2BackfillAdapter] = {}
            processing_started_at: datetime | None = None
            try:
                processing_started_at = await asyncio.to_thread(
                    self._mark_processing_sync,
                    target,
                )
                if processing_started_at is None:
                    skipped += 1
                    return

                adapter = await self._get_adapter_for_scope(target.scope_id, adapters)
                failed_langchain_ids: list[str] = []
                backfill_count = 0
                cursor: SlackMessageV2Cursor | None = None

                while True:
                    seed_page = await asyncio.to_thread(
                        self._fetch_candidate_seed_page_for_target_sync,
                        target,
                        cursor,
                        settings.VECTOR_STORE_V2_BACKFILL_SEED_PAGE_SIZE,
                    )
                    if not seed_page:
                        break

                    await asyncio.to_thread(
                        self._upsert_seed_rows_sync,
                        target,
                        seed_page,
                    )
                    cursor = await asyncio.to_thread(
                        self._cursor_for_last_seed_sync,
                        seed_page[-1],
                    )

                    for seed_chunk in _chunked(seed_page, HYDRATE_PIPELINE_BATCH_SIZE):
                        result = await run_sync_ingestion(
                            port=adapter,
                            execution=_build_execution_request(target, seed_chunk),
                            sync_window=_build_sync_window(),
                        )
                        chunk_failed_langchain_ids = _failed_langchain_ids_from_result(
                            result,
                            seed_chunk,
                        )
                        failed_langchain_ids.extend(chunk_failed_langchain_ids)
                        backfill_count += result.persisted_count

                decision = await asyncio.to_thread(
                    self._mark_finished_sync,
                    target,
                    backfill_count,
                    failed_langchain_ids,
                    processing_started_at,
                )
                succeeded += backfill_count
                failed += count_backfill_completion_failures(
                    pending_count=target.pending_count,
                    backfill_count=backfill_count,
                    failed_ids=failed_langchain_ids,
                    state=decision.state,
                )
            except Exception as exc:
                failed += target.pending_count
                try:
                    await asyncio.to_thread(
                        self._mark_finished_sync,
                        target,
                        0,
                        [],
                        processing_started_at,
                        force_failed=True,
                        error_type=type(exc).__name__,
                        error_message=str(exc),
                    )
                except Exception as state_exc:
                    logger.warning(
                        "slack_message_v2_backfill_target_state_update_failed",
                        **_target_log_context(target),
                        original_error_type=type(exc).__name__,
                        original_error_message=str(exc),
                        state_error_type=type(state_exc).__name__,
                        state_error_message=str(state_exc),
                        exc_info=(type(state_exc), state_exc, state_exc.__traceback__),
                    )
                logger.warning(
                    "slack_message_v2_backfill_target_finished",
                    **_target_log_context(target),
                    state="failed",
                    backfill_count=0,
                    failed_count=target.pending_count,
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                    exc_info=(type(exc), exc, exc.__traceback__),
                )

        await run_bounded_targets(
            targets,
            concurrency=settings.VECTOR_STORE_V2_BACKFILL_TARGET_CONCURRENCY,
            process_target=_process_target,
        )
        return SlackMessageV2BackfillResult(
            scanned=len(targets),
            succeeded=succeeded,
            skipped=skipped,
            failed=failed,
        )

    async def _get_adapter_for_scope(
        self,
        scope_id: str,
        adapters: dict[str, SlackMessageV2BackfillAdapter],
    ) -> SlackMessageV2BackfillAdapter:
        if scope_id not in adapters:
            adapters[scope_id] = await self._adapter_factory(scope_id)
        return adapters[scope_id]

    def _fetch_candidate_targets_sync(self, limit: int) -> list[SlackMessageV1Target]:
        query = build_slack_message_v1_target_query()
        with self._session_factory() as db:
            rows = db.execute(
                query,
                {
                    "collection_name": self._collection_name,
                    "limit": limit,
                },
            ).mappings()
            return [
                SlackMessageV1Target(
                    scope_id=str(row["scope_id"]),
                    target_id=str(row["target_id"]),
                    target_name=str(row["target_name"]),
                    expected_count=int(row["expected_count"]),
                    pending_count=int(row["pending_count"]),
                )
                for row in rows
            ]

    def _fetch_candidate_seed_page_for_target_sync(
        self,
        target: SlackMessageV1Target,
        cursor: SlackMessageV2Cursor | None,
        limit: int,
    ) -> list[SlackMessageV1Seed]:
        query = build_slack_message_v1_target_seed_query()
        with self._session_factory() as db:
            rows = db.execute(
                query,
                {
                    "collection_name": self._collection_name,
                    "scope_id": target.scope_id,
                    "target_id": target.target_id,
                    "after_record_ts": cursor.record_ts if cursor else None,
                    "after_langchain_id": cursor.langchain_id if cursor else None,
                    "limit": limit,
                },
            ).mappings()
            return [
                SlackMessageV1Seed(
                    langchain_id=row["langchain_id"],
                    record_id=row["record_id"],
                    content=row["content"],
                    embedding=_embedding_to_list(row["embedding"]),
                )
                for row in rows
            ]

    def _upsert_seed_rows_sync(
        self,
        target: SlackMessageV1Target,
        seeds: list[SlackMessageV1Seed],
    ) -> int:
        if not seeds:
            return 0

        statement = build_upsert_seed_rows_statement()
        seeded_at = datetime.now(timezone.utc)
        affected = 0
        with self._session_factory() as db:
            for batch in _chunked(seeds, SEED_INSERT_BATCH_SIZE):
                db.execute(
                    statement,
                    [
                        {
                            "langchain_id": seed.langchain_id,
                            "content": seed.content,
                            "embedding": _format_pgvector_embedding(seed.embedding),
                            "record_id": seed.record_id,
                            "scope_id": target.scope_id,
                            "target_id": target.target_id,
                            "target_name": target.target_name,
                            "seeded_at": seeded_at,
                        }
                        for seed in batch
                    ],
                )
                affected += len(batch)
            db.commit()
        return affected

    def _fetch_pending_seed_chunk_for_target_sync(
        self,
        target: SlackMessageV1Target,
        cursor: SlackMessageV2Cursor | None,
        limit: int,
    ) -> list[SlackMessageV1Seed]:
        query = build_fetch_pending_seed_chunk_query()
        with self._session_factory() as db:
            rows = db.execute(
                query,
                {
                    "scope_id": target.scope_id,
                    "target_id": target.target_id,
                    "after_record_ts": cursor.record_ts if cursor else None,
                    "after_langchain_id": cursor.langchain_id if cursor else None,
                    "limit": limit,
                },
            ).mappings()
            return [
                SlackMessageV1Seed(
                    langchain_id=row["langchain_id"],
                    record_id=row["record_id"],
                    content=row["content"],
                    embedding=_embedding_to_list(row["embedding"]),
                )
                for row in rows
            ]

    def _cursor_for_last_seed_sync(
        self,
        seed: SlackMessageV1Seed,
    ) -> SlackMessageV2Cursor:
        return SlackMessageV2Cursor(
            record_ts=Decimal(seed.record_id),
            langchain_id=seed.langchain_id,
        )

    def _mark_processing_sync(self, target: SlackMessageV1Target) -> datetime | None:
        with self._session_factory() as db:
            result = db.execute(
                build_mark_processing_statement(),
                {
                    "connector": "slack",
                    "entity_type": "message",
                    "scope_id": target.scope_id,
                    "target_id": target.target_id,
                    "expected_count": target.expected_count,
                },
            )
            row = result.first()
            db.commit()
            if row is None:
                return None
            return row[0]

    def _mark_finished_sync(
        self,
        target: SlackMessageV1Target,
        backfill_count: int,
        failed_langchain_ids: list[str],
        processing_started_at: datetime | None = None,
        *,
        force_failed: bool = False,
        error_type: str | None = None,
        error_message: str | None = None,
    ) -> BackfillCompletionDecision:
        now = datetime.now(timezone.utc)
        decision = decide_backfill_completion(
            pending_count=target.pending_count,
            backfill_count=backfill_count,
            failed_ids=failed_langchain_ids,
            force_failed=force_failed,
            error_type=error_type,
            error_message=error_message,
        )
        state = decision.state
        failure_metadata = build_failure_metadata(
            now,
            error_type=decision.error_type if state == "failed" else None,
            error_message=decision.error_message if state == "failed" else None,
        )
        with self._session_factory() as db:
            update_result = db.execute(
                build_mark_finished_statement(),
                {
                    "connector": "slack",
                    "entity_type": "message",
                    "scope_id": target.scope_id,
                    "target_id": target.target_id,
                    "state": state,
                    "expected_count": target.expected_count,
                    "backfill_count": backfill_count,
                    "failed_ids": json.dumps(failed_langchain_ids),
                    "succeeded_at": now if state == "succeeded" else None,
                    "failed_at": now if state == "failed" else None,
                    "last_error_type": failure_metadata.last_error_type
                    if state == "failed"
                    else None,
                    "last_error_message": failure_metadata.last_error_message
                    if state == "failed"
                    else None,
                    "next_retry_at": failure_metadata.next_retry_at
                    if state == "failed"
                    else None,
                    "processing_started_at": processing_started_at,
                },
            )
            rowcount = update_result.rowcount
            db.commit()
        if rowcount == 0:
            logger.warning(
                "slack_message_v2_backfill_target_finish_update_missed",
                **_target_log_context(target),
                state=state,
                backfill_count=backfill_count,
                failed_count=len(failed_langchain_ids),
                processing_started_at=processing_started_at,
            )
        return decision


def _build_execution_request(
    target: SlackMessageV1Target,
    seeds: list[SlackMessageV1Seed],
) -> SlackMessageV2BackfillExecutionRequest:
    return SlackMessageV2BackfillExecutionRequest(
        tenant_id=target.scope_id,
        channel_id=target.target_id,
        channel_name=target.target_name,
        seeds=tuple(
            SlackMessageV2BackfillSeed(
                langchain_id=seed.langchain_id,
                record_id=seed.record_id,
                content=seed.content,
                embedding=seed.embedding,
            )
            for seed in seeds
        ),
    )


def _target_log_context(target: SlackMessageV1Target) -> dict[str, object]:
    return {
        "connector": "slack",
        "entity_type": "message",
        "scope_id": target.scope_id,
        "target_id": target.target_id,
        "target_name": target.target_name,
        "expected_count": target.expected_count,
        "pending_count": target.pending_count,
    }


def _failed_langchain_ids_from_result(
    result: SyncExecutionResult,
    seeds: list[SlackMessageV1Seed],
) -> list[str]:
    failed_langchain_ids = result.metadata.get("failed_ids")
    if isinstance(failed_langchain_ids, list):
        return [str(failed_id) for failed_id in failed_langchain_ids]
    if result.failed_count <= 0:
        return []
    seed_ids = [seed.langchain_id for seed in seeds]
    return seed_ids[: result.failed_count]


def _build_sync_window() -> SyncWindow:
    now = datetime.now(timezone.utc)
    return SyncWindow(window_start=now, window_end=now)


def _chunked(
    values: list[SlackMessageV1Seed],
    size: int,
) -> list[list[SlackMessageV1Seed]]:
    return [values[index : index + size] for index in range(0, len(values), size)]


def _format_pgvector_embedding(embedding: list[float]) -> str:
    return f"[{','.join(format(float(value), '.12g') for value in embedding)}]"


def _embedding_to_list(value) -> list[float]:
    if value is None:
        return []
    if isinstance(value, str):
        raw = value.strip().removeprefix("[").removesuffix("]")
        if not raw:
            return []
        return [float(item.strip()) for item in raw.split(",")]
    return list(value)


def _slack_message_v1_cte() -> str:
    return f"""
        WITH v1_message AS (
            SELECT
                e.id AS langchain_id,
                e.document AS content,
                e.embedding AS embedding,
                COALESCE(
                    NULLIF(e.cmetadata ->> 'ts', ''),
                    substring(e.id from ':([^:]+)$')
                ) AS record_id,
                COALESCE(
                    NULLIF(e.cmetadata ->> 'team_id', ''),
                    substring(e.id from '^slack:message:([^:]+):')
                ) AS scope_id,
                COALESCE(
                    NULLIF(e.cmetadata ->> 'channel_id', ''),
                    substring(e.id from '^slack:message:[^:]+:([^:]+):')
                ) AS target_id,
                GREATEST(
                    COALESCE(NULLIF(e.cmetadata ->> 'created_at', '')::timestamptz, '-infinity'::timestamptz),
                    COALESCE(
                        to_timestamp(
                            CASE
                                WHEN e.cmetadata ->> 'edited_at' ~ '^[0-9]+(\\.[0-9]+)?$'
                                THEN (e.cmetadata ->> 'edited_at')::double precision
                            END
                        ),
                        '-infinity'::timestamptz
                    ),
                    COALESCE(
                        to_timestamp(
                            CASE
                                WHEN e.cmetadata ->> 'latest_reply_ts' ~ '^[0-9]+(\\.[0-9]+)?$'
                                THEN (e.cmetadata ->> 'latest_reply_ts')::double precision
                            END
                        ),
                        '-infinity'::timestamptz
                    )
                ) AS source_updated_at
            FROM langchain_pg_embedding e
            JOIN langchain_pg_collection c
              ON e.collection_id = c.uuid
            WHERE c.name = :collection_name
              AND e.cmetadata ->> 'source' = 'slack'
              AND e.cmetadata ->> 'entity_type' = 'message'
        )
    """


def _slack_message_needs_backfill_expr() -> str:
    return f"""
                    (
                        COALESCE(v2.{KNOWLEDGE_STORE_METADATA_JSON_COLUMN}::jsonb, '{{}}'::jsonb) = '{{}}'::jsonb
                        OR v2.{KNOWLEDGE_STORE_ID_COLUMN} IS NULL
                        OR (
                            v1_message.source_updated_at IS NOT NULL
                            AND v1_message.source_updated_at != '-infinity'::timestamptz
                            AND (
                                v2.updated_at < v1_message.source_updated_at
                                OR (
                                    v2.updated_at = v1_message.source_updated_at
                                    AND v2.content IS DISTINCT FROM v1_message.content
                                )
                            )
                        )
                    )
    """


def build_slack_message_v1_target_query():
    return text(
        f"""
        {_slack_message_v1_cte()},
        candidates AS (
            SELECT
                v1_message.scope_id,
                v1_message.target_id,
                COALESCE(sc.name, v1_message.target_id) AS target_name,
                {_slack_message_needs_backfill_expr()} AS needs_backfill
            FROM v1_message
            LEFT JOIN {KNOWLEDGE_STORE_TABLE_NAME} v2
              ON v2.{KNOWLEDGE_STORE_ID_COLUMN} = v1_message.langchain_id
            LEFT JOIN slack_channels sc
              ON sc.id = v1_message.target_id
             AND sc.team_id = v1_message.scope_id
        ),
        grouped AS (
            SELECT
                scope_id,
                target_id,
                target_name,
                count(*) AS expected_count,
                count(*) FILTER (WHERE needs_backfill) AS pending_count
            FROM candidates
            GROUP BY scope_id, target_id, target_name
        )
        SELECT
            grouped.scope_id,
            grouped.target_id,
            grouped.target_name,
            grouped.expected_count,
            grouped.pending_count
        FROM grouped
        LEFT JOIN vector_store_v2_backfill_states state
          ON state.connector = 'slack'
         AND state.entity_type = 'message'
         AND state.scope_id = grouped.scope_id
         AND state.target_id = grouped.target_id
        WHERE grouped.pending_count > 0
        {backfill_candidate_state_predicate("state")}
        ORDER BY grouped.scope_id, grouped.target_id
        LIMIT :limit
        """
    )


def build_slack_message_v1_target_seed_query():
    return text(
        f"""
        {_slack_message_v1_cte()},
        candidates AS (
            SELECT
                v1_message.langchain_id,
                v1_message.record_id,
                v1_message.content,
                v1_message.embedding,
                v1_message.scope_id,
                v1_message.target_id,
                {_slack_message_needs_backfill_expr()} AS needs_backfill
            FROM v1_message
            LEFT JOIN {KNOWLEDGE_STORE_TABLE_NAME} v2
              ON v2.{KNOWLEDGE_STORE_ID_COLUMN} = v1_message.langchain_id
        ),
        typed_candidates AS (
            SELECT
                langchain_id,
                record_id,
                content,
                embedding,
                record_id::numeric(20,6) AS record_ts
            FROM candidates
            WHERE scope_id = :scope_id
              AND target_id = :target_id
              AND needs_backfill
              AND record_id ~ '^[0-9]+\\.[0-9]+$'
        )
        SELECT langchain_id, record_id, content, embedding
        FROM typed_candidates
        WHERE (
              CAST(:after_record_ts AS numeric(20,6)) IS NULL
              OR record_ts > CAST(:after_record_ts AS numeric(20,6))
              OR (
                  record_ts = CAST(:after_record_ts AS numeric(20,6))
                  AND langchain_id > COALESCE(:after_langchain_id, '')
              )
          )
        ORDER BY record_ts, langchain_id
        LIMIT :limit
        """
    )


def build_upsert_seed_rows_statement():
    return text(
        f"""
        INSERT INTO {KNOWLEDGE_STORE_TABLE_NAME} (
            {KNOWLEDGE_STORE_ID_COLUMN},
            {KNOWLEDGE_STORE_CONTENT_COLUMN},
            {KNOWLEDGE_STORE_EMBEDDING_COLUMN},
            {KNOWLEDGE_STORE_METADATA_JSON_COLUMN},
            source,
            entity_type,
            record_id,
            scope_type,
            scope_id,
            target_type,
            target_id,
            target_name,
            internal_author_id,
            title,
            body,
            data,
            url,
            created_at,
            updated_at,
            synced_at
        )
        VALUES (
            :langchain_id,
            :content,
            CAST(:embedding AS vector),
            '{{}}'::json,
            'slack',
            'message',
            :record_id,
            'workspace',
            :scope_id,
            'channel',
            :target_id,
            :target_name,
            NULL,
            '',
            '',
            '{{}}'::jsonb,
            '',
            :seeded_at,
            :seeded_at,
            :seeded_at
        )
        ON CONFLICT ({KNOWLEDGE_STORE_ID_COLUMN}) DO UPDATE SET
            {KNOWLEDGE_STORE_CONTENT_COLUMN} = EXCLUDED.{KNOWLEDGE_STORE_CONTENT_COLUMN},
            {KNOWLEDGE_STORE_EMBEDDING_COLUMN} = EXCLUDED.{KNOWLEDGE_STORE_EMBEDDING_COLUMN},
            source = EXCLUDED.source,
            entity_type = EXCLUDED.entity_type,
            record_id = EXCLUDED.record_id,
            scope_type = EXCLUDED.scope_type,
            scope_id = EXCLUDED.scope_id,
            target_type = EXCLUDED.target_type,
            target_id = EXCLUDED.target_id,
            target_name = EXCLUDED.target_name
        """
    )


def build_fetch_pending_seed_chunk_query():
    return text(
        f"""
        WITH seeded_message AS (
            SELECT
                {KNOWLEDGE_STORE_ID_COLUMN} AS langchain_id,
                COALESCE(
                    NULLIF(record_id, ''),
                    substring({KNOWLEDGE_STORE_ID_COLUMN} from ':([^:]+)$')
                ) AS record_id,
                {KNOWLEDGE_STORE_CONTENT_COLUMN} AS content,
                {KNOWLEDGE_STORE_EMBEDDING_COLUMN} AS embedding
            FROM {KNOWLEDGE_STORE_TABLE_NAME}
            WHERE source = 'slack'
              AND entity_type = 'message'
              AND scope_id = :scope_id
              AND target_id = :target_id
              AND COALESCE({KNOWLEDGE_STORE_METADATA_JSON_COLUMN}::jsonb, '{{}}'::jsonb) = '{{}}'::jsonb
        ),
        typed_seeded_message AS (
            SELECT
                langchain_id,
                record_id,
                content,
                embedding,
                record_id::numeric(20,6) AS record_ts
            FROM seeded_message
            WHERE record_id ~ '^[0-9]+\\.[0-9]+$'
        )
        SELECT langchain_id, record_id, content, embedding
        FROM typed_seeded_message
        WHERE (
              CAST(:after_record_ts AS numeric(20,6)) IS NULL
              OR record_ts > CAST(:after_record_ts AS numeric(20,6))
              OR (
                  record_ts = CAST(:after_record_ts AS numeric(20,6))
                  AND langchain_id > COALESCE(:after_langchain_id, '')
              )
          )
        ORDER BY record_ts, langchain_id
        LIMIT :limit
        """
    )
