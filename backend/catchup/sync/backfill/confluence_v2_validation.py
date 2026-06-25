from __future__ import annotations

import asyncio
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from catchup.components.vector_db.v2.constants import KNOWLEDGE_STORE_ID_COLUMN
from catchup.components.vector_db.v2.constants import (
    KNOWLEDGE_STORE_METADATA_JSON_COLUMN,
)
from catchup.components.vector_db.v2.constants import KNOWLEDGE_STORE_TABLE_NAME
from catchup.configs.config import settings
from catchup.db.engine import SessionLocal
from catchup.sync.backfill.confluence_v2 import _confluence_v1_cte
from catchup.sync.backfill.confluence_v2 import (
    _validate_confluence_backfill_entity_type,
)

SessionFactory = Callable[[], AbstractContextManager[Session]]


def _domain_metadata_key(entity_type: str) -> str:
    return "confluence_page" if entity_type == "page" else "confluence_blogpost"


def _metadata_namespace_predicate(namespace: str) -> str:
    metadata = f"COALESCE({KNOWLEDGE_STORE_METADATA_JSON_COLUMN}::jsonb, '{{}}'::jsonb)"
    return (
        f"{metadata} ? '{namespace}'\n"
        f"              AND {metadata} - '{namespace}' = '{{}}'::jsonb"
    )


@dataclass(slots=True, frozen=True)
class ConfluenceV2CountValidation:
    v1_count: int
    v2_count: int
    missing_in_v2: int
    extra_in_v2: int

    @property
    def is_balanced(self) -> bool:
        return self.missing_in_v2 == 0 and self.extra_in_v2 == 0


@dataclass(slots=True, frozen=True)
class ConfluenceV2SampleValidation:
    langchain_id: str
    errors: tuple[str, ...]

    @property
    def is_valid(self) -> bool:
        return not self.errors


@dataclass(slots=True, frozen=True)
class ConfluenceV2ValidationReport:
    counts: ConfluenceV2CountValidation
    samples: tuple[ConfluenceV2SampleValidation, ...]

    @property
    def is_valid(self) -> bool:
        return self.counts.is_balanced and all(sample.is_valid for sample in self.samples)


class ConfluenceV2ValidationService:
    def __init__(
        self,
        *,
        session_factory: SessionFactory = SessionLocal,
        collection_name: str = settings.PGVECTOR_COLLECTION_NAME,
        entity_type: str = "page",
    ) -> None:
        self._session_factory = session_factory
        self._collection_name = collection_name
        self._entity_type = _validate_confluence_backfill_entity_type(entity_type)

    async def validate(self, *, sample_limit: int = 20) -> ConfluenceV2ValidationReport:
        return await asyncio.to_thread(self._validate_sync, sample_limit)

    def _validate_sync(self, sample_limit: int) -> ConfluenceV2ValidationReport:
        with self._session_factory() as db:
            count_row = db.execute(
                build_confluence_v2_count_validation_query(self._entity_type),
                {"collection_name": self._collection_name},
            ).mappings().one()
            sample_rows = list(
                db.execute(
                    build_confluence_v2_sample_query(self._entity_type),
                    {"limit": sample_limit},
                ).mappings()
            )

        counts = ConfluenceV2CountValidation(
            v1_count=int(count_row["v1_count"] or 0),
            v2_count=int(count_row["v2_count"] or 0),
            missing_in_v2=int(count_row["missing_in_v2"] or 0),
            extra_in_v2=int(count_row["extra_in_v2"] or 0),
        )
        samples = tuple(
            validate_confluence_v2_sample_row(dict(row), entity_type=self._entity_type)
            for row in sample_rows
        )
        return ConfluenceV2ValidationReport(counts=counts, samples=samples)


class ConfluenceBlogpostV2ValidationService(ConfluenceV2ValidationService):
    def __init__(
        self,
        *,
        session_factory: SessionFactory = SessionLocal,
        collection_name: str = settings.PGVECTOR_COLLECTION_NAME,
    ) -> None:
        super().__init__(
            session_factory=session_factory,
            collection_name=collection_name,
            entity_type="blogpost",
        )


