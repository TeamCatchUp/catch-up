from __future__ import annotations

from collections.abc import Awaitable
from collections.abc import Callable
from collections.abc import Sequence
from contextlib import AbstractContextManager
from datetime import datetime
from datetime import timezone

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
from catchup.sync.backfill.base import SEED_INSERT_BATCH_SIZE
from catchup.sync.backfill.base import BackfillSeed
from catchup.sync.backfill.base import BackfillSeedCursor
from catchup.sync.backfill.base import BackfillTarget
from catchup.sync.backfill.base import BaseBackfillService
from catchup.sync.backfill.base import chunked
from catchup.sync.backfill.base import embedding_to_list
from catchup.sync.backfill.base import format_pgvector_embedding
from catchup.sync.backfill.state import backfill_candidate_state_predicate
from catchup.sync.ingestion.adapters.jira import JiraIssueV2BackfillAdapter
from catchup.sync.ingestion.adapters.jira import JiraIssueV2BackfillExecutionRequest
from catchup.sync.ingestion.adapters.jira import JiraIssueV2BackfillSeed
from catchup.sync.ingestion.adapters.jira import create_jira_issue_v2_backfill_adapter

SessionFactory = Callable[[], AbstractContextManager[Session]]
BackfillAdapterFactory = Callable[[str], Awaitable[JiraIssueV2BackfillAdapter]]

class JiraIssueV2BackfillService(
    BaseBackfillService[
        JiraIssueV2BackfillAdapter,
        JiraIssueV2BackfillExecutionRequest,
        BackfillSeedCursor,
        None,
    ]
):
    connector = "jira"
    entity_type = "issue"
    target_failure_event_suffix = "target_failed"
    log_event_prefix = "jira_issue_v2_backfill"

    def __init__(
        self,
        *,
        adapter_factory: BackfillAdapterFactory = create_jira_issue_v2_backfill_adapter,
        session_factory: SessionFactory = SessionLocal,
        collection_name: str = settings.PGVECTOR_COLLECTION_NAME,
    ) -> None:
        super().__init__(
            adapter_factory=adapter_factory,
            session_factory=session_factory,
            collection_name=collection_name,
        )

    def _fetch_candidate_targets_sync(self, limit: int) -> list[BackfillTarget]:
        with self._session_factory() as db:
            rows = db.execute(
                build_jira_v1_target_query(),
                {
                    "collection_name": self._collection_name,
                    "limit": limit,
                },
            ).mappings()
            return [
                BackfillTarget(
                    scope_id=str(row["scope_id"]),
                    target_id=str(row["target_id"]),
                    expected_count=int(row["expected_count"]),
                    pending_count=int(row["pending_count"]),
                    target_name=str(row["target_name"]),
                )
                for row in rows
                if row["scope_id"] and row["target_id"]
            ]

    def _fetch_candidate_seed_page_for_target_sync(
        self,
        target: BackfillTarget,
        cursor: BackfillSeedCursor | None,
        limit: int,
    ) -> list[BackfillSeed]:
        with self._session_factory() as db:
            rows = db.execute(
                build_jira_v1_target_seed_query(),
                {
                    "collection_name": self._collection_name,
                    "scope_id": target.scope_id,
                    "target_id": target.target_id,
                    "after_record_id": cursor.record_id if cursor else None,
                    "after_langchain_id": cursor.langchain_id if cursor else None,
                    "limit": limit,
                },
            ).mappings()
            seeds: list[BackfillSeed] = []
            for row in rows:
                embedding = embedding_to_list(row["embedding"])
                if not embedding:
                    continue
                seeds.append(
                    BackfillSeed(
                        langchain_id=str(row["langchain_id"]),
                        record_id=str(row["record_id"]),
                        content=str(row["content"] or ""),
                        embedding=embedding,
                    )
                )
            return seeds

    def _upsert_seed_rows_sync(
        self,
        target: BackfillTarget,
        seeds: Sequence[BackfillSeed],
    ) -> int:
        if not seeds:
            return 0
        now = datetime.now(timezone.utc)
        with self._session_factory() as db:
            for seed_batch in chunked(seeds, SEED_INSERT_BATCH_SIZE):
                db.execute(
                    build_upsert_seed_rows_statement(),
                    [
                        {
                            "langchain_id": seed.langchain_id,
                            "content": seed.content,
                            "embedding": format_pgvector_embedding(seed.embedding),
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

    def _build_execution_request(
        self,
        target: BackfillTarget,
        seeds: Sequence[BackfillSeed],
        target_context: None,
    ) -> JiraIssueV2BackfillExecutionRequest:
        del target_context
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
                    substring(e.id from '^jira:[^:]+:(.+)$')
                ) AS record_id,
                COALESCE(
                    NULLIF(e.cmetadata ->> 'project_key', ''),
                    split_part(
                    COALESCE(
                        NULLIF(e.cmetadata ->> 'issue_key', ''),
                        NULLIF(e.cmetadata ->> 'record_id', ''),
                        substring(e.id from '^jira:[^:]+:(.+)$')
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


def _jira_issue_needs_backfill_expr() -> str:
    return f"""
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
                    )
    """


def build_jira_v1_target_query():
    return text(
        f"""
        {_jira_issue_v1_cte()},
        candidates AS (
            SELECT
                v1_issue_with_target.scope_id,
                v1_issue_with_target.target_id,
                v1_issue_with_target.target_name,
                {_jira_issue_needs_backfill_expr()} AS needs_backfill
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
            grouped.expected_count,
            grouped.pending_count
        FROM grouped
        LEFT JOIN vector_store_v2_backfill_states state
          ON state.connector = 'jira'
         AND state.entity_type = 'issue'
         AND state.scope_id = grouped.scope_id
         AND state.target_id = grouped.target_id
        WHERE grouped.pending_count > 0
        {backfill_candidate_state_predicate("state")}
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
                {_jira_issue_needs_backfill_expr()} AS needs_backfill
            FROM v1_issue_with_target
            LEFT JOIN {KNOWLEDGE_STORE_TABLE_NAME} v2
              ON v2.{KNOWLEDGE_STORE_ID_COLUMN} = v1_issue_with_target.langchain_id
        )
        SELECT langchain_id, record_id, content, embedding
        FROM candidates
        WHERE scope_id = :scope_id
          AND target_id = :target_id
          AND needs_backfill
          AND embedding IS NOT NULL
          AND (
              CAST(:after_record_id AS text) IS NULL
              OR record_id > CAST(:after_record_id AS text)
              OR (
                  record_id = CAST(:after_record_id AS text)
                  AND langchain_id > COALESCE(CAST(:after_langchain_id AS text), '')
              )
          )
        ORDER BY record_id, langchain_id
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
