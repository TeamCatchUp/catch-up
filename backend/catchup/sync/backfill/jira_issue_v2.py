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
from catchup.sync.backfill.state import build_failure_metadata
from catchup.sync.ingestion.adapters.jira import JiraIssueV2BackfillAdapter
from catchup.sync.ingestion.adapters.jira import JiraIssueV2BackfillExecutionRequest
from catchup.sync.ingestion.adapters.jira import JiraIssueV2BackfillSeed
from catchup.sync.ingestion.adapters.jira import create_jira_issue_v2_backfill_adapter
from catchup.sync.ingestion.pipeline import run_sync_ingestion
from catchup.sync.ingestion.schemas import SyncExecutionResult
from catchup.sync.ingestion.schemas import SyncWindow

SessionFactory = Callable[[], AbstractContextManager[Session]]
BackfillAdapterFactory = Callable[[str], Awaitable[JiraIssueV2BackfillAdapter]]
SEED_INSERT_BATCH_SIZE = 100
HYDRATE_PIPELINE_BATCH_SIZE = 50

logger = structlog.get_logger(__name__)


@dataclass(slots=True, frozen=True)
class JiraIssueV1Seed:
    langchain_id: str
    record_id: str
    content: str
    embedding: list[float]


@dataclass(slots=True, frozen=True)
class JiraIssueV1Target:
    scope_id: str
    target_id: str
    target_name: str
    expected_count: int


@dataclass(slots=True, frozen=True)
class JiraIssueV2BackfillResult:
    scanned: int
    succeeded: int
    skipped: int
    failed: int