def build_confluence_v2_count_validation_query(entity_type: str = "page"):
    entity_type = _validate_confluence_backfill_entity_type(entity_type)
    domain_key = _domain_metadata_key(entity_type)
    return text(
        f"""
        {_confluence_v1_cte(entity_type)},
        v1_ids AS (
            SELECT langchain_id
            FROM v1_confluence
            WHERE COALESCE(scope_id, '') != ''
              AND COALESCE(target_id, '') != ''
              AND COALESCE(record_id, '') != ''
        ),
        v2_ids AS (
            SELECT {KNOWLEDGE_STORE_ID_COLUMN} AS langchain_id
            FROM {KNOWLEDGE_STORE_TABLE_NAME}
            WHERE source = 'confluence'
              AND entity_type = '{entity_type}'
              AND {_metadata_namespace_predicate(domain_key)}
        )
        SELECT
            (SELECT count(*) FROM v1_ids) AS v1_count,
            (SELECT count(*) FROM v2_ids) AS v2_count,
            (
                SELECT count(*)
                FROM v1_ids
                LEFT JOIN v2_ids USING (langchain_id)
                WHERE v2_ids.langchain_id IS NULL
            ) AS missing_in_v2,
            (
                SELECT count(*)
                FROM v2_ids
                LEFT JOIN v1_ids USING (langchain_id)
                WHERE v1_ids.langchain_id IS NULL
            ) AS extra_in_v2
        """
    )


def build_confluence_v2_sample_query(entity_type: str = "page"):
    entity_type = _validate_confluence_backfill_entity_type(entity_type)
    domain_key = _domain_metadata_key(entity_type)
    return text(
        f"""
        SELECT
            {KNOWLEDGE_STORE_ID_COLUMN} AS langchain_id,
            content,
            source,
            entity_type,
            record_id,
            scope_type,
            scope_id,
            target_type,
            target_id,
            target_name,
            title,
            body,
            data,
            url,
            created_at,
            updated_at,
            synced_at,
            {KNOWLEDGE_STORE_METADATA_JSON_COLUMN} AS langchain_metadata
        FROM {KNOWLEDGE_STORE_TABLE_NAME}
        WHERE source = 'confluence'
          AND entity_type = '{entity_type}'
          AND {_metadata_namespace_predicate(domain_key)}
        ORDER BY synced_at DESC, langchain_id ASC
        LIMIT :limit
        """
    )


def validate_confluence_v2_sample_row(
    row: dict[str, Any],
    *,
    entity_type: str = "page",
) -> ConfluenceV2SampleValidation:
    entity_type = _validate_confluence_backfill_entity_type(entity_type)
    domain_key = _domain_metadata_key(entity_type)
    errors: list[str] = []
    langchain_id = str(row.get("langchain_id") or "")

    for field_name in (
        "langchain_id",
        "content",
        "source",
        "entity_type",
        "record_id",
        "scope_type",
        "scope_id",
        "target_type",
        "target_id",
        "target_name",
        "title",
        "url",
        "created_at",
        "updated_at",
        "synced_at",
    ):
        if row.get(field_name) in (None, ""):
            errors.append(f"missing:{field_name}")
    if row.get("body") is None:
        errors.append("missing:body")

    if langchain_id and not langchain_id.startswith(f"confluence:{entity_type}:"):
        errors.append("invalid:langchain_id_prefix")
    if row.get("source") != "confluence":
        errors.append("invalid:source")
    if row.get("entity_type") != entity_type:
        errors.append("invalid:entity_type")
    if row.get("scope_type") != "cloud":
        errors.append("invalid:scope_type")
    if row.get("target_type") != "space":
        errors.append("invalid:target_type")

    _validate_data_parts(row.get("data"), errors)
    _validate_domain_metadata(row.get("langchain_metadata"), domain_key, errors)

    return ConfluenceV2SampleValidation(
        langchain_id=langchain_id,
        errors=tuple(errors),
    )


def _validate_data_parts(data: Any, errors: list[str]) -> None:
    if not isinstance(data, dict):
        errors.append("missing:data")
        return
    parts = data.get("parts")
    if not isinstance(parts, list):
        errors.append("missing:data.parts")
        return
    for index, part in enumerate(parts):
        if not isinstance(part, dict):
            errors.append(f"invalid:data.parts[{index}]")
            continue
        metadata = part.get("metadata")
        if not isinstance(metadata, dict):
            errors.append(f"missing:data.parts[{index}].metadata")
            continue
        for forbidden in ("record_id", "content_id", "page_id", "space_key", "space_name", "title"):
            if forbidden in metadata:
                errors.append(f"forbidden:data.parts[{index}].metadata.{forbidden}")


def _validate_domain_metadata(
    metadata: Any,
    domain_key: str,
    errors: list[str],
) -> None:
    if not isinstance(metadata, dict):
        errors.append("missing:langchain_metadata")
        return
    if set(metadata) != {domain_key}:
        errors.append("invalid:metadata_namespace")
        return
    domain_metadata = metadata.get(domain_key)
    if not isinstance(domain_metadata, dict):
        errors.append(f"missing:{domain_key}")
        return
    for forbidden in (
        "schema_version",
        "record_id",
        "content_id",
        "space_key",
        "space_name",
        "target_id",
        "target_name",
        "title",
        "raw_payload",
        "storage_html",
        "atlas_doc_format",
    ):
        if forbidden in domain_metadata:
            errors.append(f"forbidden:{domain_key}.{forbidden}")
