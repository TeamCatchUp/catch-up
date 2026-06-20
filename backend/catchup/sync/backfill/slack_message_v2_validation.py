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


@dataclass(slots=True, frozen=True)
class SlackMessageV2CountValidation:
    v1_count: int
    v2_count: int
    missing_in_v2: int
    extra_in_v2: int

    @property
    def is_balanced(self) -> bool:
        return self.missing_in_v2 == 0 and self.extra_in_v2 == 0


@dataclass(slots=True, frozen=True)
class SlackMessageV2SampleValidation:
    langchain_id: str
    errors: tuple[str, ...]

    @property
    def is_valid(self) -> bool:
        return not self.errors


@dataclass(slots=True, frozen=True)
class SlackMessageV2ValidationReport:
    counts: SlackMessageV2CountValidation
    samples: tuple[SlackMessageV2SampleValidation, ...]

    @property
    def is_valid(self) -> bool:
        return self.counts.is_balanced and all(
            sample.is_valid for sample in self.samples
        )


class SlackMessageV2ValidationService:
    def __init__(
        self,
        *,
        session_factory: SessionFactory = SessionLocal,
        collection_name: str = settings.PGVECTOR_COLLECTION_NAME,
    ) -> None:
        self._session_factory = session_factory
        self._collection_name = collection_name

    async def validate(
        self, *, sample_limit: int = 20
    ) -> SlackMessageV2ValidationReport:
        return await asyncio.to_thread(self._validate_sync, sample_limit)

    def _validate_sync(self, sample_limit: int) -> SlackMessageV2ValidationReport:
        with self._session_factory() as db:
            count_row = (
                db.execute(
                    build_slack_message_v2_count_validation_query(),
                    {"collection_name": self._collection_name},
                )
                .mappings()
                .one()
            )
            sample_rows = db.execute(
                build_slack_message_v2_sample_query(),
                {"limit": sample_limit},
            ).mappings()
            sample_rows = list(sample_rows)

        counts = SlackMessageV2CountValidation(
            v1_count=int(count_row["v1_count"] or 0),
            v2_count=int(count_row["v2_count"] or 0),
            missing_in_v2=int(count_row["missing_in_v2"] or 0),
            extra_in_v2=int(count_row["extra_in_v2"] or 0),
        )
        samples = tuple(
            validate_slack_message_v2_sample_row(dict(row)) for row in sample_rows
        )
        return SlackMessageV2ValidationReport(counts=counts, samples=samples)


def build_slack_message_v2_count_validation_query():
    return text(
        f"""
        WITH v1_message AS (
            SELECT e.id AS langchain_id
            FROM langchain_pg_embedding e
            JOIN langchain_pg_collection c
              ON e.collection_id = c.uuid
            WHERE c.name = :collection_name
              AND e.cmetadata ->> 'source' = 'slack'
              AND e.cmetadata ->> 'entity_type' = 'message'
        ),
        v2_message AS (
            SELECT {KNOWLEDGE_STORE_ID_COLUMN} AS langchain_id
            FROM {KNOWLEDGE_STORE_TABLE_NAME}
            WHERE source = 'slack'
              AND entity_type = 'message'
              AND {_metadata_namespace_predicate("slack_message")}
        )
        SELECT
            (SELECT count(*) FROM v1_message) AS v1_count,
            (SELECT count(*) FROM v2_message) AS v2_count,
            (
                SELECT count(*)
                FROM v1_message
                LEFT JOIN v2_message USING (langchain_id)
                WHERE v2_message.langchain_id IS NULL
            ) AS missing_in_v2,
            (
                SELECT count(*)
                FROM v2_message
                LEFT JOIN v1_message USING (langchain_id)
                WHERE v1_message.langchain_id IS NULL
            ) AS extra_in_v2
        """
    )


def build_slack_message_v2_sample_query():
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
        WHERE source = 'slack'
          AND entity_type = 'message'
          AND {_metadata_namespace_predicate("slack_message")}
        ORDER BY synced_at DESC, langchain_id ASC
        LIMIT :limit
        """
    )


def validate_slack_message_v2_sample_row(
    row: dict[str, Any],
) -> SlackMessageV2SampleValidation:
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

    if langchain_id and not langchain_id.startswith("slack:message:"):
        errors.append("invalid:langchain_id_prefix")
    if row.get("source") != "slack":
        errors.append("invalid:source")
    if row.get("entity_type") != "message":
        errors.append("invalid:entity_type")
    if row.get("scope_type") != "workspace":
        errors.append("invalid:scope_type")
    if row.get("target_type") != "channel":
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
        if set(metadata) != {"slack_message"}:
            errors.append("invalid:metadata_namespace")
        slack_message = metadata.get("slack_message")
        if not isinstance(slack_message, dict):
            errors.append("missing:slack_message")
        else:
            _validate_slack_message_metadata(slack_message, errors)

    if isinstance(metadata, dict) and "contextual_content" in metadata:
        errors.append("forbidden:contextual_content")

    return SlackMessageV2SampleValidation(
        langchain_id=langchain_id,
        errors=tuple(errors),
    )


def _validate_slack_message_metadata(
    slack_message: dict[str, Any],
    errors: list[str],
) -> None:
    for field_name in ("team_id", "channel_id", "ts"):
        if slack_message.get(field_name) in (None, ""):
            errors.append(f"missing:slack_message.{field_name}")

    forbidden_fields = {
        "raw",
        "pagination",
        "contextual_content",
        "summary",
        "files",
        "attachments",
        "author_display",
        "author_name",
        "reply_user_ids",
        "reacted_user_ids",
        "mentioned_user_ids",
        "thread_ts",
        "is_thread_root",
        "reply_count",
        "latest_reply_ts",
        "channel_name",
    }
    for field_name in sorted(forbidden_fields & set(slack_message)):
        errors.append(f"forbidden:slack_message.{field_name}")


def _validate_data_parts(data: dict[str, Any], errors: list[str]) -> None:
    parts = data.get("parts")
    if not isinstance(parts, list):
        errors.append("missing:data.parts")
        return

    allowed_types = {
        "message_body",
        "thread_reply",
        "attachment",
        "file",
        "block_text",
    }
    for index, part in enumerate(parts):
        if not isinstance(part, dict):
            errors.append(f"invalid:data.parts[{index}]")
            continue
        part_type = part.get("type")
        if not part_type:
            errors.append(f"missing:data.parts[{index}].type")
        elif part_type not in allowed_types:
            errors.append(f"invalid:data.parts[{index}].type")
        if not part.get("text"):
            errors.append(f"missing:data.parts[{index}].text")
        if not isinstance(part.get("metadata"), dict):
            errors.append(f"missing:data.parts[{index}].metadata")
