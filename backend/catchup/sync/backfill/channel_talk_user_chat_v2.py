from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime
from datetime import timezone

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
from catchup.sync.backfill.state import backfill_candidate_state_predicate
from catchup.sync.backfill.state import backfill_claimable_state_predicate
from catchup.sync.backfill.state import build_failure_metadata
from catchup.sync.ingestion.adapters.channel_talk.user_chat_models import (
    ChannelTalkUserChatV2BackfillExecutionRequest,
)
from catchup.sync.ingestion.adapters.channel_talk.user_chat_models import (
    ChannelTalkUserChatV2BackfillSeed,
)
from catchup.sync.ingestion.adapters.channel_talk.user_chat_v2_backfill import (
    ChannelTalkUserChatV2BackfillAdapter,
)
from catchup.sync.ingestion.factories.channel_talk import (
    create_channel_talk_user_chat_v2_backfill_adapter,
)
from catchup.sync.ingestion.pipeline import run_sync_ingestion
from catchup.sync.ingestion.schemas import SyncExecutionResult
from catchup.sync.ingestion.schemas import SyncWindow

SessionFactory = Callable[[], AbstractContextManager[Session]]
BackfillAdapterFactory = Callable[[str], Awaitable[ChannelTalkUserChatV2BackfillAdapter]]
SEED_INSERT_BATCH_SIZE = 100
HYDRATE_PIPELINE_BATCH_SIZE = 50

logger = structlog.get_logger(__name__)


@dataclass(slots=True, frozen=True)
class ChannelTalkUserChatV1Seed:
    langchain_id: str
    record_id: str
    content: str
    embedding: list[float]


@dataclass(slots=True, frozen=True)
class ChannelTalkUserChatV1Target:
    scope_id: str
    target_id: str
    target_name: str
    expected_count: int


@dataclass(slots=True, frozen=True)
class ChannelTalkUserChatV2BackfillResult:
    scanned: int
    succeeded: int
    skipped: int
    failed: int


@dataclass(slots=True, frozen=True)
class ChannelTalkUserChatV2Cursor:
    record_id: str
    langchain_id: str


