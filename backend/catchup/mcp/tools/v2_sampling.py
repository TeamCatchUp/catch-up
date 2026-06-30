from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import date
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from catchup.components.vector_db.v2.constants import KNOWLEDGE_STORE_ID_COLUMN
from catchup.components.vector_db.v2.constants import (
    KNOWLEDGE_STORE_METADATA_JSON_COLUMN,
)
from catchup.components.vector_db.v2.constants import KNOWLEDGE_STORE_TABLE_NAME
from catchup.db.engine import SessionLocal

ALLOWED_ENTITY_TYPES: dict[str, set[str]] = {
    "github": {"issue", "pr"},
    "slack": {"message"},
    "jira": {"issue", "epic"},
    "channel_talk": {"user_chat", "document_article"},
    "confluence": {"page", "blogpost"},
}
ALLOWED_SAMPLE_TYPES = {
    "latest",
    "random",
    "seed",
    "failed_backfill",
}
MAX_SAMPLE_LIMIT = 30
MAX_STATUS_LIMIT = 100
MAX_CONTENT_CHARS = 4000
DEFAULT_CONTENT_CHARS = 800
STATEMENT_TIMEOUT_MS = 5000

SessionFactory = Callable[[], AbstractContextManager[Session]]


@dataclass(slots=True, frozen=True)
class V2SamplingFilters:
    source: str
    entity_type: str
    sample_type: str = "latest"
    limit: int = 10
    content_chars: int = DEFAULT_CONTENT_CHARS


async def sample_v2_knowledge_rows(
    *,
    source: str,
    entity_type: str,
    sample_type: str = "latest",
    limit: int = 10,
    content_chars: int = DEFAULT_CONTENT_CHARS,
    session_factory: SessionFactory = SessionLocal,
) -> dict[str, Any]:
    filters = _normalize_sampling_filters(
        source=source,
        entity_type=entity_type,
        sample_type=sample_type,
        limit=limit,
        content_chars=content_chars,
    )
    return await asyncio.to_thread(
        _sample_v2_knowledge_rows_sync,
        filters,
        session_factory,
    )


async def get_v2_backfill_status(
    *,
    source: str | None = None,
    entity_type: str | None = None,
    limit: int = 50,
    session_factory: SessionFactory = SessionLocal,
) -> dict[str, Any]:
    normalized_source = _normalize_optional_source(source)
    normalized_entity_type = _normalize_optional_entity_type(
        normalized_source,
        entity_type,
    )
    normalized_limit = _bounded_int(limit, default=50, minimum=1, maximum=MAX_STATUS_LIMIT)
    return await asyncio.to_thread(
        _get_v2_backfill_status_sync,
        normalized_source,
        normalized_entity_type,
        normalized_limit,
        session_factory,
    )


def serialize_sampling_result(result: dict[str, Any]) -> str:
    return json.dumps(result, ensure_ascii=False, indent=2, default=_json_default)


def build_sample_v2_knowledge_rows_query(sample_type: str):
    if sample_type not in ALLOWED_SAMPLE_TYPES:
        raise ValueError(f"unsupported sample_type: {sample_type}")

    where_clauses = [
        "source = :source",
        "entity_type = :entity_type",
    ]
    if sample_type == "seed":
        where_clauses.append(
            f"COALESCE({KNOWLEDGE_STORE_METADATA_JSON_COLUMN}::jsonb, '{{}}'::jsonb)"
            " = '{}'::jsonb"
        )
    else:
        where_clauses.append(
            f"COALESCE({KNOWLEDGE_STORE_METADATA_JSON_COLUMN}::jsonb, '{{}}'::jsonb)"
            " != '{}'::jsonb"
        )

    if sample_type == "failed_backfill":
        where_clauses.append(
            """
            EXISTS (
                SELECT 1
                FROM vector_store_v2_backfill_states state
                CROSS JOIN LATERAL jsonb_array_elements_text(
                    COALESCE(state.failed_ids, '[]'::jsonb)
                ) failed(document_id)
                WHERE state.connector = :source
                  AND state.entity_type = :entity_type
                  AND state.state = 'failed'
                  AND failed.document_id = knowledge_store.document_id
            )
            """
        )

    order_by = "random()" if sample_type == "random" else "synced_at DESC, document_id ASC"
    where_sql = "\n          AND ".join(where_clauses)
    return text(
        f"""
        SELECT
            {KNOWLEDGE_STORE_ID_COLUMN} AS document_id,
            left(content, :content_chars) AS content_preview,
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
            left(body, :content_chars) AS body_preview,
            data,
            url,
            created_at,
            updated_at,
            synced_at,
            {KNOWLEDGE_STORE_METADATA_JSON_COLUMN} AS metadata
        FROM {KNOWLEDGE_STORE_TABLE_NAME}
        WHERE {where_sql}
        ORDER BY {order_by}
        LIMIT :limit
        """
    )


