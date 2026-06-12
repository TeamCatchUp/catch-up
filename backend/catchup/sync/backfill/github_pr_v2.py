from __future__ import annotations

import asyncio
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
from catchup.sync.ingestion.adapters.github import GithubPrV2BackfillAdapter
from catchup.sync.ingestion.adapters.github import GithubPrV2BackfillExecutionRequest
from catchup.sync.ingestion.adapters.github import GithubPrV2BackfillSeed
from catchup.sync.ingestion.factories.github import create_github_pr_v2_backfill_adapter
from catchup.sync.ingestion.pipeline import run_sync_ingestion
from catchup.sync.ingestion.schemas import SyncExecutionResult
from catchup.sync.ingestion.schemas import SyncWindow

SessionFactory = Callable[[], AbstractContextManager[Session]]
BackfillAdapterFactory = Callable[[int], Awaitable[GithubPrV2BackfillAdapter]]
SEED_INSERT_BATCH_SIZE = 100
HYDRATE_PIPELINE_BATCH_SIZE = 50

logger = structlog.get_logger(__name__)


@dataclass(slots=True, frozen=True)
class GithubPrV1Seed:
    langchain_id: str
    record_id: str
    content: str
    embedding: list[float]


@dataclass(slots=True, frozen=True)
class GithubPrV1Target:
    scope_id: str
    target_id: str
    expected_count: int

    @property
    def owner(self) -> str:
        return self.target_id.split("/", 1)[0]

    @property
    def repo(self) -> str:
        return self.target_id.split("/", 1)[1]


@dataclass(slots=True, frozen=True)
class GithubPrV2BackfillResult:
    scanned: int
    succeeded: int
    skipped: int
    failed: int


