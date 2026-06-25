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


def _metadata_namespace_predicate(namespace: str) -> str:
    metadata = f"COALESCE({KNOWLEDGE_STORE_METADATA_JSON_COLUMN}::jsonb, '{{}}'::jsonb)"
    return (
        f"{metadata} ? '{namespace}'\n"
        f"              AND {metadata} - '{namespace}' = '{{}}'::jsonb"
    )


ALLOWED_JIRA_PART_TYPES = frozenset(
    {
        "issue_description",
        "issue_comment",
        "linked_issue",
        "attachment",
        "inline_attachment",
    }
)


@dataclass(slots=True, frozen=True)
class JiraIssueV2CountValidation:
    v1_count: int
    v2_count: int
    missing_in_v2: int
    extra_in_v2: int

    @property
    def is_balanced(self) -> bool:
        return self.missing_in_v2 == 0 and self.extra_in_v2 == 0


@dataclass(slots=True, frozen=True)
class JiraIssueV2SampleValidation:
    langchain_id: str
    errors: tuple[str, ...]

    @property
    def is_valid(self) -> bool:
        return not self.errors


@dataclass(slots=True, frozen=True)
class JiraIssueV2ValidationReport:
    counts: JiraIssueV2CountValidation
    samples: tuple[JiraIssueV2SampleValidation, ...]

    @property
    def is_valid(self) -> bool:
        return self.counts.is_balanced and all(sample.is_valid for sample in self.samples)


class JiraIssueV2ValidationService:
    def __init__(
        self,
        *,
        session_factory: SessionFactory = SessionLocal,
        collection_name: str = settings.PGVECTOR_COLLECTION_NAME,
    ) -> None:
        self._session_factory = session_factory
        self._collection_name = collection_name

    async def validate(self, *, sample_limit: int = 20) -> JiraIssueV2ValidationReport:
        return await asyncio.to_thread(self._validate_sync, sample_limit)

    def _validate_sync(self, sample_limit: int) -> JiraIssueV2ValidationReport:
        with self._session_factory() as db:
            count_row = db.execute(
                build_jira_issue_v2_count_validation_query(),
                {"collection_name": self._collection_name},
            ).mappings().one()
            sample_rows = list(
                db.execute(
                    build_jira_issue_v2_sample_query(),
                    {"limit": sample_limit},
                ).mappings()
            )

        counts = JiraIssueV2CountValidation(
            v1_count=int(count_row["v1_count"] or 0),
            v2_count=int(count_row["v2_count"] or 0),
            missing_in_v2=int(count_row["missing_in_v2"] or 0),
            extra_in_v2=int(count_row["extra_in_v2"] or 0),
        )
        samples = tuple(validate_jira_issue_v2_sample_row(dict(row)) for row in sample_rows)
        return JiraIssueV2ValidationReport(counts=counts, samples=samples)


def _jira_issue_v1_id_cte() -> str:
    return """
        WITH v1_issue_source AS (
            SELECT
                e.id AS v1_langchain_id,
                e.cmetadata ->> 'entity_type' AS source_entity_type,
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
                NULLIF(e.cmetadata ->> 'url', '') AS issue_url
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
                        CASE source_entity_type WHEN 'issue' THEN 0 ELSE 1 END,
                        v1_langchain_id
                ) AS canonical_rank
            FROM single_project_candidates
        ),
        v1_issue AS (
            SELECT langchain_id
            FROM ranked_project_candidates
            WHERE canonical_rank = 1
        )
    """


