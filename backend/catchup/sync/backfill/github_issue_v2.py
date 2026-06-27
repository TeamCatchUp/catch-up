from __future__ import annotations

from collections.abc import Awaitable
from collections.abc import Callable
from collections.abc import Sequence
from contextlib import AbstractContextManager
from dataclasses import dataclass
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
from catchup.sync.backfill.base import BackfillTarget
from catchup.sync.backfill.base import BaseBackfillService
from catchup.sync.backfill.base import chunked
from catchup.sync.backfill.base import embedding_to_list
from catchup.sync.backfill.base import format_pgvector_embedding
from catchup.sync.backfill.state import backfill_candidate_state_predicate
from catchup.sync.ingestion.adapters.github import GithubIssueV2BackfillAdapter
from catchup.sync.ingestion.adapters.github import GithubIssueV2BackfillExecutionRequest
from catchup.sync.ingestion.adapters.github import GithubIssueV2BackfillSeed
from catchup.sync.ingestion.factories.github import (
    create_github_issue_v2_backfill_adapter,
)

SessionFactory = Callable[[], AbstractContextManager[Session]]
BackfillAdapterFactory = Callable[[int], Awaitable[GithubIssueV2BackfillAdapter]]

@dataclass(slots=True, frozen=True)
class GithubIssueSeedCursor:
    record_number: int
    langchain_id: str


