from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import ValidationInfo
from pydantic import field_validator
from pydantic import model_validator

from catchup.sync.ingestion.document_format.base import DocumentBaseMetadata
from catchup.utils.validation import require_text


class ChannelTalkUserChatChatMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    channel_id: str
    channel_name: str
    user_chat_id: str
    state: str
    managed: bool | None = None
    priority: str | None = None
    customer_name: str | None = None
    description: str | None = None
    goal_state: str | None = None

    @field_validator("channel_id", "channel_name", "user_chat_id", "state")
    @classmethod
    def _validate_required_text(cls, value: str, info: ValidationInfo) -> str:
        return require_text(value, info.field_name)


class ChannelTalkUserChatCustomerMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: str | None = None
    member_id: str | None = None
    veil_id: str | None = None
    unified_id: str | None = None
    type: str | None = None
    name: str | None = None
    email: str | None = None
    mobile_number: str | None = None
    avatar_url: str | None = None
    language: str | None = None
    country: str | None = None
    city: str | None = None
    time_zone: str | None = None

    @field_validator("user_id")
    @classmethod
    def _validate_user_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return require_text(value, "user_id")


class ChannelTalkUserChatAssignmentMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    manager_ids: list[str] = Field(default_factory=list)
    assignee_id: str | None = None
    assignee_name: str | None = None
    assignee_email: str | None = None
    first_assignee_id_after_open: str | None = None
    manager_names: list[str] = Field(default_factory=list)
    manager_role_ids: list[str] = Field(default_factory=list)


class ChannelTalkUserChatMessageMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message_ids: list[str] = Field(default_factory=list)
    last_message_at: datetime | None = None
    included_message_count: int = 0
    excluded_message_count: int = 0
    author_types: list[str] = Field(default_factory=list)
    contains_bot_messages: bool = False
    contains_private_events: bool = False
    contains_form_messages: bool = False


class ChannelTalkUserChatTimingMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    first_opened_at: datetime | None = None
    opened_at: datetime | None = None
    first_asked_at: datetime | None = None
    first_replied_at: datetime | None = None
    first_replied_at_after_open: datetime | None = None
    front_updated_at: datetime | None = None
    desk_updated_at: datetime | None = None
    follow_up_triggered_at: datetime | None = None
    closed_at: datetime | None = None
    snoozed_at: datetime | None = None


class ChannelTalkUserChatMetricsMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    waiting_time: int | None = None
    avg_reply_time: int | None = None
    total_reply_time: int | None = None
    reply_count: int | None = None
    operation_waiting_time: int | None = None
    operation_avg_reply_time: int | None = None
    operation_total_reply_time: int | None = None
    operation_reply_count: int | None = None


class ChannelTalkUserChatAnchorsMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    front_message_id: str | None = None
    desk_message_id: str | None = None
    user_last_message_id: str | None = None


class ChannelTalkUserChatTagsMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    keys: list[str] = Field(default_factory=list)
    names: list[str] = Field(default_factory=list)


class ChannelTalkUserChatChunkMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chunk_index: int = 0
    chunk_count: int = 1

    @model_validator(mode="after")
    def _validate_chunk_bounds(self) -> "ChannelTalkUserChatChunkMetadata":
        if self.chunk_index < 0:
            raise ValueError("chunk_index must be non-negative")
        if self.chunk_count < 1:
            raise ValueError("chunk_count must be greater than zero")
        if self.chunk_index >= self.chunk_count:
            raise ValueError("chunk_index must be less than chunk_count")
        return self


class ChannelTalkUserChatCoreMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chat: ChannelTalkUserChatChatMetadata
    customer: ChannelTalkUserChatCustomerMetadata
    assignment: ChannelTalkUserChatAssignmentMetadata
    messages: ChannelTalkUserChatMessageMetadata
    timing: ChannelTalkUserChatTimingMetadata
    metrics: ChannelTalkUserChatMetricsMetadata
    anchors: ChannelTalkUserChatAnchorsMetadata
    tags: ChannelTalkUserChatTagsMetadata
    chunk: ChannelTalkUserChatChunkMetadata


