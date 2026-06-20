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
from catchup.sync.backfill.channel_talk_document_article_v2 import (
    _channel_talk_document_article_v1_cte,
)
from catchup.sync.backfill.channel_talk_user_chat_v2 import (
    _channel_talk_user_chat_v1_cte,
)
from catchup.sync.ingestion.vector_records.channel_talk_document_article import (
    CHANNEL_TALK_DOCUMENT_ARTICLE_V2_SCHEMA_VERSION,
)

SessionFactory = Callable[[], AbstractContextManager[Session]]


def _metadata_namespace_predicate(namespace: str) -> str:
    metadata = f"COALESCE({KNOWLEDGE_STORE_METADATA_JSON_COLUMN}::jsonb, '{{}}'::jsonb)"
    return (
        f"{metadata} ? '{namespace}'\n"
        f"              AND {metadata} - '{namespace}' = '{{}}'::jsonb"
    )


@dataclass(slots=True, frozen=True)
class ChannelTalkV2CountValidation:
    v1_count: int
    v2_count: int
    missing_in_v2: int
    extra_in_v2: int

    @property
    def is_balanced(self) -> bool:
        return self.missing_in_v2 == 0 and self.extra_in_v2 == 0


@dataclass(slots=True, frozen=True)
class ChannelTalkV2SampleValidation:
    langchain_id: str
    errors: tuple[str, ...]

    @property
    def is_valid(self) -> bool:
        return not self.errors


@dataclass(slots=True, frozen=True)
class ChannelTalkV2ValidationReport:
    counts: ChannelTalkV2CountValidation
    samples: tuple[ChannelTalkV2SampleValidation, ...]

    @property
    def is_valid(self) -> bool:
        return self.counts.is_balanced and all(sample.is_valid for sample in self.samples)


class ChannelTalkUserChatV2ValidationService:
    def __init__(
        self,
        *,
        session_factory: SessionFactory = SessionLocal,
        collection_name: str = settings.PGVECTOR_COLLECTION_NAME,
    ) -> None:
        self._session_factory = session_factory
        self._collection_name = collection_name

    async def validate(self, *, sample_limit: int = 20) -> ChannelTalkV2ValidationReport:
        return await asyncio.to_thread(self._validate_sync, sample_limit)

    def _validate_sync(self, sample_limit: int) -> ChannelTalkV2ValidationReport:
        with self._session_factory() as db:
            count_row = db.execute(
                build_channel_talk_user_chat_v2_count_validation_query(),
                {"collection_name": self._collection_name},
            ).mappings().one()
            sample_rows = list(
                db.execute(
                    build_channel_talk_user_chat_v2_sample_query(),
                    {"limit": sample_limit},
                ).mappings()
            )

        counts = _count_validation_from_row(dict(count_row))
        samples = tuple(
            validate_channel_talk_user_chat_v2_sample_row(dict(row))
            for row in sample_rows
        )
        return ChannelTalkV2ValidationReport(counts=counts, samples=samples)


class ChannelTalkArticleV2ValidationService:
    def __init__(
        self,
        *,
        session_factory: SessionFactory = SessionLocal,
        collection_name: str = settings.PGVECTOR_COLLECTION_NAME,
    ) -> None:
        self._session_factory = session_factory
        self._collection_name = collection_name

    async def validate(self, *, sample_limit: int = 20) -> ChannelTalkV2ValidationReport:
        return await asyncio.to_thread(self._validate_sync, sample_limit)

    def _validate_sync(self, sample_limit: int) -> ChannelTalkV2ValidationReport:
        with self._session_factory() as db:
            count_row = db.execute(
                build_channel_talk_document_article_v2_count_validation_query(),
                {"collection_name": self._collection_name},
            ).mappings().one()
            sample_rows = list(
                db.execute(
                    build_channel_talk_document_article_v2_sample_query(),
                    {"limit": sample_limit},
                ).mappings()
            )

        counts = _count_validation_from_row(dict(count_row))
        samples = tuple(
            validate_channel_talk_document_article_v2_sample_row(dict(row))
            for row in sample_rows
        )
        return ChannelTalkV2ValidationReport(counts=counts, samples=samples)


