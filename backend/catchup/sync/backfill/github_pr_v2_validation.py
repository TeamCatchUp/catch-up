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

SessionFactory = Callable[[], AbstractContextManager[Session]]


@dataclass(slots=True, frozen=True)
class GithubPrV2CountValidation:
    v1_count: int
    v2_count: int
    missing_in_v2: int
    extra_in_v2: int

    @property
    def is_balanced(self) -> bool:
        return self.missing_in_v2 == 0 and self.extra_in_v2 == 0


@dataclass(slots=True, frozen=True)
class GithubPrV2SampleValidation:
    langchain_id: str
    errors: tuple[str, ...]

    @property
    def is_valid(self) -> bool:
        return not self.errors


@dataclass(slots=True, frozen=True)
class GithubPrV2ValidationReport:
    counts: GithubPrV2CountValidation
    samples: tuple[GithubPrV2SampleValidation, ...]

    @property
    def is_valid(self) -> bool:
        return self.counts.is_balanced and all(sample.is_valid for sample in self.samples)


class GithubPrV2ValidationService:
    def __init__(
        self,
        *,
        session_factory: SessionFactory = SessionLocal,
        collection_name: str = settings.PGVECTOR_COLLECTION_NAME,
    ) -> None:
        self._session_factory = session_factory
        self._collection_name = collection_name

    async def validate(self, *, sample_limit: int = 20) -> GithubPrV2ValidationReport:
        return await asyncio.to_thread(self._validate_sync, sample_limit)

    def _validate_sync(self, sample_limit: int) -> GithubPrV2ValidationReport:
        with self._session_factory() as db:
            count_row = db.execute(
                build_github_pr_v2_count_validation_query(),
                {"collection_name": self._collection_name},
            ).mappings().one()
            sample_rows = db.execute(
                build_github_pr_v2_sample_query(),
                {"limit": sample_limit},
            ).mappings()
            sample_rows = list(sample_rows)

        counts = GithubPrV2CountValidation(
            v1_count=int(count_row["v1_count"] or 0),
            v2_count=int(count_row["v2_count"] or 0),
            missing_in_v2=int(count_row["missing_in_v2"] or 0),
            extra_in_v2=int(count_row["extra_in_v2"] or 0),
        )
        samples = tuple(validate_github_pr_v2_sample_row(dict(row)) for row in sample_rows)
        return GithubPrV2ValidationReport(counts=counts, samples=samples)


def build_github_pr_v2_count_validation_query():
    return text(
        f"""
        WITH v1_pr AS (
            SELECT e.id AS langchain_id
            FROM langchain_pg_embedding e
            JOIN langchain_pg_collection c
              ON e.collection_id = c.uuid
            WHERE c.name = :collection_name
              AND e.cmetadata ->> 'source' = 'github'
              AND e.cmetadata ->> 'entity_type' = 'pr'
        ),
        v2_pr AS (
            SELECT {KNOWLEDGE_STORE_ID_COLUMN} AS langchain_id
            FROM {KNOWLEDGE_STORE_TABLE_NAME}
            WHERE source = 'github'
              AND entity_type = 'pr'
              AND COALESCE({KNOWLEDGE_STORE_METADATA_JSON_COLUMN}, '{{}}'::jsonb) != '{{}}'::jsonb
        )
        SELECT
            (SELECT count(*) FROM v1_pr) AS v1_count,
            (SELECT count(*) FROM v2_pr) AS v2_count,
            (
                SELECT count(*)
                FROM v1_pr
                LEFT JOIN v2_pr USING (langchain_id)
                WHERE v2_pr.langchain_id IS NULL
            ) AS missing_in_v2,
            (
                SELECT count(*)
                FROM v2_pr
                LEFT JOIN v1_pr USING (langchain_id)
                WHERE v1_pr.langchain_id IS NULL
            ) AS extra_in_v2
        """
    )


def build_github_pr_v2_sample_query():
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
            {KNOWLEDGE_STORE_METADATA_JSON_COLUMN}
              AS langchain_metadata
        FROM {KNOWLEDGE_STORE_TABLE_NAME}
        WHERE source = 'github'
          AND entity_type = 'pr'
          AND COALESCE({KNOWLEDGE_STORE_METADATA_JSON_COLUMN}, '{{}}'::jsonb) != '{{}}'::jsonb
        ORDER BY synced_at DESC, langchain_id ASC
        LIMIT :limit
        """
    )


def validate_github_pr_v2_sample_row(row: dict[str, Any]) -> GithubPrV2SampleValidation:
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
        "body",
        "url",
        "created_at",
        "updated_at",
        "synced_at",
    ):
        if row.get(field_name) in (None, ""):
            errors.append(f"missing:{field_name}")

    if langchain_id and not langchain_id.startswith("github:pr:"):
        errors.append("invalid:langchain_id_prefix")
    if row.get("source") != "github":
        errors.append("invalid:source")
    if row.get("entity_type") != "pr":
        errors.append("invalid:entity_type")
    if row.get("scope_type") != "installation":
        errors.append("invalid:scope_type")
    if row.get("target_type") != "repository":
        errors.append("invalid:target_type")

    data = row.get("data")
    if not isinstance(data, dict):
        errors.append("missing:data")
    else:
        _validate_data_parts(data, errors)

    metadata = row.get("langchain_metadata")
    if not isinstance(metadata, dict):
        errors.append("missing:langchain_metadata")
    else:
        if set(metadata) != {"github_pr"}:
            errors.append("invalid:metadata_namespace")
        github_pr = metadata.get("github_pr")
        if not isinstance(github_pr, dict):
            errors.append("missing:github_pr")
        else:
            if "contextual_content" in github_pr:
                errors.append("forbidden:github_pr.contextual_content")
            _validate_github_pr_metadata(github_pr, errors)

    if isinstance(metadata, dict) and "contextual_content" in metadata:
        errors.append("forbidden:contextual_content")

    return GithubPrV2SampleValidation(
        langchain_id=langchain_id,
        errors=tuple(errors),
    )


def _validate_github_pr_metadata(
    github_pr: dict[str, Any],
    errors: list[str],
) -> None:
    for field_name in (
        "state",
        "base_ref",
        "head_ref",
        "changed_files",
    ):
        if github_pr.get(field_name) is None:
            errors.append(f"missing:github_pr.{field_name}")

    for field_name in ("changed_files",):
        if not isinstance(github_pr.get(field_name), int):
            errors.append(f"invalid:github_pr.{field_name}")

    forbidden_fields = {
        "merged",
        "counts",
        "commits_count",
        "comments_count",
        "commit_shas",
        "raw",
        "pagination",
        "body_text_anchor",
        "author_display",
        "assignee_displays",
        "reviewer_displays",
        "merged_by_display",
        "review_state",
    }
    for field_name in sorted(forbidden_fields & set(github_pr)):
        errors.append(f"forbidden:github_pr.{field_name}")


def _validate_data_parts(data: dict[str, Any], errors: list[str]) -> None:
    parts = data.get("parts")
    if not isinstance(parts, list):
        errors.append("missing:data.parts")
        return

    for index, part in enumerate(parts):
        if not isinstance(part, dict):
            errors.append(f"invalid:data.parts[{index}]")
            continue
        if not part.get("type"):
            errors.append(f"missing:data.parts[{index}].type")
        if not part.get("text"):
            errors.append(f"missing:data.parts[{index}].text")
        if not isinstance(part.get("metadata"), dict):
            errors.append(f"missing:data.parts[{index}].metadata")
