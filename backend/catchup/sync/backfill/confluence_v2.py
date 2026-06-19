from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime
from datetime import timezone
from typing import cast

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
from catchup.sync.backfill.state import build_failure_metadata
from catchup.sync.backfill.state import build_mark_finished_statement
from catchup.sync.backfill.state import build_mark_processing_statement
from catchup.sync.ingestion.adapters.confluence import ConfluenceV2BackfillAdapter
from catchup.sync.ingestion.adapters.confluence import (
    ConfluenceV2BackfillExecutionRequest,
)
from catchup.sync.ingestion.adapters.confluence import ConfluenceV2BackfillSeed
from catchup.sync.ingestion.adapters.confluence.space_sync import ConfluenceRecordType
from catchup.sync.ingestion.factories.confluence import (
    create_confluence_v2_backfill_adapter,
)
from catchup.sync.ingestion.pipeline import run_sync_ingestion
from catchup.sync.ingestion.schemas import SyncExecutionResult
from catchup.sync.ingestion.schemas import SyncWindow

SessionFactory = Callable[[], AbstractContextManager[Session]]
BackfillAdapterFactory = Callable[[str], Awaitable[ConfluenceV2BackfillAdapter]]
SEED_INSERT_BATCH_SIZE = 100
HYDRATE_PIPELINE_BATCH_SIZE = 50

logger = structlog.get_logger(__name__)


def _validate_confluence_backfill_entity_type(entity_type: str) -> ConfluenceRecordType:
    if entity_type not in {"page", "blogpost"}:
        raise ValueError(f"unsupported confluence backfill entity_type: {entity_type}")
    return cast(ConfluenceRecordType, entity_type)


@dataclass(slots=True, frozen=True)
class ConfluenceV1Seed:
    langchain_id: str
    record_id: str
    content: str
    embedding: list[float]


@dataclass(slots=True, frozen=True)
class ConfluenceV1Target:
    scope_id: str
    target_id: str
    target_name: str
    expected_count: int


@dataclass(slots=True, frozen=True)
class ConfluenceV2BackfillResult:
    scanned: int
    succeeded: int
    skipped: int
    failed: int