class ChannelTalkUserChatV2BackfillService:
    def __init__(
        self,
        *,
        adapter_factory: BackfillAdapterFactory = (
            create_channel_talk_user_chat_v2_backfill_adapter
        ),
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
    ) -> ChannelTalkUserChatV2BackfillResult:
        del locked_by
        targets = await asyncio.to_thread(self._fetch_candidate_targets_sync, limit)
        logger.info(
            "channel_talk_user_chat_v2_backfill_candidate_targets_fetched",
            connector="channel_talk",
            entity_type="user_chat",
            limit=limit,
            target_count=len(targets),
        )
        succeeded = 0
        skipped = 0
        failed = 0

        async def _process_target(target) -> None:
            nonlocal succeeded, skipped, failed
            adapters: dict[str, ChannelTalkUserChatV2BackfillAdapter] = {}
            processing_started_at: datetime | None = None
            try:
                processing_started_at = await asyncio.to_thread(
                    self._mark_processing_sync,
                    target,
                )
                if processing_started_at is None:
                    skipped += 1
                    return

                seeds = await asyncio.to_thread(
                    self._fetch_candidate_seeds_for_target_sync,
                    target,
                )
                await asyncio.to_thread(self._upsert_seed_rows_sync, target, seeds)
                adapter = await self._get_adapter_for_scope(target.scope_id, adapters)
                failed_langchain_ids: list[str] = []
                backfill_count = 0
                cursor: ChannelTalkUserChatV2Cursor | None = None

                while True:
                    seed_chunk = await asyncio.to_thread(
                        self._fetch_pending_seed_chunk_for_target_sync,
                        target,
                        cursor,
                        HYDRATE_PIPELINE_BATCH_SIZE,
                    )
                    if not seed_chunk:
                        break

                    cursor = ChannelTalkUserChatV2Cursor(
                        record_id=seed_chunk[-1].record_id,
                        langchain_id=seed_chunk[-1].langchain_id,
                    )
                    result = await run_sync_ingestion(
                        port=adapter,
                        execution=_build_execution_request(target, seed_chunk),
                        sync_window=_build_sync_window(),
                    )
                    chunk_failed_ids = _failed_langchain_ids_from_result(
                        result,
                        seed_chunk,
                    )
                    failed_langchain_ids.extend(chunk_failed_ids)
                    backfill_count += result.persisted_count

                await asyncio.to_thread(
                    self._mark_finished_sync,
                    target,
                    backfill_count,
                    failed_langchain_ids,
                    processing_started_at,
                )
                succeeded += backfill_count
                failed += len(failed_langchain_ids)
            except Exception as exc:
                failed += target.expected_count
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
                        "channel_talk_user_chat_v2_backfill_target_state_update_failed",
                        **_target_log_context(target),
                        original_error_type=type(exc).__name__,
                        original_error_message=str(exc),
                        state_error_type=type(state_exc).__name__,
                        state_error_message=str(state_exc),
                        exc_info=(type(state_exc), state_exc, state_exc.__traceback__),
                    )
                logger.warning(
                    "channel_talk_user_chat_v2_backfill_target_finished",
                    **_target_log_context(target),
                    state="failed",
                    backfill_count=0,
                    failed_count=target.expected_count,
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                    exc_info=(type(exc), exc, exc.__traceback__),
                )


        await run_bounded_targets(
            targets,
            concurrency=settings.VECTOR_STORE_V2_BACKFILL_TARGET_CONCURRENCY,
            process_target=_process_target,
        )
        return ChannelTalkUserChatV2BackfillResult(
            scanned=len(targets),
            succeeded=succeeded,
            skipped=skipped,
            failed=failed,
        )

    async def _get_adapter_for_scope(
        self,
        scope_id: str,
        adapters: dict[str, ChannelTalkUserChatV2BackfillAdapter],
    ) -> ChannelTalkUserChatV2BackfillAdapter:
        if scope_id not in adapters:
            adapters[scope_id] = await self._adapter_factory(scope_id)
        return adapters[scope_id]

    def _fetch_candidate_targets_sync(
        self,
        limit: int,
    ) -> list[ChannelTalkUserChatV1Target]:
        query = build_channel_talk_user_chat_v1_target_query()
        with self._session_factory() as db:
            rows = db.execute(
                query,
                {"collection_name": self._collection_name, "limit": limit},
            ).mappings()
            return [
                ChannelTalkUserChatV1Target(
                    scope_id=str(row["scope_id"]),
                    target_id=str(row["target_id"]),
                    target_name=str(row["target_name"]),
                    expected_count=int(row["expected_count"]),
                )
                for row in rows
            ]

    def _fetch_candidate_seeds_for_target_sync(
        self,
        target: ChannelTalkUserChatV1Target,
    ) -> list[ChannelTalkUserChatV1Seed]:
        query = build_channel_talk_user_chat_v1_target_seed_query()
        with self._session_factory() as db:
            rows = db.execute(
                query,
                {
                    "collection_name": self._collection_name,
                    "scope_id": target.scope_id,
                    "target_id": target.target_id,
                },
            ).mappings()
            return [
                ChannelTalkUserChatV1Seed(
                    langchain_id=row["langchain_id"],
                    record_id=row["record_id"],
                    content=row["content"],
                    embedding=_embedding_to_list(row["embedding"]),
                )
                for row in rows
            ]

    def _upsert_seed_rows_sync(
        self,
        target: ChannelTalkUserChatV1Target,
        seeds: list[ChannelTalkUserChatV1Seed],
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
        target: ChannelTalkUserChatV1Target,
        cursor: ChannelTalkUserChatV2Cursor | None,
        limit: int,
    ) -> list[ChannelTalkUserChatV1Seed]:
        query = build_fetch_seeded_seed_chunk_query()
        with self._session_factory() as db:
            rows = db.execute(
                query,
                {
                    "scope_id": target.scope_id,
                    "target_id": target.target_id,
                    "after_record_id": cursor.record_id if cursor else None,
                    "after_langchain_id": cursor.langchain_id if cursor else None,
                    "limit": limit,
                },
            ).mappings()
            return [
                ChannelTalkUserChatV1Seed(
                    langchain_id=row["langchain_id"],
                    record_id=row["record_id"],
                    content=row["content"],
                    embedding=_embedding_to_list(row["embedding"]),
                )
                for row in rows
            ]

    def _mark_processing_sync(
        self,
        target: ChannelTalkUserChatV1Target,
    ) -> datetime | None:
        with self._session_factory() as db:
            result = db.execute(
                build_mark_processing_statement(),
                {
                    "connector": "channel_talk",
                    "entity_type": "user_chat",
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
        target: ChannelTalkUserChatV1Target,
        backfill_count: int,
        failed_langchain_ids: list[str],
        processing_started_at: datetime | None = None,
        *,
        force_failed: bool = False,
        error_type: str | None = None,
        error_message: str | None = None,
    ) -> None:
        now = datetime.now(timezone.utc)
        state = "failed" if force_failed or failed_langchain_ids else "succeeded"
        failure_metadata = build_failure_metadata(
            now,
            error_type=error_type or ("PartialBackfillFailure" if failed_langchain_ids else None),
            error_message=error_message
            or (f"{len(failed_langchain_ids)} v2 documents failed during hydration" if failed_langchain_ids else None),
        )
        with self._session_factory() as db:
            db.execute(
                build_mark_finished_statement(),
                {
                    "connector": "channel_talk",
                    "entity_type": "user_chat",
                    "scope_id": target.scope_id,
                    "target_id": target.target_id,
                    "state": state,
                    "expected_count": target.expected_count,
                    "backfill_count": backfill_count,
                    "failed_ids": json.dumps(failed_langchain_ids),
                    "succeeded_at": now if state == "succeeded" else None,
                    "failed_at": now if state == "failed" else None,
                    "last_error_type": failure_metadata.last_error_type if state == "failed" else None,
                    "last_error_message": failure_metadata.last_error_message if state == "failed" else None,
                    "next_retry_at": failure_metadata.next_retry_at if state == "failed" else None,
                    "processing_started_at": processing_started_at,
                },
            )
            db.commit()


def _build_execution_request(
    target: ChannelTalkUserChatV1Target,
    seeds: list[ChannelTalkUserChatV1Seed],
) -> ChannelTalkUserChatV2BackfillExecutionRequest:
    return ChannelTalkUserChatV2BackfillExecutionRequest(
        tenant_id=target.scope_id,
        seeds=tuple(
            ChannelTalkUserChatV2BackfillSeed(
                langchain_id=seed.langchain_id,
                record_id=seed.record_id,
                content=seed.content,
                embedding=seed.embedding,
            )
            for seed in seeds
        ),
    )


def _target_log_context(target: ChannelTalkUserChatV1Target) -> dict[str, object]:
    return {
        "connector": "channel_talk",
        "entity_type": "user_chat",
        "scope_id": target.scope_id,
        "target_id": target.target_id,
        "target_name": target.target_name,
        "expected_count": target.expected_count,
    }


def _failed_langchain_ids_from_result(
    result: SyncExecutionResult,
    seeds: list[ChannelTalkUserChatV1Seed],
) -> list[str]:
    failed_ids = result.metadata.get("failed_ids")
    if isinstance(failed_ids, list):
        return [str(failed_id) for failed_id in failed_ids]
    if result.failed_count <= 0:
        return []
    seed_ids = [seed.langchain_id for seed in seeds]
    return seed_ids[: result.failed_count]


def _build_sync_window() -> SyncWindow:
    now = datetime.now(timezone.utc)
    return SyncWindow(window_start=now, window_end=now)


def _chunked(
    values: list[ChannelTalkUserChatV1Seed],
    size: int,
) -> list[list[ChannelTalkUserChatV1Seed]]:
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


def _channel_talk_user_chat_v1_cte() -> str:
    return f"""
        WITH v1_user_chat AS (
            SELECT
                e.id AS langchain_id,
                e.document AS content,
                e.embedding AS embedding,
                COALESCE(
                    NULLIF(e.cmetadata ->> 'record_id', ''),
                    NULLIF(e.cmetadata #>> '{{user_chat_core,chat,user_chat_id}}', ''),
                    substring(e.id from ':([^:]+)$')
                ) AS record_id,
                COALESCE(
                    NULLIF(e.cmetadata #>> '{{user_chat_core,chat,channel_id}}', ''),
                    substring(e.id from '^channel_talk:user_chat:([^:]+):')
                ) AS scope_id,
                COALESCE(
                    NULLIF(e.cmetadata #>> '{{user_chat_core,chat,channel_id}}', ''),
                    substring(e.id from '^channel_talk:user_chat:([^:]+):')
                ) AS target_id,
                COALESCE(
                    NULLIF(e.cmetadata #>> '{{user_chat_core,chat,channel_name}}', ''),
                    NULLIF(e.cmetadata #>> '{{target_name}}', ''),
                    NULLIF(e.cmetadata #>> '{{user_chat_core,chat,channel_id}}', ''),
                    substring(e.id from '^channel_talk:user_chat:([^:]+):')
                ) AS target_name,
                NULLIF(e.cmetadata ->> 'updated_at', '')::timestamptz AS source_updated_at
            FROM langchain_pg_embedding e
            JOIN langchain_pg_collection c
              ON e.collection_id = c.uuid
            WHERE c.name = :collection_name
              AND e.cmetadata ->> 'source' = 'channel_talk'
              AND e.cmetadata ->> 'entity_type' = 'user_chat'
        )
    """


def build_channel_talk_user_chat_v1_target_query():
    return text(
        f"""
        {_channel_talk_user_chat_v1_cte()},
        candidates AS (
            SELECT
                v1_user_chat.scope_id,
                v1_user_chat.target_id,
                v1_user_chat.target_name,
                (
                    COALESCE(v2.{KNOWLEDGE_STORE_METADATA_JSON_COLUMN}::jsonb, '{{}}'::jsonb) = '{{}}'::jsonb
                    OR v2.{KNOWLEDGE_STORE_ID_COLUMN} IS NULL
                    OR (
                        v2.internal_author_id IS NULL
                        AND NULLIF(
                            v2.{KNOWLEDGE_STORE_METADATA_JSON_COLUMN}::jsonb
                            #>> '{{channel_talk_user_chat,assignment,assignee_id}}',
                            ''
                        ) IS NOT NULL
                    )
                    OR (
                        v1_user_chat.source_updated_at IS NOT NULL
                        AND (
                            v2.updated_at < v1_user_chat.source_updated_at
                            OR (
                                v2.updated_at = v1_user_chat.source_updated_at
                                AND v2.content IS DISTINCT FROM v1_user_chat.content
                            )
                        )
                    )
                ) AS needs_backfill
            FROM v1_user_chat
            LEFT JOIN {KNOWLEDGE_STORE_TABLE_NAME} v2
              ON v2.{KNOWLEDGE_STORE_ID_COLUMN} = v1_user_chat.langchain_id
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
            grouped.expected_count
        FROM grouped
        LEFT JOIN vector_store_v2_backfill_states state
          ON state.connector = 'channel_talk'
         AND state.entity_type = 'user_chat'
         AND state.scope_id = grouped.scope_id
         AND state.target_id = grouped.target_id
        WHERE grouped.pending_count > 0
        {backfill_candidate_state_predicate("state")}
        ORDER BY grouped.scope_id, grouped.target_id
        LIMIT :limit
        """
    )


def build_channel_talk_user_chat_v1_target_seed_query():
    return text(
        f"""
        {_channel_talk_user_chat_v1_cte()},
        candidates AS (
            SELECT
                v1_user_chat.langchain_id,
                v1_user_chat.record_id,
                v1_user_chat.content,
                v1_user_chat.embedding,
                v1_user_chat.scope_id,
                v1_user_chat.target_id,
                (
                    COALESCE(v2.{KNOWLEDGE_STORE_METADATA_JSON_COLUMN}::jsonb, '{{}}'::jsonb) = '{{}}'::jsonb
                    OR v2.{KNOWLEDGE_STORE_ID_COLUMN} IS NULL
                    OR (
                        v2.internal_author_id IS NULL
                        AND NULLIF(
                            v2.{KNOWLEDGE_STORE_METADATA_JSON_COLUMN}::jsonb
                            #>> '{{channel_talk_user_chat,assignment,assignee_id}}',
                            ''
                        ) IS NOT NULL
                    )
                    OR (
                        v1_user_chat.source_updated_at IS NOT NULL
                        AND (
                            v2.updated_at < v1_user_chat.source_updated_at
                            OR (
                                v2.updated_at = v1_user_chat.source_updated_at
                                AND v2.content IS DISTINCT FROM v1_user_chat.content
                            )
                        )
                    )
                ) AS needs_backfill
            FROM v1_user_chat
            LEFT JOIN {KNOWLEDGE_STORE_TABLE_NAME} v2
              ON v2.{KNOWLEDGE_STORE_ID_COLUMN} = v1_user_chat.langchain_id
        )
        SELECT langchain_id, record_id, content, embedding
        FROM candidates
        WHERE scope_id = :scope_id
          AND target_id = :target_id
          AND needs_backfill
        ORDER BY record_id, langchain_id
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
            'channel_talk',
            'user_chat',
            :record_id,
            'channel',
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
            {KNOWLEDGE_STORE_METADATA_JSON_COLUMN} = '{{}}'::json,
            source = EXCLUDED.source,
            entity_type = EXCLUDED.entity_type,
            record_id = EXCLUDED.record_id,
            scope_type = EXCLUDED.scope_type,
            scope_id = EXCLUDED.scope_id,
            target_type = EXCLUDED.target_type,
            target_id = EXCLUDED.target_id,
            target_name = EXCLUDED.target_name,
            internal_author_id = NULL,
            title = '',
            body = '',
            data = '{{}}'::jsonb,
            url = '',
            updated_at = EXCLUDED.updated_at,
            synced_at = EXCLUDED.synced_at
        """
    )


def build_fetch_seeded_seed_chunk_query():
    return text(
        f"""
        WITH seeded_user_chat AS (
            SELECT
                {KNOWLEDGE_STORE_ID_COLUMN} AS langchain_id,
                COALESCE(
                    NULLIF(record_id, ''),
                    substring({KNOWLEDGE_STORE_ID_COLUMN} from ':([^:]+)$')
                ) AS record_id,
                {KNOWLEDGE_STORE_CONTENT_COLUMN} AS content,
                {KNOWLEDGE_STORE_EMBEDDING_COLUMN} AS embedding
            FROM {KNOWLEDGE_STORE_TABLE_NAME}
            WHERE source = 'channel_talk'
              AND entity_type = 'user_chat'
              AND scope_id = :scope_id
              AND target_id = :target_id
              AND COALESCE({KNOWLEDGE_STORE_METADATA_JSON_COLUMN}::jsonb, '{{}}'::jsonb) = '{{}}'::jsonb
        )
        SELECT langchain_id, record_id, content, embedding
        FROM seeded_user_chat
        WHERE (
              CAST(:after_record_id AS text) IS NULL
              OR (record_id, langchain_id) > (
                  CAST(:after_record_id AS text),
                  CAST(:after_langchain_id AS text)
              )
          )
        ORDER BY record_id, langchain_id
        LIMIT :limit
        """
    )


def build_mark_processing_statement():
    return text(
        f"""
        INSERT INTO vector_store_v2_backfill_states (
            connector,
            entity_type,
            scope_id,
            target_id,
            state,
            expected_count,
            backfill_count,
            failed_ids,
            succeeded_at,
            failed_at,
            failure_count,
            last_error_type,
            last_error_message,
            next_retry_at,
            processing_started_at
        )
        VALUES (
            :connector,
            :entity_type,
            :scope_id,
            :target_id,
            'processing',
            :expected_count,
            0,
            '[]'::jsonb,
            NULL,
            NULL,
            0,
            NULL,
            NULL,
            NULL,
            now()
        )
        ON CONFLICT (connector, entity_type, scope_id, target_id) DO UPDATE SET
            state = 'processing',
            expected_count = EXCLUDED.expected_count,
            backfill_count = 0,
            failed_ids = '[]'::jsonb,
            succeeded_at = NULL,
            failed_at = NULL,
            last_error_type = NULL,
            last_error_message = NULL,
            next_retry_at = NULL,
            processing_started_at = now()
        WHERE {backfill_claimable_state_predicate("vector_store_v2_backfill_states").strip()}
        RETURNING processing_started_at
        """
    )


def build_mark_finished_statement():
    return text(
        """
        UPDATE vector_store_v2_backfill_states
        SET state = CAST(:state AS varchar(32)),
            expected_count = :expected_count,
            backfill_count = :backfill_count,
            failed_ids = CAST(:failed_ids AS jsonb),
            succeeded_at = :succeeded_at,
            failed_at = :failed_at,
            failure_count = CASE
                WHEN CAST(:state AS varchar(32)) = 'failed' THEN failure_count + 1
                ELSE 0
            END,
            last_error_type = :last_error_type,
            last_error_message = :last_error_message,
            next_retry_at = :next_retry_at,
            processing_started_at = NULL
        WHERE connector = :connector
          AND entity_type = :entity_type
          AND scope_id = :scope_id
          AND target_id = :target_id
          AND processing_started_at = :processing_started_at
        """
    )