def build_v2_backfill_status_query(
    *,
    source: str | None,
    entity_type: str | None,
):
    where_clauses: list[str] = []
    if source is not None:
        where_clauses.append("connector = :source")
    if entity_type is not None:
        where_clauses.append("entity_type = :entity_type")

    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
    return text(
        f"""
        SELECT
            connector AS source,
            entity_type,
            scope_id,
            target_id,
            state,
            expected_count,
            backfill_count,
            jsonb_array_length(COALESCE(failed_ids, '[]'::jsonb)) AS failed_count,
            failed_ids,
            succeeded_at,
            failed_at,
            created_at
        FROM vector_store_v2_backfill_states
        {where_sql}
        ORDER BY
            CASE state
                WHEN 'failed' THEN 0
                WHEN 'processing' THEN 1
                WHEN 'pending' THEN 2
                ELSE 3
            END,
            COALESCE(failed_at, succeeded_at, created_at) DESC,
            connector,
            entity_type,
            scope_id,
            target_id
        LIMIT :limit
        """
    )


def _sample_v2_knowledge_rows_sync(
    filters: V2SamplingFilters,
    session_factory: SessionFactory,
) -> dict[str, Any]:
    params = {
        "source": filters.source,
        "entity_type": filters.entity_type,
        "limit": filters.limit,
        "content_chars": filters.content_chars,
    }
    with session_factory() as db:
        _apply_read_only_session_settings(db)
        rows = list(
            db.execute(
                build_sample_v2_knowledge_rows_query(filters.sample_type),
                params,
            ).mappings()
        )

    return {
        "source": filters.source,
        "entity_type": filters.entity_type,
        "sample_type": filters.sample_type,
        "limit": filters.limit,
        "content_chars": filters.content_chars,
        "rows": [_format_sample_row(dict(row)) for row in rows],
    }


def _get_v2_backfill_status_sync(
    source: str | None,
    entity_type: str | None,
    limit: int,
    session_factory: SessionFactory,
) -> dict[str, Any]:
    params: dict[str, Any] = {"limit": limit}
    if source is not None:
        params["source"] = source
    if entity_type is not None:
        params["entity_type"] = entity_type

    with session_factory() as db:
        _apply_read_only_session_settings(db)
        rows = list(
            db.execute(
                build_v2_backfill_status_query(
                    source=source,
                    entity_type=entity_type,
                ),
                params,
            ).mappings()
        )

    return {
        "source": source,
        "entity_type": entity_type,
        "limit": limit,
        "rows": [_json_safe_dict(dict(row)) for row in rows],
    }


def _apply_read_only_session_settings(db: Session) -> None:
    db.execute(text("SET TRANSACTION READ ONLY"))
    db.execute(text(f"SET LOCAL statement_timeout = {STATEMENT_TIMEOUT_MS}"))


def _normalize_sampling_filters(
    *,
    source: str,
    entity_type: str,
    sample_type: str,
    limit: int,
    content_chars: int,
) -> V2SamplingFilters:
    normalized_source = _normalize_source(source)
    normalized_entity_type = _normalize_entity_type(normalized_source, entity_type)
    normalized_sample_type = sample_type.strip().lower()
    if normalized_sample_type not in ALLOWED_SAMPLE_TYPES:
        raise ValueError(
            "sample_type must be one of: "
            + ", ".join(sorted(ALLOWED_SAMPLE_TYPES))
        )
    return V2SamplingFilters(
        source=normalized_source,
        entity_type=normalized_entity_type,
        sample_type=normalized_sample_type,
        limit=_bounded_int(limit, default=10, minimum=1, maximum=MAX_SAMPLE_LIMIT),
        content_chars=_bounded_int(
            content_chars,
            default=DEFAULT_CONTENT_CHARS,
            minimum=100,
            maximum=MAX_CONTENT_CHARS,
        ),
    )


