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
from catchup.connectors.channel_talk.credential_loader import (
    load_channel_talk_connection,
)
from catchup.connectors.channel_talk.credential_loader import (
    load_channel_talk_document_connection,
)
from catchup.connectors.channel_talk.full_sync_helper import (
    is_verified_channel_talk_document_connection,
)
from catchup.connectors.channel_talk.schemas.channel_connection import (
    ChannelTalkCredentialsRecord,
)
from catchup.connectors.channel_talk.schemas.document_connection import (
    ChannelTalkDocumentCredentialsRecord,
)
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
from catchup.sync.ingestion.adapters.channel_talk.article_models import (
    ChannelTalkArticleV2BackfillExecutionRequest,
)
from catchup.sync.ingestion.adapters.channel_talk.article_models import (
    ChannelTalkArticleV2BackfillSeed,
)
from catchup.sync.ingestion.adapters.channel_talk.article_v2_backfill import (
    ChannelTalkArticleV2BackfillAdapter,
)
from catchup.sync.ingestion.factories.channel_talk import (
    create_channel_talk_article_v2_backfill_adapter,
)
from catchup.sync.ingestion.vector_records.channel_talk_document_article import (
    CHANNEL_TALK_DOCUMENT_ARTICLE_V2_SCHEMA_VERSION,
)

SessionFactory = Callable[[], AbstractContextManager[Session]]
BackfillAdapterFactory = Callable[
    [str, str],
    Awaitable[ChannelTalkArticleV2BackfillAdapter],
]

@dataclass(slots=True, frozen=True)
class ChannelTalkArticleBackfillConnections:
    channel_connection: ChannelTalkCredentialsRecord
    document_connection: ChannelTalkDocumentCredentialsRecord