def build_channel_talk_user_chat_v2_count_validation_query():
    return text(
        f"""
        {_channel_talk_user_chat_v1_cte()},
        v1_ids AS (
            SELECT langchain_id
            FROM v1_user_chat
            WHERE COALESCE(scope_id, '') != ''
              AND COALESCE(target_id, '') != ''
              AND COALESCE(record_id, '') != ''
        ),
        v2_ids AS (
            SELECT {KNOWLEDGE_STORE_ID_COLUMN} AS langchain_id
            FROM {KNOWLEDGE_STORE_TABLE_NAME}
            WHERE source = 'channel_talk'
              AND entity_type = 'user_chat'
              AND {_metadata_namespace_predicate("channel_talk_user_chat")}
        )
        {_count_validation_select_sql()}
        """
    )


def build_channel_talk_document_article_v2_count_validation_query():
    return text(
        f"""
        {_channel_talk_document_article_v1_cte()},
        v1_ids AS (
            SELECT langchain_id
            FROM v1_article
            WHERE COALESCE(scope_id, '') != ''
              AND COALESCE(target_id, '') != ''
              AND COALESCE(record_id, '') != ''
        ),
        v2_ids AS (
            SELECT {KNOWLEDGE_STORE_ID_COLUMN} AS langchain_id
            FROM {KNOWLEDGE_STORE_TABLE_NAME}
            WHERE source = 'channel_talk'
              AND entity_type = 'document_article'
              AND {_metadata_namespace_predicate("channel_talk_document_article")}
              AND COALESCE(
                    {KNOWLEDGE_STORE_METADATA_JSON_COLUMN}::jsonb
                    #>> '{{channel_talk_document_article,schema_version}}',
                    ''
                  ) = '{CHANNEL_TALK_DOCUMENT_ARTICLE_V2_SCHEMA_VERSION}'
        )
        {_count_validation_select_sql()}
        """
    )


def build_channel_talk_user_chat_v2_sample_query():
    return _sample_query(
        entity_type="user_chat",
        namespace="channel_talk_user_chat",
        extra_predicate="",
    )


def build_channel_talk_document_article_v2_sample_query():
    return _sample_query(
        entity_type="document_article",
        namespace="channel_talk_document_article",
        extra_predicate=(
            "AND COALESCE("
            f"{KNOWLEDGE_STORE_METADATA_JSON_COLUMN}::jsonb "
            "#>> '{channel_talk_document_article,schema_version}', "
            "''"
            f") = '{CHANNEL_TALK_DOCUMENT_ARTICLE_V2_SCHEMA_VERSION}'"
        ),
    )


def validate_channel_talk_user_chat_v2_sample_row(
    row: dict[str, Any],
) -> ChannelTalkV2SampleValidation:
    errors: list[str] = []
    langchain_id = _validate_base_row(
        row,
        errors,
        entity_type="user_chat",
        langchain_id_prefix="channel_talk:user_chat:",
        scope_type="channel",
        target_type="channel",
        title_required=True,
    )
    _validate_parts(row.get("data"), errors)
    metadata = _validate_metadata_namespace(
        row.get("langchain_metadata"),
        namespace="channel_talk_user_chat",
        errors=errors,
    )
    if isinstance(metadata, dict):
        if metadata.get("state") in (None, ""):
            errors.append("missing:channel_talk_user_chat.state")
        for field_name in ("assignment", "messages", "timing", "metrics", "anchors"):
            if field_name in metadata and not isinstance(metadata[field_name], dict):
                errors.append(f"invalid:channel_talk_user_chat.{field_name}")
    return ChannelTalkV2SampleValidation(langchain_id=langchain_id, errors=tuple(errors))