class ConfluenceV2BackfillService:
    def __init__(
        self,
        *,
        adapter_factory: BackfillAdapterFactory = create_confluence_v2_backfill_adapter,
        session_factory: SessionFactory = SessionLocal,
        collection_name: str = settings.PGVECTOR_COLLECTION_NAME,
        entity_type: str = "page",
    ) -> None:
        self._adapter_factory = adapter_factory
        self._session_factory = session_factory
        self._collection_name = collection_name
        self._entity_type = _validate_confluence_backfill_entity_type(entity_type)

    async def backfill_batch(
        self,
        *,
        limit: int,
        locked_by: str | None = None,
    ) -> ConfluenceV2BackfillResult:
        del locked_by
        targets = await asyncio.to_thread(self._fetch_candidate_targets_sync, limit)
        succeeded = 0
        skipped = 0
        failed = 0

        async def _process_target(target) -> None:
            nonlocal succeeded, skipped, failed
            adapters: dict[str, ConfluenceV2BackfillAdapter] = {}
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
                failed_ids: list[str] = []
                backfill_count = 0
                after_record_id: str | None = None
                after_langchain_id: str | None = None

                while True:
                    seed_chunk = await asyncio.to_thread(
                        self._fetch_seeded_seed_chunk_for_target_sync,
                        target,
                        after_record_id,
                        after_langchain_id,
                        HYDRATE_PIPELINE_BATCH_SIZE,
                    )
                    if not seed_chunk:
                        break

                    after_record_id = seed_chunk[-1].record_id
                    after_langchain_id = seed_chunk[-1].langchain_id
                    result = await run_sync_ingestion(
                        port=adapter,
                        execution=_build_execution_request(
                            target,
                            seed_chunk,
                            entity_type=self._entity_type,
                        ),
                        sync_window=_build_sync_window(),
                    )
                    chunk_failed_ids = _failed_ids_from_result(result, seed_chunk)
                    failed_ids.extend(chunk_failed_ids)
                    backfill_count += result.persisted_count

                await asyncio.to_thread(
                    self._mark_finished_sync,
                    target,
                    backfill_count,
                    failed_ids,
                    processing_started_at,
                )
                succeeded += backfill_count
                failed += len(failed_ids)
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
                        "confluence_v2_backfill_target_state_update_failed",
                        **_target_log_context(target, self._entity_type),
                        original_error_type=type(exc).__name__,
                        original_error_message=str(exc),
                        state_error_type=type(state_exc).__name__,
                        state_error_message=str(state_exc),
                        exc_info=(type(state_exc), state_exc, state_exc.__traceback__),
                    )
                logger.warning(
                    "confluence_v2_backfill_target_failed",
                    **_target_log_context(target, self._entity_type),
                    exc_info=(type(exc), exc, exc.__traceback__),
                )


        await run_bounded_targets(
            targets,
            concurrency=settings.VECTOR_STORE_V2_BACKFILL_TARGET_CONCURRENCY,
            process_target=_process_target,
        )
        return ConfluenceV2BackfillResult(
            scanned=len(targets),
            succeeded=succeeded,
            skipped=skipped,
            failed=failed,
        )

    async def _get_adapter_for_scope(
        self,
        scope_id: str,
        adapters: dict[str, ConfluenceV2BackfillAdapter],
    ) -> ConfluenceV2BackfillAdapter:
        if scope_id not in adapters:
            adapters[scope_id] = await self._adapter_factory(scope_id)
        return adapters[scope_id]

    def _fetch_candidate_targets_sync(self, limit: int) -> list[ConfluenceV1Target]:
        with self._session_factory() as db:
            rows = db.execute(
                build_confluence_v1_target_query(self._entity_type),
                {"collection_name": self._collection_name, "limit": limit},
            ).mappings()
            return [
                ConfluenceV1Target(
                    scope_id=str(row["scope_id"]),
                    target_id=str(row["target_id"]),
                    target_name=str(row["target_name"]),
                    expected_count=int(row["expected_count"]),
                )
                for row in rows
                if row["scope_id"] and row["target_id"]
            ]

    def _fetch_candidate_seeds_for_target_sync(
        self,
        target: ConfluenceV1Target,
    ) -> list[ConfluenceV1Seed]:
        with self._session_factory() as db:
            rows = db.execute(
                build_confluence_v1_target_seed_query(self._entity_type),
                {
                    "collection_name": self._collection_name,
                    "scope_id": target.scope_id,
                    "target_id": target.target_id,
                },
            ).mappings()
            seeds: list[ConfluenceV1Seed] = []
            for row in rows:
                embedding = _embedding_to_list(row["embedding"])
                if not embedding:
                    continue
                seeds.append(
                    ConfluenceV1Seed(
                        langchain_id=str(row["langchain_id"]),
                        record_id=str(row["record_id"]),
                        content=str(row["content"] or ""),
                        embedding=embedding,
                    )
                )
            return seeds

    def _upsert_seed_rows_sync(
        self,
        target: ConfluenceV1Target,
        seeds: list[ConfluenceV1Seed],
    ) -> int:
        if not seeds:
            return 0
        now = datetime.now(timezone.utc)
        with self._session_factory() as db:
            for seed_batch in _chunked(seeds, SEED_INSERT_BATCH_SIZE):
                db.execute(
                    build_upsert_seed_rows_statement(self._entity_type),
                    [
                        {
                            "langchain_id": seed.langchain_id,
                            "content": seed.content,
                            "embedding": _format_pgvector_embedding(seed.embedding),
                            "record_id": seed.record_id,
                            "scope_id": target.scope_id,
                            "target_id": target.target_id,
                            "target_name": target.target_name,
                            "seeded_at": now,
                        }
                        for seed in seed_batch
                    ],
                )
            db.commit()
        return len(seeds)

    def _fetch_seeded_seed_chunk_for_target_sync(
        self,
        target: ConfluenceV1Target,
        after_record_id: str | None,
        after_langchain_id: str | None,
        limit: int,
    ) -> list[ConfluenceV1Seed]:
        with self._session_factory() as db:
            rows = db.execute(
                build_fetch_pending_seed_chunk_query(self._entity_type),
                {
                    "scope_id": target.scope_id,
                    "target_id": target.target_id,
                    "after_record_id": after_record_id,
                    "after_langchain_id": after_langchain_id,
                    "limit": limit,
                },
            ).mappings()
            return [
                ConfluenceV1Seed(
                    langchain_id=str(row["langchain_id"]),
                    record_id=str(row["record_id"]),
                    content=str(row["content"] or ""),
                    embedding=_embedding_to_list(row["embedding"]),
                )
                for row in rows
                if _embedding_to_list(row["embedding"])
            ]

    def _mark_processing_sync(self, target: ConfluenceV1Target) -> datetime | None:
        with self._session_factory() as db:
            result = db.execute(
                build_mark_processing_statement(),
                {
                    "connector": "confluence",
                    "entity_type": self._entity_type,
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
        target: ConfluenceV1Target,
        backfill_count: int,
        failed_ids: list[str],
        processing_started_at: datetime | None = None,
        *,
        force_failed: bool = False,
        error_type: str | None = None,
        error_message: str | None = None,
    ) -> None:
        now = datetime.now(timezone.utc)
        state = "failed" if force_failed or failed_ids else "succeeded"
        failure_metadata = build_failure_metadata(
            now,
            error_type=error_type or ("PartialBackfillFailure" if failed_ids else None),
            error_message=error_message
            or (f"{len(failed_ids)} v2 documents failed during hydration" if failed_ids else None),
        )
        with self._session_factory() as db:
            update_result = db.execute(
                build_mark_finished_statement(),
                {
                    "connector": "confluence",
                    "entity_type": self._entity_type,
                    "scope_id": target.scope_id,
                    "target_id": target.target_id,
                    "state": state,
                    "expected_count": target.expected_count,
                    "backfill_count": backfill_count,
                    "failed_ids": json.dumps(failed_ids),
                    "succeeded_at": now if state == "succeeded" else None,
                    "failed_at": now if state == "failed" else None,
                    "last_error_type": failure_metadata.last_error_type if state == "failed" else None,
                    "last_error_message": failure_metadata.last_error_message if state == "failed" else None,
                    "next_retry_at": failure_metadata.next_retry_at if state == "failed" else None,
                    "processing_started_at": processing_started_at,
                },
            )
            rowcount = update_result.rowcount
            db.commit()
        if rowcount == 0:
            logger.warning(
                "confluence_v2_backfill_target_finish_update_missed",
                **_target_log_context(target, self._entity_type),
                state=state,
                backfill_count=backfill_count,
                failed_count=len(failed_ids),
                processing_started_at=processing_started_at,
            )


class ConfluenceBlogpostV2BackfillService(ConfluenceV2BackfillService):
    def __init__(
        self,
        *,
        adapter_factory: BackfillAdapterFactory = create_confluence_v2_backfill_adapter,
        session_factory: SessionFactory = SessionLocal,
        collection_name: str = settings.PGVECTOR_COLLECTION_NAME,
    ) -> None:
        super().__init__(
            adapter_factory=adapter_factory,
            session_factory=session_factory,
            collection_name=collection_name,
            entity_type="blogpost",
        )


def _build_execution_request(
    target: ConfluenceV1Target,
    seeds: list[ConfluenceV1Seed],
    *,
    entity_type: str,
) -> ConfluenceV2BackfillExecutionRequest:
    return ConfluenceV2BackfillExecutionRequest(
        tenant_id=target.scope_id,
        target="space",
        space_key=target.target_id,
        space_name=target.target_name,
        record_type=_validate_confluence_backfill_entity_type(entity_type),
        seeds=tuple(
            ConfluenceV2BackfillSeed(
                langchain_id=seed.langchain_id,
                record_id=seed.record_id,
                content=seed.content,
                embedding=seed.embedding,
            )
            for seed in seeds
        ),
    )


def _failed_ids_from_result(
    result: SyncExecutionResult,
    seeds: list[ConfluenceV1Seed],
) -> list[str]:
    failed_ids = result.metadata.get("v2_failed_ids")
    if isinstance(failed_ids, list):
        return [str(failed_id) for failed_id in failed_ids]
    if result.failed_count <= 0:
        return []
    return [seed.langchain_id for seed in seeds[: result.failed_count]]


def _target_log_context(
    target: ConfluenceV1Target,
    entity_type: str,
) -> dict[str, object]:
    return {
        "connector": "confluence",
        "entity_type": entity_type,
        "scope_id": target.scope_id,
        "target_id": target.target_id,
        "target_name": target.target_name,
        "expected_count": target.expected_count,
    }


def _build_sync_window() -> SyncWindow:
    now = datetime.now(timezone.utc)
    return SyncWindow(window_start=now, window_end=now)


def _chunked(values: list[ConfluenceV1Seed], size: int) -> list[list[ConfluenceV1Seed]]:
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


def _confluence_v1_cte(entity_type: str) -> str:
    entity_type = _validate_confluence_backfill_entity_type(entity_type)
    return f"""
        WITH v1_confluence AS (
            SELECT
                e.id AS langchain_id,
                e.document AS content,
                e.embedding AS embedding,
                COALESCE(
                    NULLIF(e.cmetadata ->> 'id', ''),
                    NULLIF(e.cmetadata ->> 'record_id', ''),
                    substring(e.id from '^confluence:{entity_type}:([^:]+):chunk:')
                ) AS record_id,
                COALESCE(
                    NULLIF(e.cmetadata ->> 'cloud_id', ''),
                    NULLIF(e.cmetadata ->> 'scope_id', '')
                ) AS scope_id,
                COALESCE(
                    NULLIF(e.cmetadata ->> 'space_key', ''),
                    NULLIF(e.cmetadata ->> 'target_id', '')
                ) AS target_id,
                COALESCE(
                    NULLIF(e.cmetadata ->> 'space_name', ''),
                    NULLIF(e.cmetadata ->> 'target_name', ''),
                    NULLIF(e.cmetadata ->> 'space_key', ''),
                    NULLIF(e.cmetadata ->> 'target_id', '')
                ) AS target_name,
                NULLIF(e.cmetadata ->> 'updated_at', '')::timestamptz AS source_updated_at
            FROM langchain_pg_embedding e
            JOIN langchain_pg_collection c
              ON e.collection_id = c.uuid
            WHERE c.name = :collection_name
              AND e.cmetadata ->> 'source' = 'confluence'
              AND e.cmetadata ->> 'entity_type' = '{entity_type}'
        )
    """


def _confluence_needs_backfill_expr() -> str:
    return f"""
                    (
                        COALESCE(v2.{KNOWLEDGE_STORE_METADATA_JSON_COLUMN}::jsonb, '{{}}'::jsonb) = '{{}}'::jsonb
                        OR v2.{KNOWLEDGE_STORE_ID_COLUMN} IS NULL
                        OR (
                            v1_confluence.source_updated_at IS NOT NULL
                            AND v2.updated_at < v1_confluence.source_updated_at
                        )
                    )
    """


def build_confluence_v1_target_query(entity_type: str = "page"):
    entity_type = _validate_confluence_backfill_entity_type(entity_type)
    return text(
        f"""
        {_confluence_v1_cte(entity_type)},
        candidates AS (
            SELECT
                v1_confluence.scope_id,
                v1_confluence.target_id,
                v1_confluence.target_name,
                {_confluence_needs_backfill_expr()} AS needs_backfill
            FROM v1_confluence
            LEFT JOIN {KNOWLEDGE_STORE_TABLE_NAME} v2
              ON v2.{KNOWLEDGE_STORE_ID_COLUMN} = v1_confluence.langchain_id
            WHERE COALESCE(v1_confluence.scope_id, '') != ''
              AND COALESCE(v1_confluence.target_id, '') != ''
              AND COALESCE(v1_confluence.record_id, '') != ''
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
        SELECT scope_id, target_id, target_name, expected_count
        FROM grouped
        LEFT JOIN vector_store_v2_backfill_states state
          ON state.connector = 'confluence'
         AND state.entity_type = '{entity_type}'
         AND state.scope_id = grouped.scope_id
         AND state.target_id = grouped.target_id
        WHERE grouped.pending_count > 0
        {backfill_candidate_state_predicate("state")}
        ORDER BY scope_id, target_id
        LIMIT :limit
        """
    )


def build_confluence_v1_target_seed_query(entity_type: str = "page"):
    entity_type = _validate_confluence_backfill_entity_type(entity_type)
    return text(
        f"""
        {_confluence_v1_cte(entity_type)},
        candidates AS (
            SELECT
                v1_confluence.langchain_id,
                v1_confluence.record_id,
                v1_confluence.content,
                v1_confluence.embedding,
                v1_confluence.scope_id,
                v1_confluence.target_id,
                {_confluence_needs_backfill_expr()} AS needs_backfill
            FROM v1_confluence
            LEFT JOIN {KNOWLEDGE_STORE_TABLE_NAME} v2
              ON v2.{KNOWLEDGE_STORE_ID_COLUMN} = v1_confluence.langchain_id
        )
        SELECT langchain_id, record_id, content, embedding
        FROM candidates
        WHERE scope_id = :scope_id
          AND target_id = :target_id
          AND needs_backfill
        ORDER BY record_id, langchain_id
        """
    )


def build_upsert_seed_rows_statement(entity_type: str = "page"):
    entity_type = _validate_confluence_backfill_entity_type(entity_type)
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
            'confluence',
            '{entity_type}',
            :record_id,
            'cloud',
            :scope_id,
            'space',
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


def build_fetch_pending_seed_chunk_query(entity_type: str = "page"):
    entity_type = _validate_confluence_backfill_entity_type(entity_type)
    return text(
        f"""
        SELECT
            {KNOWLEDGE_STORE_ID_COLUMN} AS langchain_id,
            record_id,
            {KNOWLEDGE_STORE_CONTENT_COLUMN} AS content,
            {KNOWLEDGE_STORE_EMBEDDING_COLUMN} AS embedding
        FROM {KNOWLEDGE_STORE_TABLE_NAME}
        WHERE source = 'confluence'
          AND entity_type = '{entity_type}'
          AND scope_id = :scope_id
          AND target_id = :target_id
          AND COALESCE({KNOWLEDGE_STORE_METADATA_JSON_COLUMN}::jsonb, '{{}}'::jsonb) = '{{}}'::jsonb
          AND (
              CAST(:after_record_id AS text) IS NULL
              OR record_id > CAST(:after_record_id AS text)
              OR (
                  record_id = CAST(:after_record_id AS text)
                  AND {KNOWLEDGE_STORE_ID_COLUMN} > COALESCE(CAST(:after_langchain_id AS text), '')
              )
          )
        ORDER BY record_id, {KNOWLEDGE_STORE_ID_COLUMN}
        LIMIT :limit
        """
    )