class ChannelTalkArticleV2BackfillService(
    BaseBackfillService[
        ChannelTalkArticleV2BackfillAdapter,
        ChannelTalkArticleV2BackfillExecutionRequest,
        BackfillSeedCursor,
        ChannelTalkArticleBackfillConnections,
    ]
):
    connector = "channel_talk"
    entity_type = "document_article"
    log_event_prefix = "channel_talk_document_article_v2_backfill"

    def __init__(
        self,
        *,
        adapter_factory: BackfillAdapterFactory = (
            create_channel_talk_article_v2_backfill_adapter
        ),
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
    ) -> ChannelTalkArticleV2BackfillAdapter:
        return await self._adapter_factory(target.scope_id, target.target_id)

    def _fetch_candidate_targets_sync(
        self,
        limit: int,
    ) -> list[BackfillTarget]:
        query = build_channel_talk_document_article_v1_target_query()
        with self._session_factory() as db:
            rows = db.execute(
                query,
                {"collection_name": self._collection_name, "limit": limit},
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
        cursor: BackfillSeedCursor | None,
        limit: int,
    ) -> list[BackfillSeed]:
        query = build_channel_talk_document_article_v1_target_seed_query()
        with self._session_factory() as db:
            rows = db.execute(
                query,
                {
                    "collection_name": self._collection_name,
                    "scope_id": target.scope_id,
                    "target_id": target.target_id,
                    "after_record_id": cursor.record_id if cursor else None,
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

    def _load_target_context_sync(
        self,
        target: BackfillTarget,
    ) -> ChannelTalkArticleBackfillConnections:
        channel_connection = load_channel_talk_connection(target.scope_id)
        if (
            channel_connection is None
            or channel_connection.channel_id != target.scope_id
        ):
            raise ValueError("channel_talk is not connected for the requested channel")

        document_connection = load_channel_talk_document_connection(
            target.scope_id,
            target.target_id,
        )
        if document_connection is None:
            raise ValueError("channel_talk documents credentials are missing")
        if not is_verified_channel_talk_document_connection(
            document_connection,
            channel_id=target.scope_id,
        ):
            raise ValueError(
                "channel_talk documents credentials are not API verified for the requested channel"
            )
        return ChannelTalkArticleBackfillConnections(
            channel_connection=channel_connection,
            document_connection=document_connection,
        )

    def _build_execution_request(
        self,
        target: BackfillTarget,
        seeds: Sequence[BackfillSeed],
        target_context: ChannelTalkArticleBackfillConnections,
    ) -> ChannelTalkArticleV2BackfillExecutionRequest:
        return ChannelTalkArticleV2BackfillExecutionRequest(
            tenant_id=target.scope_id,
            channel_connection=target_context.channel_connection,
            document_connection=target_context.document_connection,
            seeds=tuple(
                ChannelTalkArticleV2BackfillSeed(
                    langchain_id=seed.langchain_id,
                    record_id=seed.record_id,
                    content=seed.content,
                    embedding=seed.embedding,
                )
                for seed in seeds
            ),
        )


def _channel_talk_document_article_v1_cte() -> str:
    return f"""
        WITH v1_article AS (
            SELECT
                e.id AS langchain_id,
                e.document AS content,
                e.embedding AS embedding,
                COALESCE(
                    NULLIF(e.cmetadata ->> 'record_id', ''),
                    NULLIF(e.cmetadata #>> '{{document_article_core,article,article_id}}', ''),
                    substring(e.id from '^channel_talk:document_article:[^:]+:[^:]+:[^:]+:([^:]+):chunk:')
                ) AS record_id,
                COALESCE(
                    NULLIF(e.cmetadata #>> '{{document_article_core,space,channel_id}}', ''),
                    substring(e.id from '^channel_talk:document_article:([^:]+):')
                ) AS scope_id,
                COALESCE(
                    NULLIF(e.cmetadata #>> '{{document_article_core,space,space_id}}', ''),
                    substring(e.id from '^channel_talk:document_article:[^:]+:([^:]+):')
                ) AS target_id,
                COALESCE(
                    NULLIF(e.cmetadata #>> '{{document_article_core,space,space_name}}', ''),
                    NULLIF(e.cmetadata #>> '{{target_name}}', ''),
                    NULLIF(e.cmetadata #>> '{{document_article_core,space,space_id}}', ''),
                    substring(e.id from '^channel_talk:document_article:[^:]+:([^:]+):')
                ) AS target_name,
                COALESCE(
                    NULLIF(e.cmetadata ->> 'updated_at', '')::timestamptz,
                    NULLIF(e.cmetadata #>> '{{document_article_core,publication,updated_at}}', '')::timestamptz
                ) AS source_updated_at
            FROM langchain_pg_embedding e
            JOIN langchain_pg_collection c
              ON e.collection_id = c.uuid
            WHERE c.name = :collection_name
              AND e.cmetadata ->> 'source' = 'channel_talk'
              AND e.cmetadata ->> 'entity_type' = 'document_article'
        )
    """


def _channel_talk_document_article_needs_backfill_expr() -> str:
    return f"""
                    (
                        COALESCE(v2.{KNOWLEDGE_STORE_METADATA_JSON_COLUMN}::jsonb, '{{}}'::jsonb) = '{{}}'::jsonb
                        OR v2.{KNOWLEDGE_STORE_ID_COLUMN} IS NULL
                        OR COALESCE(
                            v2.{KNOWLEDGE_STORE_METADATA_JSON_COLUMN}::jsonb
                            #>> '{{channel_talk_document_article,schema_version}}',
                            ''
                        ) != '{CHANNEL_TALK_DOCUMENT_ARTICLE_V2_SCHEMA_VERSION}'
                        OR (
                            v1_article.source_updated_at IS NOT NULL
                            AND (
                                v2.updated_at < v1_article.source_updated_at
                                OR (
                                    v2.updated_at = v1_article.source_updated_at
                                    AND v2.content IS DISTINCT FROM v1_article.content
                                )
                            )
                        )
                    )
    """


def build_channel_talk_document_article_v1_target_query():
    return text(
        f"""
        {_channel_talk_document_article_v1_cte()},
        candidates AS (
            SELECT
                v1_article.scope_id,
                v1_article.target_id,
                v1_article.target_name,
                {_channel_talk_document_article_needs_backfill_expr()} AS needs_backfill
            FROM v1_article
            LEFT JOIN {KNOWLEDGE_STORE_TABLE_NAME} v2
              ON v2.{KNOWLEDGE_STORE_ID_COLUMN} = v1_article.langchain_id
        ),
        grouped AS (
            SELECT
                scope_id,
                target_id,
                COALESCE(MAX(NULLIF(target_name, '')), target_id) AS target_name,
                count(*) AS expected_count,
                count(*) FILTER (WHERE needs_backfill) AS pending_count
            FROM candidates
            GROUP BY scope_id, target_id
        )
        SELECT
            grouped.scope_id,
            grouped.target_id,
            grouped.target_name,
            grouped.expected_count,
            grouped.pending_count
        FROM grouped
        LEFT JOIN vector_store_v2_backfill_states state
          ON state.connector = 'channel_talk'
         AND state.entity_type = 'document_article'
         AND state.scope_id = grouped.scope_id
         AND state.target_id = grouped.target_id
        WHERE grouped.pending_count > 0
        {backfill_candidate_state_predicate("state")}
        ORDER BY grouped.scope_id, grouped.target_id
        LIMIT :limit
        """
    )


def build_channel_talk_document_article_v1_target_seed_query():
    return text(
        f"""
        {_channel_talk_document_article_v1_cte()},
        candidates AS (
            SELECT
                v1_article.langchain_id,
                v1_article.record_id,
                v1_article.content,
                v1_article.embedding,
                v1_article.scope_id,
                v1_article.target_id,
                {_channel_talk_document_article_needs_backfill_expr()} AS needs_backfill
            FROM v1_article
            LEFT JOIN {KNOWLEDGE_STORE_TABLE_NAME} v2
              ON v2.{KNOWLEDGE_STORE_ID_COLUMN} = v1_article.langchain_id
        )
        SELECT langchain_id, record_id, content, embedding
        FROM candidates
        WHERE scope_id = :scope_id
          AND target_id = :target_id
          AND needs_backfill
          AND (
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
            'document_article',
            :record_id,
            'channel',
            :scope_id,
            'document_space',
            :target_id,
            :target_name,
            NULL,
            '',
            '',
            jsonb_build_object('parts', '[]'::jsonb),
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
