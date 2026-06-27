from __future__ import annotations

from collections.abc import Awaitable
from collections.abc import Callable
from collections.abc import Sequence
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime
from datetime import timezone
from decimal import Decimal

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
from catchup.sync.ingestion.adapters.slack import SlackMessageV2BackfillAdapter
from catchup.sync.ingestion.adapters.slack import SlackMessageV2BackfillExecutionRequest
from catchup.sync.ingestion.adapters.slack import SlackMessageV2BackfillSeed
from catchup.sync.ingestion.factories.slack import (
    create_slack_message_v2_backfill_adapter,
)

SessionFactory = Callable[[], AbstractContextManager[Session]]
BackfillAdapterFactory = Callable[[str], Awaitable[SlackMessageV2BackfillAdapter]]

@dataclass(slots=True, frozen=True)
class SlackMessageV2Cursor:
    record_ts: Decimal
    langchain_id: str


class SlackMessageV2BackfillService(
    BaseBackfillService[
        SlackMessageV2BackfillAdapter,
        SlackMessageV2BackfillExecutionRequest,
        SlackMessageV2Cursor,
        None,
    ]
):
    connector = "slack"
    entity_type = "message"
    log_event_prefix = "slack_message_v2_backfill"

    def __init__(
        self,
        *,
        adapter_factory: BackfillAdapterFactory = create_slack_message_v2_backfill_adapter,
        session_factory: SessionFactory = SessionLocal,
        collection_name: str = settings.PGVECTOR_COLLECTION_NAME,
    ) -> None:
        super().__init__(
            adapter_factory=adapter_factory,
            session_factory=session_factory,
            collection_name=collection_name,
        )

    def _fetch_candidate_targets_sync(self, limit: int) -> list[BackfillTarget]:
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
                BackfillTarget(
                    scope_id=str(row["scope_id"]),
                    target_id=str(row["target_id"]),
                    expected_count=int(row["expected_count"]),
                    pending_count=int(row["pending_count"]),
                    target_name=str(row["target_name"]),
                )
                for row in rows
            ]

    def _fetch_candidate_seed_page_for_target_sync(
        self,
        target: BackfillTarget,
        cursor: SlackMessageV2Cursor | None,
        limit: int,
    ) -> list[BackfillSeed]:
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
                            "target_name": target.target_name,
                            "seeded_at": seeded_at,
                        }
                        for seed in batch
                    ],
                )
                affected += len(batch)
            db.commit()
        return affected

    def _cursor_from_last_seed(self, seed: BackfillSeed) -> SlackMessageV2Cursor:
        return SlackMessageV2Cursor(
            record_ts=Decimal(seed.record_id),
            langchain_id=seed.langchain_id,
        )

    def _cursor_log_context(
        self,
        cursor: SlackMessageV2Cursor | None,
    ) -> dict[str, object]:
        return {
            "after_record_ts": cursor.record_ts if cursor else None,
            "after_langchain_id": cursor.langchain_id if cursor else None,
        }

    def _build_execution_request(
        self,
        target: BackfillTarget,
        seeds: Sequence[BackfillSeed],
        target_context: None,
    ) -> SlackMessageV2BackfillExecutionRequest:
        del target_context
        return SlackMessageV2BackfillExecutionRequest(
            tenant_id=target.scope_id,
            channel_id=target.target_id,
            channel_name=target.target_name or target.target_id,
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