def build_jira_issue_v2_count_validation_query():
    return text(
        f"""
        {_jira_issue_v1_id_cte()},
        v2_issue AS (
            SELECT {KNOWLEDGE_STORE_ID_COLUMN} AS langchain_id
            FROM {KNOWLEDGE_STORE_TABLE_NAME}
            WHERE source = 'jira'
              AND entity_type = 'issue'
              AND {_metadata_namespace_predicate("jira_issue")}
        )
        SELECT
            (SELECT count(*) FROM v1_issue) AS v1_count,
            (SELECT count(*) FROM v2_issue) AS v2_count,
            (
                SELECT count(*)
                FROM v1_issue
                LEFT JOIN v2_issue USING (langchain_id)
                WHERE v2_issue.langchain_id IS NULL
            ) AS missing_in_v2,
            (
                SELECT count(*)
                FROM v2_issue
                LEFT JOIN v1_issue USING (langchain_id)
                WHERE v1_issue.langchain_id IS NULL
            ) AS extra_in_v2
        """
    )


def build_jira_issue_v2_sample_query():
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
        WHERE source = 'jira'
          AND entity_type = 'issue'
          AND {_metadata_namespace_predicate("jira_issue")}
        ORDER BY synced_at DESC, langchain_id ASC
        LIMIT :limit
        """
    )


def build_jira_issue_v2_legacy_epic_shape_query():
    return text(
        f"""
        SELECT
            {KNOWLEDGE_STORE_ID_COLUMN} AS langchain_id,
            entity_type,
            {KNOWLEDGE_STORE_METADATA_JSON_COLUMN} AS langchain_metadata
        FROM {KNOWLEDGE_STORE_TABLE_NAME}
        WHERE source = 'jira'
          AND (
              entity_type = 'epic'
              OR {KNOWLEDGE_STORE_ID_COLUMN} LIKE 'jira:epic:%'
              OR COALESCE({KNOWLEDGE_STORE_METADATA_JSON_COLUMN}::jsonb, '{{}}'::jsonb)
                    ? 'jira_epic'
          )
        ORDER BY langchain_id ASC
        """
    )


def validate_jira_issue_v2_sample_row(row: dict[str, Any]) -> JiraIssueV2SampleValidation:
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

    if langchain_id and not langchain_id.startswith("jira:issue:"):
        errors.append("invalid:langchain_id_prefix")
    if row.get("source") != "jira":
        errors.append("invalid:source")
    if row.get("entity_type") != "issue":
        errors.append("invalid:entity_type")
    if row.get("scope_type") != "cloud":
        errors.append("invalid:scope_type")
    if row.get("target_type") != "project":
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
        if set(metadata) != {"jira_issue"}:
            errors.append("invalid:metadata_namespace")
        jira_issue = metadata.get("jira_issue")
        if not isinstance(jira_issue, dict):
            errors.append("missing:jira_issue")
        else:
            _validate_jira_issue_metadata(jira_issue, errors)

    if isinstance(metadata, dict) and "contextual_content" in metadata:
        errors.append("forbidden:contextual_content")

    return JiraIssueV2SampleValidation(
        langchain_id=langchain_id,
        errors=tuple(errors),
    )


def _validate_data_parts(data: dict[str, Any], errors: list[str]) -> None:
    parts = data.get("parts")
    if not isinstance(parts, list):
        errors.append("missing:data.parts")
        return
    for index, part in enumerate(parts):
        if not isinstance(part, dict):
            errors.append(f"invalid:data.parts[{index}]")
            continue
        part_type = part.get("type")
        if part_type not in ALLOWED_JIRA_PART_TYPES:
            errors.append(f"invalid:data.parts[{index}].type")
        if not part.get("text"):
            errors.append(f"missing:data.parts[{index}].text")


def _validate_jira_issue_metadata(
    jira_issue: dict[str, Any],
    errors: list[str],
) -> None:
    for field_name in ("issue_id", "type"):
        if not jira_issue.get(field_name):
            errors.append(f"missing:jira_issue.{field_name}")
    for forbidden_field in (
        "raw",
        "fields",
        "adf",
        "issue_type",
        "contextual_content",
        "custom_fields",
        "attachments",
        "issue_key",
        "project_key",
        "project_name",
        "comments_count",
        "attachments_count",
        "linked_issue_count",
    ):
        if forbidden_field in jira_issue:
            errors.append(f"forbidden:jira_issue.{forbidden_field}")