class GithubPrV2BackfillService:
    def __init__(
        self,
        *,
        adapter_factory: BackfillAdapterFactory = create_github_pr_v2_backfill_adapter,
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
    ) -> GithubPrV2BackfillResult:
        del locked_by
        targets = await asyncio.to_thread(self._fetch_candidate_targets_sync, limit)
        logger.info(
            "github_pr_v2_backfill_candidate_targets_fetched",
            connector="github",
            entity_type="pr",
            limit=limit,
            target_count=len(targets),
        )
        succeeded = 0
        skipped = 0
        failed = 0
        adapters: dict[str, GithubPrV2BackfillAdapter] = {}

        for target in targets:
            try:
                claimed = await asyncio.to_thread(
                    self._mark_processing_sync,
                    target,
                )
                if not claimed:
                    logger.info(
                        "github_pr_v2_backfill_target_claim_skipped",
                        **_target_log_context(target),
                        reason="already_processing",
                    )
                    skipped += 1
                    continue
                logger.info(
                    "github_pr_v2_backfill_target_claimed",
                    **_target_log_context(target),
                )

                seeds = await asyncio.to_thread(
                    self._fetch_candidate_seeds_for_target_sync,
                    target,
                )
                logger.info(
                    "github_pr_v2_backfill_v1_seeds_fetched",
                    **_target_log_context(target),
                    seed_count=len(seeds),
                )
                upserted_seed_count = await asyncio.to_thread(
                    self._upsert_seed_rows_sync,
                    target,
                    seeds,
                )
                logger.info(
                    "github_pr_v2_backfill_seed_rows_upserted",
                    **_target_log_context(target),
                    seed_count=len(seeds),
                    upserted_count=upserted_seed_count,
                    seed_insert_batch_size=SEED_INSERT_BATCH_SIZE,
                )
                adapter = await self._get_adapter_for_scope(target.scope_id, adapters)
                failed_ids: list[str] = []
                backfill_count = 0
                after_record_id: int | None = None
                chunk_index = 0

                while True:
                    seed_chunk = await asyncio.to_thread(
                        self._fetch_seeded_seed_chunk_for_target_sync,
                        target,
                        after_record_id,
                        HYDRATE_PIPELINE_BATCH_SIZE,
                    )
                    if not seed_chunk:
                        break

                    chunk_index += 1
                    next_after_record_id = _record_id_to_int(seed_chunk[-1].record_id)
                    logger.info(
                        "github_pr_v2_backfill_seeded_chunk_started",
                        **_target_log_context(target),
                        chunk_index=chunk_index,
                        seed_count=len(seed_chunk),
                        hydrate_batch_size=HYDRATE_PIPELINE_BATCH_SIZE,
                        after_record_id=after_record_id,
                        last_record_id=seed_chunk[-1].record_id,
                        last_langchain_id=seed_chunk[-1].langchain_id,
                    )
                    after_record_id = next_after_record_id
                    result = await run_sync_ingestion(
                        port=adapter,
                        execution=_build_execution_request(target, seed_chunk),
                        sync_window=_build_sync_window(),
                    )
                    chunk_failed_ids = _failed_ids_from_result(result, seed_chunk)
                    failed_ids.extend(chunk_failed_ids)
                    backfill_count += result.persisted_count
                    logger.info(
                        "github_pr_v2_backfill_seeded_chunk_completed",
                        **_target_log_context(target),
                        chunk_index=chunk_index,
                        seed_count=len(seed_chunk),
                        persisted_count=result.persisted_count,
                        failed_count=len(chunk_failed_ids),
                        failed_ids=chunk_failed_ids,
                    )

                await asyncio.to_thread(
                    self._mark_finished_sync,
                    target,
                    backfill_count,
                    failed_ids,
                )
                logger.info(
                    "github_pr_v2_backfill_target_finished",
                    **_target_log_context(target),
                    state="failed" if failed_ids else "succeeded",
                    backfill_count=backfill_count,
                    failed_count=len(failed_ids),
                    failed_ids=failed_ids,
                )
                succeeded += backfill_count
                failed += len(failed_ids)
            except Exception as exc:
                failed += target.expected_count
                await asyncio.to_thread(
                    self._mark_finished_sync,
                    target,
                    0,
                    [],
                    force_failed=True,
                )
                logger.warning(
                    "github_pr_v2_backfill_target_finished",
                    **_target_log_context(target),
                    state="failed",
                    backfill_count=0,
                    failed_count=target.expected_count,
                    failed_ids=[],
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                    exc_info=True,
                )

        return GithubPrV2BackfillResult(
            scanned=len(targets),
            succeeded=succeeded,
            skipped=skipped,
            failed=failed,
        )

    async def _get_adapter_for_scope(
        self,
        scope_id: str,
        adapters: dict[str, GithubPrV2BackfillAdapter],
    ) -> GithubPrV2BackfillAdapter:
        if scope_id not in adapters:
            adapters[scope_id] = await self._adapter_factory(int(scope_id))
        return adapters[scope_id]

    def _fetch_candidate_targets_sync(self, limit: int) -> list[GithubPrV1Target]:
        query = build_github_pr_v1_target_query()
        with self._session_factory() as db:
            rows = db.execute(
                query,
                {
                    "collection_name": self._collection_name,
                    "limit": limit,
                },
            ).mappings()
            return [
                GithubPrV1Target(
                    scope_id=str(row["scope_id"]),
                    target_id=str(row["target_id"]),
                    expected_count=int(row["expected_count"]),
                )
                for row in rows
            ]

    def _fetch_candidate_seeds_for_target_sync(
        self,
        target: GithubPrV1Target,
    ) -> list[GithubPrV1Seed]:
        query = build_github_pr_v1_target_seed_query()
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
                GithubPrV1Seed(
                    langchain_id=row["langchain_id"],
                    record_id=row["record_id"],
                    content=row["content"],
                    embedding=_embedding_to_list(row["embedding"]),
                )
                for row in rows
            ]

    def _upsert_seed_rows_sync(
        self,
        target: GithubPrV1Target,
        seeds: list[GithubPrV1Seed],
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
                            "seeded_at": seeded_at,
                        }
                        for seed in batch
                    ],
                )
                affected += len(batch)
            db.commit()
        return affected

    def _fetch_seeded_seed_chunk_for_target_sync(
        self,
        target: GithubPrV1Target,
        after_record_id: int | None,
        limit: int,
    ) -> list[GithubPrV1Seed]:
        query = build_fetch_seeded_seed_chunk_query()
        with self._session_factory() as db:
            rows = db.execute(
                query,
                {
                    "scope_id": target.scope_id,
                    "target_id": target.target_id,
                    "after_record_id": after_record_id,
                    "limit": limit,
                },
            ).mappings()
            return [
                GithubPrV1Seed(
                    langchain_id=row["langchain_id"],
                    record_id=row["record_id"],
                    content=row["content"],
                    embedding=_embedding_to_list(row["embedding"]),
                )
                for row in rows
            ]

    def _mark_processing_sync(self, target: GithubPrV1Target) -> bool:
        with self._session_factory() as db:
            result = db.execute(
                build_mark_processing_statement(),
                {
                    "connector": "github",
                    "entity_type": "pr",
                    "scope_id": target.scope_id,
                    "target_id": target.target_id,
                    "expected_count": target.expected_count,
                },
            )
            claimed = result.first() is not None
            db.commit()
            return claimed

    def _mark_finished_sync(
        self,
        target: GithubPrV1Target,
        backfill_count: int,
        failed_ids: list[str],
        *,
        force_failed: bool = False,
    ) -> None:
        now = datetime.now(timezone.utc)
        state = "failed" if force_failed or failed_ids else "succeeded"
        with self._session_factory() as db:
            db.execute(
                build_mark_finished_statement(),
                {
                    "connector": "github",
                    "entity_type": "pr",
                    "scope_id": target.scope_id,
                    "target_id": target.target_id,
                    "state": state,
                    "expected_count": target.expected_count,
                    "backfill_count": backfill_count,
                    "failed_ids": failed_ids,
                    "succeeded_at": now if state == "succeeded" else None,
                    "failed_at": now if state == "failed" else None,
                },
            )
            db.commit()