def validate_channel_talk_document_article_v2_sample_row(
    row: dict[str, Any],
) -> ChannelTalkV2SampleValidation:
    errors: list[str] = []
    langchain_id = _validate_base_row(
        row,
        errors,
        entity_type="document_article",
        langchain_id_prefix="channel_talk:document_article:",
        scope_type="channel",
        target_type="document_space",
        title_required=False,
    )
    _validate_parts(row.get("data"), errors)
    metadata = _validate_metadata_namespace(
        row.get("langchain_metadata"),
        namespace="channel_talk_document_article",
        errors=errors,
    )
    if isinstance(metadata, dict):
        if metadata.get("schema_version") != CHANNEL_TALK_DOCUMENT_ARTICLE_V2_SCHEMA_VERSION:
            errors.append("invalid:channel_talk_document_article.schema_version")
        for field_name in ("author", "taxonomy", "publication"):
            if field_name in metadata and not isinstance(metadata[field_name], dict):
                errors.append(f"invalid:channel_talk_document_article.{field_name}")
    return ChannelTalkV2SampleValidation(langchain_id=langchain_id, errors=tuple(errors))


def _count_validation_from_row(row: dict[str, Any]) -> ChannelTalkV2CountValidation:
    return ChannelTalkV2CountValidation(
        v1_count=int(row["v1_count"] or 0),
        v2_count=int(row["v2_count"] or 0),
        missing_in_v2=int(row["missing_in_v2"] or 0),
        extra_in_v2=int(row["extra_in_v2"] or 0),
    )


def _count_validation_select_sql() -> str:
    return """
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


def _sample_query(*, entity_type: str, namespace: str, extra_predicate: str):
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
        WHERE source = 'channel_talk'
          AND entity_type = '{entity_type}'
          AND {_metadata_namespace_predicate(namespace)}
          {extra_predicate}
        ORDER BY synced_at DESC, langchain_id ASC
        LIMIT :limit
        """
    )


def _validate_base_row(
    row: dict[str, Any],
    errors: list[str],
    *,
    entity_type: str,
    langchain_id_prefix: str,
    scope_type: str,
    target_type: str,
    title_required: bool,
) -> str:
    langchain_id = str(row.get("langchain_id") or "")
    required_fields = [
        "langchain_id",
        "content",
        "source",
        "entity_type",
        "record_id",
        "scope_type",
        "scope_id",
        "target_type",
        "target_id",
        "url",
        "created_at",
        "updated_at",
        "synced_at",
    ]
    if title_required:
        required_fields.append("title")

    for field_name in required_fields:
        if row.get(field_name) in (None, ""):
            errors.append(f"missing:{field_name}")
    if row.get("body") is None:
        errors.append("missing:body")

    if langchain_id and not langchain_id.startswith(langchain_id_prefix):
        errors.append("invalid:langchain_id_prefix")
    if row.get("source") != "channel_talk":
        errors.append("invalid:source")
    if row.get("entity_type") != entity_type:
        errors.append("invalid:entity_type")
    if row.get("scope_type") != scope_type:
        errors.append("invalid:scope_type")
    if row.get("target_type") != target_type:
        errors.append("invalid:target_type")
    return langchain_id


def _validate_parts(data: Any, errors: list[str]) -> None:
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
        if part.get("type") in (None, ""):
            errors.append(f"missing:data.parts[{index}].type")
        if part.get("text") is None:
            errors.append(f"missing:data.parts[{index}].text")
        if not isinstance(part.get("metadata"), dict):
            errors.append(f"missing:data.parts[{index}].metadata")


def _validate_metadata_namespace(
    metadata: Any,
    *,
    namespace: str,
    errors: list[str],
) -> dict[str, Any] | None:
    if not isinstance(metadata, dict):
        errors.append("missing:langchain_metadata")
        return None
    if set(metadata) != {namespace}:
        errors.append("invalid:metadata_namespace")
        return None
    namespace_metadata = metadata.get(namespace)
    if not isinstance(namespace_metadata, dict):
        errors.append(f"missing:{namespace}")
        return None
    if "contextual_content" in namespace_metadata:
        errors.append(f"forbidden:{namespace}.contextual_content")
    return namespace_metadata
