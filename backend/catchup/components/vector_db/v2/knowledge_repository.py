from __future__ import annotations

import asyncio
from collections.abc import Callable
from collections.abc import Sequence
from contextlib import AbstractContextManager

import structlog
from sqlalchemy import text
from sqlalchemy.orm import Session

from catchup.components.vector_db.v2.constants import KNOWLEDGE_STORE_ID_COLUMN
from catchup.components.vector_db.v2.constants import (
    KNOWLEDGE_STORE_METADATA_JSON_COLUMN,
)
from catchup.components.vector_db.v2.constants import KNOWLEDGE_STORE_TABLE_NAME
from catchup.db.engine import SessionLocal

logger = structlog.get_logger(__name__)


class V2KnowledgeRepository:
    """PostgreSQL operations that target the v2 knowledge_store table."""

    def __init__(
        self,
        *,
        table_name: str = KNOWLEDGE_STORE_TABLE_NAME,
        session_factory: Callable[[], AbstractContextManager[Session]] = SessionLocal,
    ) -> None:
        self._table_name = table_name
        self._session_factory = session_factory

    async def delete_multiple_chunks_by_id(
        self,
        *,
        source: str,
        entity_type: str,
        scope_id: str,
        target_id: str,
        record_id: str,
    ) -> int:
        """
        Incremnetal 경로의 삭제 이벤트가 있을 때 record에 대해서 여러 Chunk가 존재하는 경우 
        (source, entity_type, scope_id, target_id, record_id) 조합으로 모든 Chunk를 일괄 삭제
        """
        identity = {
            "source": source.strip(),
            "entity_type": entity_type.strip(),
            "scope_id": scope_id.strip(),
            "target_id": target_id.strip(),
            "record_id": record_id.strip(),
        }
        missing_fields = [field for field, value in identity.items() if not value]
        if missing_fields:
            raise ValueError(
                "chunk delete identity fields are required: "
                + ", ".join(missing_fields)
            )
        return await asyncio.to_thread(self._delete_multiple_chunks_by_id_sync, identity)

    async def find_missing_metadata_namespace_ids(
        self,
        ids: Sequence[str],
        *,
        namespace: str,
    ) -> tuple[str, ...]:
        """주어진 문서 ID 목록 중 Backfill이 필요한 대상을 식별

        1. knowledge_store 테이블에 행이 없는 경우
        2. knowledge_store.metadata JSONB 컬럼이 비어 있는 경우
        3. knowledge_store.metadata JSONB 컬럼에 지정된 namespace 키가 없는 경우

        Args:
            ids: 검사할 문서 ID 목록
            namespace: 메타데이터 존재 여부를 확인할 네임스페이스 키 (예: 'github')

        Returns:
            Backfill이 필요한 문서 ID 튜플

        Raises:
            ValueError: namespace가 빈 문자열이거나 공백만 있는 경우
        """
        document_ids = [str(document_id) for document_id in ids]
        if not document_ids:
            return ()
        if not namespace.strip():
            raise ValueError("metadata namespace is required")

        return await asyncio.to_thread(
            self._find_missing_metadata_namespace_ids_sync,
            document_ids,
            namespace,
        )

    def _find_missing_metadata_namespace_ids_sync(
        self,
        ids: list[str],
        namespace: str,
    ) -> tuple[str, ...]:

        params = {
            f"id_{index}": document_id for index, document_id in enumerate(ids)
        }
        placeholders = ", ".join(
            f"(CAST(:id_{index} AS varchar))" for index in range(len(ids))
        )
        statement = text(
            f"""
            WITH requested(document_id) AS (
                VALUES {placeholders}
            )
            SELECT requested.document_id
            FROM requested
            LEFT JOIN {self._table_name} store
              ON store.{KNOWLEDGE_STORE_ID_COLUMN} = requested.document_id
            WHERE store.{KNOWLEDGE_STORE_ID_COLUMN} IS NULL
               OR COALESCE(
                    store.{KNOWLEDGE_STORE_METADATA_JSON_COLUMN}::jsonb,
                    '{{}}'::jsonb
                  ) = '{{}}'::jsonb
               OR NOT jsonb_exists(
                    COALESCE(
                        store.{KNOWLEDGE_STORE_METADATA_JSON_COLUMN}::jsonb,
                        '{{}}'::jsonb
                    ),
                    :namespace
                  )
            """
        )
        try:
            with self._session_factory() as db:
                rows = db.execute(
                    statement,
                    {**params, "namespace": namespace},
                )
                return tuple(str(row[0]) for row in rows)
        except Exception as exc:
            logger.exception(
                "metadata_namespace_check_failed",
                table_name=self._table_name,
                id_count=len(ids),
                namespace=namespace,
                error=str(exc),
            )
            raise

    def _delete_multiple_chunks_by_id_sync(
        self,
        identity: dict[str, str],
    ) -> int:
        
        statement = text(
            f"""
            DELETE FROM {self._table_name}
            WHERE source = :source
              AND entity_type = :entity_type
              AND scope_id = :scope_id
              AND target_id = :target_id
              AND record_id = :record_id
            """
        )
        try:
            with self._session_factory() as db:
                result = db.execute(statement, identity)
                db.commit()
                return int(result.rowcount or 0)
        except Exception as exc:
            logger.exception(
                "delete_multiple_chunks_by_id_failed",
                table_name=self._table_name,
                **identity,
                error=str(exc),
            )
            raise