def _build_execution_request(
    target: GithubPrV1Target,
    seeds: list[GithubPrV1Seed],
) -> GithubPrV2BackfillExecutionRequest:
    return GithubPrV2BackfillExecutionRequest(
        tenant_id=target.scope_id,
        owner=target.owner,
        repo=target.repo,
        seeds=tuple(
            GithubPrV2BackfillSeed(
                langchain_id=seed.langchain_id,
                record_id=seed.record_id,
                content=seed.content,
                embedding=seed.embedding,
            )
            for seed in seeds
        ),
    )


def _target_log_context(target: GithubPrV1Target) -> dict[str, object]:
    return {
        "connector": "github",
        "entity_type": "pr",
        "scope_id": target.scope_id,
        "target_id": target.target_id,
        "expected_count": target.expected_count,
    }


def _failed_ids_from_result(
    result: SyncExecutionResult,
    seeds: list[GithubPrV1Seed],
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
    values: list[GithubPrV1Seed],
    size: int,
) -> list[list[GithubPrV1Seed]]:
    return [values[index : index + size] for index in range(0, len(values), size)]


def _format_pgvector_embedding(embedding: list[float]) -> str:
    return f"[{','.join(format(float(value), '.12g') for value in embedding)}]"


def _embedding_to_list(value) -> list[float]:
    if isinstance(value, str):
        raw = value.strip().removeprefix("[").removesuffix("]")
        if not raw:
            return []
        return [float(item.strip()) for item in raw.split(",")]
    return list(value)


def _record_id_to_int(record_id: str) -> int:
    return int(record_id)


