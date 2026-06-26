from __future__ import annotations

from datetime import datetime
from typing import Any

from langchain_core.documents import Document
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import field_validator

from catchup.components.vector_db.v2.constants import (
    KNOWLEDGE_STORE_METADATA_COLUMN_NAMES,
)
from catchup.utils.validation import require_text

CHANNEL_TALK_DOCUMENT_ARTICLE_V2_SCHEMA_VERSION = 2


class ChannelTalkDocumentArticleAuthorMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    external_user_id: str | None = None
    internal_user_id: str | None = None


class ChannelTalkDocumentArticleTaxonomyMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topic_ids: list[str] = Field(default_factory=list)
    topic_names: list[str] = Field(default_factory=list)
    category_id: str | None = None
    category_name: str | None = None


class ChannelTalkDocumentArticlePublicationMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    published_at: datetime | None = None
    published_revision_id: str | None = None
    current_revision_id: str | None = None


class ChannelTalkDocumentArticleMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = CHANNEL_TALK_DOCUMENT_ARTICLE_V2_SCHEMA_VERSION
    author: ChannelTalkDocumentArticleAuthorMetadata = Field(
        default_factory=ChannelTalkDocumentArticleAuthorMetadata
    )
    taxonomy: ChannelTalkDocumentArticleTaxonomyMetadata = Field(
        default_factory=ChannelTalkDocumentArticleTaxonomyMetadata
    )
    publication: ChannelTalkDocumentArticlePublicationMetadata = Field(
        default_factory=ChannelTalkDocumentArticlePublicationMetadata
    )


class ChannelTalkDocumentArticleDataPart(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    text: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChannelTalkDocumentArticleData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    parts: list[ChannelTalkDocumentArticleDataPart] = Field(default_factory=list)


class ChannelTalkDocumentArticleVectorRecord(BaseModel):
    """v2 vector-store row contract for a Channel Talk document article chunk."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    langchain_id: str
    content: str
    embedding: list[float]
    source: str
    entity_type: str
    record_id: str
    scope_type: str
    scope_id: str
    target_type: str
    target_id: str
    target_name: str
    internal_author_id: str | None = None
    title: str
    body: str
    data: ChannelTalkDocumentArticleData = Field(
        default_factory=ChannelTalkDocumentArticleData
    )
    url: str
    created_at: datetime
    updated_at: datetime
    synced_at: datetime
    channel_talk_document_article: ChannelTalkDocumentArticleMetadata

    @field_validator(
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
    )
    @classmethod
    def _validate_required_text(cls, value: str, info) -> str:
        return require_text(value, info.field_name)

    @property
    def langchain_metadata(self) -> dict[str, object]:
        return {
            "channel_talk_document_article": (
                self.channel_talk_document_article.model_dump(
                    mode="json",
                    exclude_none=False,
                )
            )
        }

    def to_db_values(self) -> dict[str, Any]:
        values = self.model_dump(
            mode="json",
            exclude={"channel_talk_document_article"},
            exclude_none=False,
        )
        values["langchain_metadata"] = self.langchain_metadata
        return values

    def to_document(self) -> Document:
        values = self.to_db_values()
        metadata = {
            column_name: values[column_name]
            for column_name in KNOWLEDGE_STORE_METADATA_COLUMN_NAMES
        }
        metadata["channel_talk_document_article"] = values["langchain_metadata"][
            "channel_talk_document_article"
        ]
        return Document(
            id=self.langchain_id,
            page_content=self.content,
            metadata=metadata,
        )