class ChannelTalkUserChatLogicalMetadata(BaseModel):
    """
    Logical contract only.

    Storage remains free to project these fields into the current flat pg_embedding
    metadata shape until a later full-data rewrite migrates the physical layout.
    """

    model_config = ConfigDict(extra="forbid")

    base: DocumentBaseMetadata
    user_chat_core: ChannelTalkUserChatCoreMetadata

    @model_validator(mode="after")
    def _validate_cross_field_consistency(self) -> "ChannelTalkUserChatLogicalMetadata":
        chat = self.user_chat_core.chat

        if self.base.source != "channel_talk":
            raise ValueError("base.source must be channel_talk")
        if self.base.record_id != chat.user_chat_id:
            raise ValueError(
                "base.record_id must match user_chat_core.chat.user_chat_id"
            )

        return self

    def to_storage_metadata(self) -> dict[str, object]:
        """
        Current physical-storage projection for the existing flat pg_embedding layout.

        The logical contract remains nested, but shared read paths can continue to
        use top-level keys until the later all-data rewrite adopts nested storage.
        """
        base_storage = self.base.model_dump(mode="json")
        core_storage = self.user_chat_core.model_dump(mode="json")
        timing = self.user_chat_core.timing

        storage = {
            **base_storage,
            "entity_type": "user_chat",
            "user_chat_core": core_storage,
        }

        if (
            base_storage.get("updated_at") is None
            and timing.desk_updated_at is not None
        ):
            storage["updated_at"] = timing.desk_updated_at.isoformat()

        return storage


class ChannelTalkDocumentArticleArticleMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    article_id: str
    language: str
    state: str
    title: str | None = None
    subtitle: str | None = None
    summary: str | None = None
    body_text: str | None = None
    slug: str | None = None
    url: str | None = None

    @field_validator("article_id", "language", "state")
    @classmethod
    def _validate_required_text(cls, value: str, info: ValidationInfo) -> str:
        return require_text(value, info.field_name or "field")


class ChannelTalkDocumentArticleSpaceMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    channel_id: str
    space_id: str
    channel_name: str
    space_name: str | None = None

    @field_validator("channel_id", "space_id", "channel_name")
    @classmethod
    def _validate_required_text(cls, value: str, info: ValidationInfo) -> str:
        return require_text(value, info.field_name or "field")


class ChannelTalkDocumentArticleAuthorMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    author_id: str | None = None
    author_name: str | None = None


class ChannelTalkDocumentArticleTaxonomyMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topic_ids: list[str] = Field(default_factory=list)
    topic_names: list[str] = Field(default_factory=list)
    category_id: str | None = None
    category_name: str | None = None


class ChannelTalkDocumentArticlePublicationMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    created_at: datetime | None = None
    updated_at: datetime | None = None
    published_at: datetime | None = None
    published_revision_id: str | None = None
    current_revision_id: str | None = None


class ChannelTalkDocumentArticleChunkMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chunk_index: int = 0
    chunk_count: int = 1

    @model_validator(mode="after")
    def _validate_chunk_bounds(self) -> "ChannelTalkDocumentArticleChunkMetadata":
        if self.chunk_index < 0:
            raise ValueError("chunk_index must be non-negative")
        if self.chunk_count < 1:
            raise ValueError("chunk_count must be greater than zero")
        if self.chunk_index >= self.chunk_count:
            raise ValueError("chunk_index must be less than chunk_count")
        return self


class ChannelTalkDocumentArticleCoreMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    article: ChannelTalkDocumentArticleArticleMetadata
    space: ChannelTalkDocumentArticleSpaceMetadata
    author: ChannelTalkDocumentArticleAuthorMetadata
    taxonomy: ChannelTalkDocumentArticleTaxonomyMetadata
    publication: ChannelTalkDocumentArticlePublicationMetadata
    chunk: ChannelTalkDocumentArticleChunkMetadata


class ChannelTalkDocumentArticleLogicalMetadata(BaseModel):
    """
    Logical contract for Channel Talk document articles stored in PGVector.

    The storage projection keeps the nested contract while exposing commonly
    queried fields as flat cmetadata keys for current retrieval paths.
    """

    model_config = ConfigDict(extra="forbid")

    base: DocumentBaseMetadata
    document_article_core: ChannelTalkDocumentArticleCoreMetadata

    @model_validator(mode="after")
    def _validate_cross_field_consistency(
        self,
    ) -> "ChannelTalkDocumentArticleLogicalMetadata":
        article = self.document_article_core.article

        if self.base.source != "channel_talk":
            raise ValueError("base.source must be channel_talk")
        if self.base.record_id != article.article_id:
            raise ValueError(
                "base.record_id must match document_article_core.article.article_id"
            )

        return self

    def to_storage_metadata(self) -> dict[str, object]:
        base_storage = self.base.model_dump(mode="json")
        core_storage = self.document_article_core.model_dump(mode="json")
        core = self.document_article_core
        article = core.article
        article_storage = core_storage.get("article")
        if isinstance(article_storage, dict):
            article_storage.pop("summary", None)
            article_storage.pop("body_text", None)

        return {
            **base_storage,
            "entity_type": "document_article",
            "title": article.title,
            "document_article_core": core_storage,
        }