def build_github_pr_v1_target_query():
    return text(
        f"""
        WITH v1_pr AS (
            SELECT
                e.id AS langchain_id,
                e.document AS content,
                e.cmetadata AS metadata,
                NULLIF(e.cmetadata ->> 'updated_at', '')::timestamptz AS source_updated_at,
                COALESCE(NULLIF(e.cmetadata ->> 'installation_id', ''), '') AS scope_id,
                COALESCE(
                    CASE
                        WHEN NULLIF(e.cmetadata ->> 'owner', '') IS NOT NULL
                         AND NULLIF(e.cmetadata ->> 'repo', '') IS NOT NULL
                        THEN (e.cmetadata ->> 'owner') || '/' || (e.cmetadata ->> 'repo')
                        ELSE substring(e.id from '^github:pr:([^:]+):')
                    END,
                    ''
                ) AS target_id
            FROM langchain_pg_embedding e
            JOIN langchain_pg_collection c
              ON e.collection_id = c.uuid
            WHERE c.name = :collection_name
              AND e.cmetadata ->> 'source' = 'github'
              AND e.cmetadata ->> 'entity_type' = 'pr'
        ),
        candidates AS (
            SELECT
                v1_pr.scope_id,
                v1_pr.target_id,
                (
                    COALESCE(v2.{KNOWLEDGE_STORE_METADATA_JSON_COLUMN}::jsonb, '{{}}'::jsonb) = '{{}}'::jsonb
                    OR v2.{KNOWLEDGE_STORE_ID_COLUMN} IS NULL
                    OR (
                        v1_pr.source_updated_at IS NOT NULL
                        AND (
                            v2.updated_at < v1_pr.source_updated_at
                            OR (
                                v2.updated_at = v1_pr.source_updated_at
                                AND v2.content IS DISTINCT FROM v1_pr.content
                            )
                        )
                    )
                ) AS needs_backfill
            FROM v1_pr
            LEFT JOIN {KNOWLEDGE_STORE_TABLE_NAME} v2
              ON v2.{KNOWLEDGE_STORE_ID_COLUMN} = v1_pr.langchain_id
        ),
        grouped AS (
            SELECT
                scope_id,
                target_id,
                count(*) AS expected_count,
                count(*) FILTER (WHERE needs_backfill) AS pending_count
            FROM candidates
            GROUP BY scope_id, target_id
        )
        SELECT
            grouped.scope_id,
            grouped.target_id,
            grouped.expected_count
        FROM grouped
        LEFT JOIN vector_store_v2_backfill_states state
          ON state.connector = 'github'
         AND state.entity_type = 'pr'
         AND state.scope_id = grouped.scope_id
         AND state.target_id = grouped.target_id
        WHERE grouped.pending_count > 0
          AND (
              state.state IS NULL
              OR state.state != 'processing'
          )
        ORDER BY grouped.scope_id, grouped.target_id
        LIMIT :limit
        """
    )