class GithubIssueV2BackfillService(
    BaseBackfillService[
        GithubIssueV2BackfillAdapter,
        GithubIssueV2BackfillExecutionRequest,
        GithubIssueSeedCursor,
        None,
    ]
):
    connector = "github"
    entity_type = "issue"
    log_event_prefix = "github_issue_v2_backfill"

    def __init__(
        self,
        *,
        adapter_factory: BackfillAdapterFactory = create_github_issue_v2_backfill_adapter,
        session_factory: SessionFactory = SessionLocal,
        collection_name: str = settings.PGVECTOR_COLLECTION_NAME,
    ) -> None:
        super().__init__(
            adapter_factory=adapter_factory,
            session_factory=session_factory,
            collection_name=collection_name,
        )

    async def _create_adapter_for_target(
        self,
        target: BackfillTarget,
    ) -> GithubIssueV2BackfillAdapter:
        return await self._adapter_factory(int(target.scope_id))

    def _fetch_candidate_targets_sync(self, limit: int) -> list[BackfillTarget]:
        query = build_github_issue_v1_target_query()
        with self._session_factory() as db:
            rows = db.execute(
                query,
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
                )
                for row in rows
            ]

    def _fetch_candidate_seed_page_for_target_sync(
        self,
        target: BackfillTarget,
        cursor: GithubIssueSeedCursor | None,
        limit: int,
    ) -> list[BackfillSeed]:
        query = build_github_issue_v1_target_seed_query()
        with self._session_factory() as db:
            rows = db.execute(
                query,
                {
                    "collection_name": self._collection_name,
                    "scope_id": target.scope_id,
                    "target_id": target.target_id,
                    "after_record_number": (cursor.record_number if cursor else None),
                    "after_langchain_id": cursor.langchain_id if cursor else None,
                    "limit": limit,
                },
            ).mappings()
            return [
                BackfillSeed(
                    langchain_id=row["langchain_id"],
                    record_id=row["record_id"],
                    content=row["content"],
                    embedding=embedding_to_list(row["embedding"]),
                )
                for row in rows
            ]

    def _upsert_seed_rows_sync(
        self,
        target: BackfillTarget,
        seeds: Sequence[BackfillSeed],
    ) -> int:
        if not seeds:
            return 0

        statement = build_upsert_seed_rows_statement()
        seeded_at = datetime.now(timezone.utc)
        affected = 0
        with self._session_factory() as db:
            for batch in chunked(seeds, SEED_INSERT_BATCH_SIZE):
                db.execute(
                    statement,
                    [
                        {
                            "langchain_id": seed.langchain_id,
                            "content": seed.content,
                            "embedding": format_pgvector_embedding(seed.embedding),
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

    def _cursor_from_last_seed(self, seed: BackfillSeed) -> GithubIssueSeedCursor:
        return GithubIssueSeedCursor(
            record_number=_record_id_to_int(seed.record_id),
            langchain_id=seed.langchain_id,
        )

    def _cursor_log_context(
        self,
        cursor: GithubIssueSeedCursor | None,
    ) -> dict[str, object]:
        return {
            "after_record_number": cursor.record_number if cursor else None,
            "after_langchain_id": cursor.langchain_id if cursor else None,
        }

    def _build_execution_request(
        self,
        target: BackfillTarget,
        seeds: Sequence[BackfillSeed],
        target_context: None,
    ) -> GithubIssueV2BackfillExecutionRequest:
        del target_context
        owner, repo = target.target_id.split("/", 1)
        return GithubIssueV2BackfillExecutionRequest(
            tenant_id=target.scope_id,
            owner=owner,
            repo=repo,
            seeds=tuple(
                GithubIssueV2BackfillSeed(
                    langchain_id=seed.langchain_id,
                    record_id=seed.record_id,
                    content=seed.content,
                    embedding=seed.embedding,
                )
                for seed in seeds
            ),
        )


def _record_id_to_int(record_id: str) -> int:
    return int(record_id)


def _github_issue_needs_backfill_expr() -> str:
    return f"""
                    (
                        COALESCE(v2.{KNOWLEDGE_STORE_METADATA_JSON_COLUMN}::jsonb, '{{}}'::jsonb) = '{{}}'::jsonb
                        OR v2.{KNOWLEDGE_STORE_ID_COLUMN} IS NULL
                    )
    """


def build_github_issue_v1_target_query():
    return text(
        f"""
        WITH v1_issue AS (
            SELECT
                e.id AS langchain_id,
                e.document AS content,
                e.cmetadata AS metadata,
                COALESCE(NULLIF(e.cmetadata ->> 'installation_id', ''), '') AS scope_id,
                COALESCE(
                    CASE
                        WHEN NULLIF(e.cmetadata ->> 'owner', '') IS NOT NULL
                         AND NULLIF(e.cmetadata ->> 'repo', '') IS NOT NULL
                        THEN (e.cmetadata ->> 'owner') || '/' || (e.cmetadata ->> 'repo')
                        ELSE substring(e.id from '^github:issue:([^:]+):')
                    END,
                    ''
                ) AS target_id
            FROM langchain_pg_embedding e
            JOIN langchain_pg_collection c
              ON e.collection_id = c.uuid
            WHERE c.name = :collection_name
              AND e.cmetadata ->> 'source' = 'github'
              AND e.cmetadata ->> 'entity_type' = 'issue'
              AND e.embedding IS NOT NULL
        ),
        candidates AS (
            SELECT
                v1_issue.scope_id,
                v1_issue.target_id,
                {_github_issue_needs_backfill_expr()} AS needs_backfill
            FROM v1_issue
            LEFT JOIN {KNOWLEDGE_STORE_TABLE_NAME} v2
              ON v2.{KNOWLEDGE_STORE_ID_COLUMN} = v1_issue.langchain_id
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
            grouped.expected_count,
            grouped.pending_count
        FROM grouped
        LEFT JOIN vector_store_v2_backfill_states state
          ON state.connector = 'github'
         AND state.entity_type = 'issue'
         AND state.scope_id = grouped.scope_id
         AND state.target_id = grouped.target_id
        WHERE grouped.pending_count > 0
        {backfill_candidate_state_predicate("state")}
        ORDER BY grouped.scope_id, grouped.target_id
        LIMIT :limit
        """
    )


def build_github_issue_v1_target_seed_query():
    return text(
        f"""
        WITH v1_issue AS (
            SELECT
                e.id AS langchain_id,
                e.document AS content,
                e.embedding AS embedding,
                COALESCE(
                    NULLIF(e.cmetadata ->> 'number', ''),
                    substring(e.id from ':([^:]+)$')
                ) AS record_id,
                COALESCE(NULLIF(e.cmetadata ->> 'installation_id', ''), '') AS scope_id,
                COALESCE(
                    CASE
                        WHEN NULLIF(e.cmetadata ->> 'owner', '') IS NOT NULL
                         AND NULLIF(e.cmetadata ->> 'repo', '') IS NOT NULL
                        THEN (e.cmetadata ->> 'owner') || '/' || (e.cmetadata ->> 'repo')
                        ELSE substring(e.id from '^github:issue:([^:]+):')
                    END,
                    ''
                ) AS target_id
            FROM langchain_pg_embedding e
            JOIN langchain_pg_collection c
              ON e.collection_id = c.uuid
            WHERE c.name = :collection_name
              AND e.cmetadata ->> 'source' = 'github'
              AND e.cmetadata ->> 'entity_type' = 'issue'
              AND e.embedding IS NOT NULL
        ),
        candidates AS (
            SELECT
                v1_issue.langchain_id,
                v1_issue.record_id,
                v1_issue.content,
                v1_issue.embedding,
                v1_issue.scope_id,
                v1_issue.target_id,
                {_github_issue_needs_backfill_expr()} AS needs_backfill
            FROM v1_issue
            LEFT JOIN {KNOWLEDGE_STORE_TABLE_NAME} v2
              ON v2.{KNOWLEDGE_STORE_ID_COLUMN} = v1_issue.langchain_id
        ),
        numbered_candidates AS (
            SELECT
                candidates.langchain_id,
                candidates.record_id,
                candidates.content,
                candidates.embedding,
                candidates.record_id::integer AS record_number
            FROM candidates
            WHERE candidates.scope_id = :scope_id
              AND candidates.target_id = :target_id
              AND candidates.needs_backfill
              AND candidates.record_id ~ '^[0-9]+$'
        )
        SELECT
            langchain_id,
            record_id,
            content,
            embedding
        FROM numbered_candidates
        WHERE (
              CAST(:after_record_number AS integer) IS NULL
              OR record_number > CAST(:after_record_number AS integer)
              OR (
                  record_number = CAST(:after_record_number AS integer)
                  AND langchain_id > COALESCE(CAST(:after_langchain_id AS text), '')
              )
          )
        ORDER BY record_number, langchain_id
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
            'github',
            'issue',
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