def _normalize_optional_source(source: str | None) -> str | None:
    if source is None or source == "":
        return None
    return _normalize_source(source)


def _normalize_optional_entity_type(
    source: str | None,
    entity_type: str | None,
) -> str | None:
    if entity_type is None or entity_type == "":
        return None
    normalized = entity_type.strip().lower()
    if source is not None:
        return _normalize_entity_type(source, normalized)
    if not any(normalized in entity_types for entity_types in ALLOWED_ENTITY_TYPES.values()):
        raise ValueError(f"unsupported entity_type: {entity_type}")
    return normalized


def _normalize_source(source: str) -> str:
    normalized = source.strip().lower()
    if normalized not in ALLOWED_ENTITY_TYPES:
        raise ValueError(
            "source must be one of: " + ", ".join(sorted(ALLOWED_ENTITY_TYPES))
        )
    return normalized


def _normalize_entity_type(source: str, entity_type: str) -> str:
    normalized = entity_type.strip().lower()
    if normalized not in ALLOWED_ENTITY_TYPES[source]:
        allowed = ", ".join(sorted(ALLOWED_ENTITY_TYPES[source]))
        raise ValueError(f"entity_type for {source} must be one of: {allowed}")
    return normalized


def _bounded_int(
    value: int,
    *,
    default: int,
    minimum: int,
    maximum: int,
) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return min(max(number, minimum), maximum)


def _format_sample_row(row: dict[str, Any]) -> dict[str, Any]:
    data = row.get("data")
    metadata = row.get("metadata")
    return {
        **_json_safe_dict(row),
        "metadata_state": "seed" if metadata in ({}, None) else "hydrated",
        "data_part_types": _data_part_types(data),
    }


def _data_part_types(data: Any) -> list[str]:
    if not isinstance(data, dict):
        return []
    parts = data.get("parts")
    if not isinstance(parts, list):
        return []
    part_types = []
    for part in parts:
        if isinstance(part, dict) and isinstance(part.get("type"), str):
            part_types.append(part["type"])
    return part_types


def _json_safe_dict(row: dict[str, Any]) -> dict[str, Any]:
    return {key: _json_safe_value(value) for key, value in row.items()}


def _json_safe_value(value: Any) -> Any:
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, tuple):
        return [_json_safe_value(item) for item in value]
    if isinstance(value, list):
        return [_json_safe_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _json_safe_value(item) for key, item in value.items()}
    return value


def _json_default(value: Any) -> str:
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return str(value)


async def sample_v2_knowledge_store(
    source: str,
    entity_type: str,
    sample_type: str = "latest",
    limit: int = 10,
    content_chars: int = 800,
) -> str:
    """
    v2 knowledge_store row를 source/entity_type 단위로 샘플링합니다.

    Raw SQL은 허용하지 않고 allowlist 파라미터만 받습니다. embedding 컬럼은
    반환하지 않으며 content/body는 preview 길이로 제한됩니다.

    Args:
        source: github, slack, jira, channel_talk, confluence
        entity_type: source별 entity type
        sample_type: latest, random, seed, failed_backfill
        limit: 반환할 row 수. 최대 30.
        content_chars: content/body preview 길이. 최대 4000.
    """
    result = await sample_v2_knowledge_rows(
        source=source,
        entity_type=entity_type,
        sample_type=sample_type,
        limit=limit,
        content_chars=content_chars,
    )
    result["enabled"] = True
    return serialize_sampling_result(result)


async def get_v2_backfill_state(
    source: str | None = None,
    entity_type: str | None = None,
    limit: int = 50,
) -> str:
    """
    vector_store_v2_backfill_states 상태를 read-only로 조회합니다.

    Args:
        source: 선택 필터. github, slack, jira, channel_talk, confluence.
        entity_type: 선택 필터. source와 함께 주면 source별 allowlist 검증.
        limit: 반환할 state row 수. 최대 100.
    """
    result = await get_v2_backfill_status(
        source=source,
        entity_type=entity_type,
        limit=limit,
    )
    result["enabled"] = True
    return serialize_sampling_result(result)