class JiraIssueV2BackfillService:
    def __init__(
        self,
        *,
        adapter_factory: BackfillAdapterFactory = create_jira_issue_v2_backfill_adapter,
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
    ) -> JiraIssueV2BackfillResult:
        del locked_by
        targets = await asyncio.to_thread(self._fetch_candidate_targets_sync, limit)
        succeeded = 0
        skipped = 0
        failed = 0

        async def _process_target(target) -> None:
            nonlocal succeeded, skipped, failed
            adapters: dict[str, JiraIssueV2BackfillAdapter] = {}
            try:
                claimed = await asyncio.to_thread(self._mark_processing_sync, target)
                if not claimed:
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
                )
                succeeded += backfill_count
                failed += len(failed_ids)
            except Exception:
                failed += target.expected_count
                await asyncio.to_thread(
                    self._mark_finished_sync,
                    target,
                    0,
                    [],
                    force_failed=True,
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                )
                logger.warning(
                    "jira_issue_v2_backfill_target_failed",
                    **_target_log_context(target),
                    exc_info=True,
                )


        await run_bounded_targets(
            targets,
            concurrency=settings.VECTOR_STORE_V2_BACKFILL_TARGET_CONCURRENCY,
            process_target=_process_target,
        )
        return JiraIssueV2BackfillResult(
            scanned=len(targets),
            succeeded=succeeded,
            skipped=skipped,
            failed=failed,
        )

    async def _get_adapter_for_scope(
        self,
        scope_id: str,
        adapters: dict[str, JiraIssueV2BackfillAdapter],
    ) -> JiraIssueV2BackfillAdapter:
        if scope_id not in adapters:
            adapters[scope_id] = await self._adapter_factory(scope_id)
        return adapters[scope_id]

    def _fetch_candidate_targets_sync(self, limit: int) -> list[JiraIssueV1Target]:
        with self._session_factory() as db:
            rows = db.execute(
                build_jira_v1_target_query(),
                {
                    "collection_name": self._collection_name,
                    "limit": limit,
                },
            ).mappings()
            return [
                JiraIssueV1Target(
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
        target: JiraIssueV1Target,
    ) -> list[JiraIssueV1Seed]:
        with self._session_factory() as db:
            rows = db.execute(
                build_jira_v1_target_seed_query(),
                {
                    "collection_name": self._collection_name,
                    "scope_id": target.scope_id,
                    "target_id": target.target_id,
                },
            ).mappings()
            seeds: list[JiraIssueV1Seed] = []
            for row in rows:
                embedding = _embedding_to_list(row["embedding"])
                if not embedding:
                    continue
                seeds.append(
                    JiraIssueV1Seed(
                        langchain_id=str(row["langchain_id"]),
                        record_id=str(row["record_id"]),
                        content=str(row["content"] or ""),
                        embedding=embedding,
                    )
                )
            return seeds

    def _upsert_seed_rows_sync(
        self,
        target: JiraIssueV1Target,
        seeds: list[JiraIssueV1Seed],
    ) -> int:
        if not seeds:
            return 0
        now = datetime.now(timezone.utc)
        with self._session_factory() as db:
            for seed_batch in _chunked(seeds, SEED_INSERT_BATCH_SIZE):
                db.execute(
                    build_upsert_seed_rows_statement(),
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
        target: JiraIssueV1Target,
        after_record_id: str | None,
        after_langchain_id: str | None,
        limit: int,
    ) -> list[JiraIssueV1Seed]:
        with self._session_factory() as db:
            rows = db.execute(
                build_fetch_pending_seed_chunk_query(),
                {
                    "scope_id": target.scope_id,
                    "target_id": target.target_id,
                    "after_record_id": after_record_id,
                    "after_langchain_id": after_langchain_id,
                    "limit": limit,
                },
            ).mappings()
            return [
                JiraIssueV1Seed(
                    langchain_id=str(row["langchain_id"]),
                    record_id=str(row["record_id"]),
                    content=str(row["content"] or ""),
                    embedding=_embedding_to_list(row["embedding"]),
                )
                for row in rows
                if _embedding_to_list(row["embedding"])
            ]

    def _mark_processing_sync(self, target: JiraIssueV1Target) -> bool:
        with self._session_factory() as db:
            result = db.execute(
                build_mark_processing_statement(),
                {
                    "connector": "jira",
                    "entity_type": "issue",
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
        target: JiraIssueV1Target,
        backfill_count: int,
        failed_ids: list[str],
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
            db.execute(
                build_mark_finished_statement(),
                {
                    "connector": "jira",
                    "entity_type": "issue",
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
                },
            )
            db.commit()


def _build_execution_request(
    target: JiraIssueV1Target,
    seeds: list[JiraIssueV1Seed],
) -> JiraIssueV2BackfillExecutionRequest:
    return JiraIssueV2BackfillExecutionRequest(
        tenant_id=target.scope_id,
        target="issue_v2_backfill",
        project_key=target.target_id,
        seeds=tuple(
            JiraIssueV2BackfillSeed(
                langchain_id=seed.langchain_id,
                record_id=seed.record_id,
                content=seed.content,
                embedding=seed.embedding,
            )
            for seed in seeds
        ),
    )


def _target_log_context(
    target: JiraIssueV1Target,
) -> dict[str, object]:
    return {
        "connector": "jira",
        "entity_type": "issue",
        "scope_id": target.scope_id,
        "target_id": target.target_id,
        "target_name": target.target_name,
        "expected_count": target.expected_count,
    }


def _failed_ids_from_result(
    result: SyncExecutionResult,
    seeds: list[JiraIssueV1Seed],
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
    values: list[JiraIssueV1Seed],
    size: int,
) -> list[list[JiraIssueV1Seed]]:
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


def _jira_issue_v1_cte() -> str:
    return f"""
        WITH v1_issue_source AS (
            SELECT
                e.id AS v1_langchain_id,
                e.cmetadata ->> 'entity_type' AS source_entity_type,
                e.document AS content,
                e.embedding AS embedding,
                COALESCE(
                    NULLIF(e.cmetadata ->> 'issue_key', ''),
                    NULLIF(e.cmetadata ->> 'record_id', ''),
                    substring(e.id from '^jira:(?:issue|epic):(.+)$')
                ) AS record_id,
                COALESCE(
                    NULLIF(e.cmetadata ->> 'project_key', ''),
                    split_part(
                    COALESCE(
                        NULLIF(e.cmetadata ->> 'issue_key', ''),
                        NULLIF(e.cmetadata ->> 'record_id', ''),
                        substring(e.id from '^jira:(?:issue|epic):(.+)$')
                    ),
                        '-',
                        1
                    )
                ) AS target_id,
                COALESCE(
                    NULLIF(e.cmetadata ->> 'cloud_id', ''),
                    NULLIF(e.cmetadata ->> 'scope_id', '')
                ) AS source_scope_id,
                NULLIF(e.cmetadata ->> 'url', '') AS issue_url,
                NULLIF(e.cmetadata ->> 'updated_at', '')::timestamptz
                    AS source_updated_at
            FROM langchain_pg_embedding e
            JOIN langchain_pg_collection c
              ON e.collection_id = c.uuid
            WHERE c.name = :collection_name
              AND e.cmetadata ->> 'source' = 'jira'
              AND e.cmetadata ->> 'entity_type' IN ('issue', 'epic')
        ),
        project_candidates AS (
            SELECT
                ('jira:issue:' || jp.cloud_id || ':' || v1_issue_source.target_id || ':'
                    || v1_issue_source.record_id) AS langchain_id,
                v1_issue_source.v1_langchain_id,
                v1_issue_source.source_entity_type,
                v1_issue_source.record_id,
                v1_issue_source.content,
                v1_issue_source.embedding,
                v1_issue_source.target_id,
                jp.cloud_id AS scope_id,
                jp.project_name AS target_name,
                v1_issue_source.source_updated_at,
                count(*) OVER (
                    PARTITION BY v1_issue_source.v1_langchain_id
                ) AS project_match_count
            FROM v1_issue_source
            JOIN jira_projects jp
              ON jp.project_key = v1_issue_source.target_id
             AND (
                    jp.cloud_id = v1_issue_source.source_scope_id
                    OR (
                        v1_issue_source.source_scope_id IS NULL
                        AND substring(v1_issue_source.issue_url from '^https?://([^/]+)')
                            = substring(jp.url from '^https?://([^/]+)')
                    )
             )
            WHERE COALESCE(v1_issue_source.record_id, '') != ''
              AND COALESCE(v1_issue_source.target_id, '') != ''
        ),
        single_project_candidates AS (
            SELECT *
            FROM project_candidates
            WHERE project_match_count = 1
        ),
        ranked_project_candidates AS (
            SELECT
                *,
                row_number() OVER (
                    PARTITION BY langchain_id
                    ORDER BY
                        source_updated_at DESC NULLS LAST,
                        CASE source_entity_type WHEN 'issue' THEN 0 ELSE 1 END,
                        v1_langchain_id
                ) AS canonical_rank
            FROM single_project_candidates
        ),
        v1_issue_with_target AS (
            SELECT
                langchain_id,
                record_id,
                content,
                embedding,
                target_id,
                scope_id,
                target_name,
                source_updated_at
            FROM ranked_project_candidates
            WHERE canonical_rank = 1
        )
    """


def build_jira_issue_v1_target_query():
    return build_jira_v1_target_query()


def build_jira_v1_target_query():
    return text(
        f"""
        {_jira_issue_v1_cte()},
        candidates AS (
            SELECT
                v1_issue_with_target.scope_id,
                v1_issue_with_target.target_id,
                v1_issue_with_target.target_name,
                (
                    COALESCE(v2.{KNOWLEDGE_STORE_METADATA_JSON_COLUMN}::jsonb, '{{}}'::jsonb) = '{{}}'::jsonb
                    OR v2.{KNOWLEDGE_STORE_ID_COLUMN} IS NULL
                    OR (
                        v2.internal_author_id IS NULL
                        AND COALESCE(
                            v2.{KNOWLEDGE_STORE_METADATA_JSON_COLUMN}::jsonb
                                #>> '{{jira_issue,assignee,account_id}}',
                            ''
                        ) != ''
                    )
                    OR (
                        v1_issue_with_target.source_updated_at IS NOT NULL
                        AND (
                            v2.updated_at < v1_issue_with_target.source_updated_at
                            OR (
                                v2.updated_at = v1_issue_with_target.source_updated_at
                                AND v2.content IS DISTINCT FROM v1_issue_with_target.content
                            )
                        )
                    )
                ) AS needs_backfill
            FROM v1_issue_with_target
            LEFT JOIN {KNOWLEDGE_STORE_TABLE_NAME} v2
              ON v2.{KNOWLEDGE_STORE_ID_COLUMN} = v1_issue_with_target.langchain_id
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
          ON state.connector = 'jira'
         AND state.entity_type = 'issue'
         AND state.scope_id = grouped.scope_id
         AND state.target_id = grouped.target_id
        WHERE grouped.pending_count > 0
          AND (state.state IS NULL OR (
                  state.state IN ('pending', 'succeeded')
                  OR (
                      state.state = 'failed'
                      AND state.next_retry_at <= now()
                  )
              ))
        ORDER BY grouped.scope_id, grouped.target_id
        LIMIT :limit
        """
    )


def build_jira_issue_v1_target_seed_query():
    return build_jira_v1_target_seed_query()


def build_jira_v1_target_seed_query():
    return text(
        f"""
        {_jira_issue_v1_cte()},
        candidates AS (
            SELECT
                v1_issue_with_target.langchain_id,
                v1_issue_with_target.record_id,
                v1_issue_with_target.content,
                v1_issue_with_target.embedding,
                v1_issue_with_target.scope_id,
                v1_issue_with_target.target_id,
                (
                    COALESCE(v2.{KNOWLEDGE_STORE_METADATA_JSON_COLUMN}::jsonb, '{{}}'::jsonb) = '{{}}'::jsonb
                    OR v2.{KNOWLEDGE_STORE_ID_COLUMN} IS NULL
                    OR (
                        v2.internal_author_id IS NULL
                        AND COALESCE(
                            v2.{KNOWLEDGE_STORE_METADATA_JSON_COLUMN}::jsonb
                                #>> '{{jira_issue,assignee,account_id}}',
                            ''
                        ) != ''
                    )
                    OR (
                        v1_issue_with_target.source_updated_at IS NOT NULL
                        AND (
                            v2.updated_at < v1_issue_with_target.source_updated_at
                            OR (
                                v2.updated_at = v1_issue_with_target.source_updated_at
                                AND v2.content IS DISTINCT FROM v1_issue_with_target.content
                            )
                        )
                    )
                ) AS needs_backfill
            FROM v1_issue_with_target
            LEFT JOIN {KNOWLEDGE_STORE_TABLE_NAME} v2
              ON v2.{KNOWLEDGE_STORE_ID_COLUMN} = v1_issue_with_target.langchain_id
        )
        SELECT langchain_id, record_id, content, embedding
        FROM candidates
        WHERE scope_id = :scope_id
          AND target_id = :target_id
          AND needs_backfill
        ORDER BY target_id, record_id, langchain_id
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
            'jira',
            'issue',
            :record_id,
            'cloud',
            :scope_id,
            'project',
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


def build_fetch_pending_seed_chunk_query():
    return text(
        f"""
        SELECT
            {KNOWLEDGE_STORE_ID_COLUMN} AS langchain_id,
            record_id,
            {KNOWLEDGE_STORE_CONTENT_COLUMN} AS content,
            {KNOWLEDGE_STORE_EMBEDDING_COLUMN} AS embedding
        FROM {KNOWLEDGE_STORE_TABLE_NAME}
        WHERE source = 'jira'
          AND entity_type = 'issue'
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
            failed_at,
            failure_count,
            last_error_type,
            last_error_message,
            next_retry_at
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
            NULL
        )
        ON CONFLICT (connector, entity_type, scope_id, target_id) DO UPDATE SET
            state = 'processing',
            expected_count = EXCLUDED.expected_count,
            backfill_count = 0,
            failed_ids = '[]'::jsonb,
            succeeded_at = NULL,
            failed_at = NULL,
            failure_count = 0,
            last_error_type = NULL,
            last_error_message = NULL,
            next_retry_at = NULL
        WHERE vector_store_v2_backfill_states.state != 'processing'
        RETURNING id
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
            next_retry_at = :next_retry_at
        WHERE connector = :connector
          AND entity_type = :entity_type
          AND scope_id = :scope_id
          AND target_id = :target_id
        """
    )