def build_github_pr_v1_target_seed_query():
    return text(
        f"""
        WITH v1_pr AS (
            SELECT
                e.id AS langchain_id,
                e.document AS content,
                e.embedding AS embedding,
                COALESCE(
                    NULLIF(e.cmetadata ->> 'number', ''),
                    substring(e.id from ':([^:]+)$')
                ) AS record_id,
                NULLIF(e.cmetadata ->> 'updated_at', '')::timestamptz AS source_updated_at,
                COALESCE(NULLIF(e.cmetadata ->> 'installation_id', ''), '') AS scope_id,
                COALESCE(
                    CASE
                        WHEN NULLIF(e.cmetadata ->> 'owner', '') IS NOT NULL
                         AND NULLIF(e.cmetadata ->> 'repo', '') IS NOT NULL
                        THEN (e.cmetadata ->> 'owner') || '/' || (e.cmetadata ->> 'repo')
                        ELSE substring(e.id from '^github:pr:([^:]+):')
                    END,
                    ''
                ) AS target_id
            FROM langchain_pg_embedding e
            JOIN langchain_pg_collection c
              ON e.collection_id = c.uuid
            WHERE c.name = :collection_name
              AND e.cmetadata ->> 'source' = 'github'
              AND e.cmetadata ->> 'entity_type' = 'pr'
        ),
        candidates AS (
            SELECT
                v1_pr.langchain_id,
                v1_pr.record_id,
                v1_pr.content,
                v1_pr.embedding,
                v1_pr.scope_id,
                v1_pr.target_id,
                (
                    COALESCE(v2.{KNOWLEDGE_STORE_METADATA_JSON_COLUMN}::jsonb, '{{}}'::jsonb) = '{{}}'::jsonb
                    OR v2.{KNOWLEDGE_STORE_ID_COLUMN} IS NULL
                    OR (
                        v1_pr.source_updated_at IS NOT NULL
                        AND (
                            v2.updated_at < v1_pr.source_updated_at
                            OR (
                                v2.updated_at = v1_pr.source_updated_at
                                AND v2.content IS DISTINCT FROM v1_pr.content
                            )
                        )
                    )
                ) AS needs_backfill
            FROM v1_pr
            LEFT JOIN {KNOWLEDGE_STORE_TABLE_NAME} v2
              ON v2.{KNOWLEDGE_STORE_ID_COLUMN} = v1_pr.langchain_id
        )
        SELECT
            candidates.langchain_id,
            candidates.record_id,
            candidates.content,
            candidates.embedding
        FROM candidates
        WHERE candidates.scope_id = :scope_id
          AND candidates.target_id = :target_id
          AND candidates.needs_backfill
        ORDER BY candidates.langchain_id
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
            'github',
            'pr',
            :record_id,
            'installation',
            :scope_id,
            'repository',
            :target_id,
            :target_id,
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
        WITH seeded_pr AS (
            SELECT
                {KNOWLEDGE_STORE_ID_COLUMN} AS langchain_id,
                COALESCE(
                    NULLIF(record_id, ''),
                    substring({KNOWLEDGE_STORE_ID_COLUMN} from ':([^:]+)$')
                ) AS record_id,
                {KNOWLEDGE_STORE_CONTENT_COLUMN} AS content,
                {KNOWLEDGE_STORE_EMBEDDING_COLUMN} AS embedding
            FROM {KNOWLEDGE_STORE_TABLE_NAME}
            WHERE source = 'github'
              AND entity_type = 'pr'
              AND scope_id = :scope_id
              AND target_id = :target_id
              AND COALESCE({KNOWLEDGE_STORE_METADATA_JSON_COLUMN}::jsonb, '{{}}'::jsonb) = '{{}}'::jsonb
        ),
        numbered_seeded_pr AS (
            SELECT
                langchain_id,
                record_id,
                content,
                embedding,
                record_id::integer AS record_number
            FROM seeded_pr
            WHERE record_id ~ '^[0-9]+$'
        )
        SELECT
            langchain_id,
            record_id,
            content,
            embedding
        FROM numbered_seeded_pr
        WHERE (
              CAST(:after_record_id AS integer) IS NULL
              OR record_number > CAST(:after_record_id AS integer)
          )
        ORDER BY record_number
        LIMIT :limit
        """
    )


def build_mark_processing_statement():
    return text(
        """
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
            failed_at
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
            NULL
        )
        ON CONFLICT (connector, entity_type, scope_id, target_id) DO UPDATE SET
            state = 'processing',
            expected_count = EXCLUDED.expected_count,
            backfill_count = 0,
            failed_ids = '[]'::jsonb,
            succeeded_at = NULL,
            failed_at = NULL
        WHERE vector_store_v2_backfill_states.state != 'processing'
        RETURNING id
        """
    )


def build_mark_finished_statement():
    return text(
        """
        UPDATE vector_store_v2_backfill_states
        SET state = :state,
            expected_count = :expected_count,
            backfill_count = :backfill_count,
            failed_ids = :failed_ids,
            succeeded_at = :succeeded_at,
            failed_at = :failed_at
        WHERE connector = :connector
          AND entity_type = :entity_type
          AND scope_id = :scope_id
          AND target_id = :target_id
        """
    )
