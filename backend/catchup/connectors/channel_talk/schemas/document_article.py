from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from enum import StrEnum
from typing import Any
from typing import NamedTuple
from typing import TypeAlias

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import SkipValidation
from pydantic import ValidationInfo
from pydantic import field_validator

from catchup.connectors.channel_talk.schemas._parsing import _first_localized_text
from catchup.connectors.channel_talk.schemas._parsing import _mapping_copy
from catchup.connectors.channel_talk.schemas._parsing import _parse_mapping_list
from catchup.connectors.channel_talk.schemas._parsing import _parse_optional_mapping
from catchup.connectors.channel_talk.schemas._parsing import _PayloadReader
from catchup.connectors.channel_talk.schemas._parsing import _required_reader_text
from catchup.connectors.channel_talk.schemas._parsing import _unwrap_payload
from catchup.connectors.channel_talk.schemas.document_metadata import (
    ChannelTalkDocumentAuthorMetadata,
)
from catchup.utils.validation import require_text

ChannelTalkDocumentArticleBody: TypeAlias = str | list[Mapping[str, Any]]


class ChannelTalkDocumentArticleState(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    UNPUBLISHED = "unpublished"


class ChannelTalkDocumentWebsite(BaseModel):
    model_config = ConfigDict(extra="ignore")

    url: str | None = None

    @classmethod
    def from_api_payload(cls, payload: Any) -> ChannelTalkDocumentWebsite | None:
        if not isinstance(payload, Mapping):
            return None
        reader = _PayloadReader(payload)
        return cls(url=reader.text("url"))


class ChannelTalkDocumentTopic(BaseModel):
    model_config = ConfigDict(extra="ignore")

    topic_id: str
    name: str | None = None
    localized_name: dict[str, Any] | None = None
    slug: str | None = None
    parent_id: str | None = None

    @field_validator("topic_id")
    @classmethod
    def validate_topic_id(cls, value: str) -> str:
        return require_text(value, "topic_id")

    @classmethod
    def from_api_payload(cls, payload: Any) -> "ChannelTalkDocumentTopic":
        if not isinstance(payload, Mapping):
            raise ValueError("topic payload must be an object")
        reader = _PayloadReader(payload)
        topic_id = _required_reader_text(
            reader,
            "topic payload missing topic id",
            "id",
        )
        localized_name = _mapping_copy(payload.get("name") or payload.get("title"))
        return cls(
            topic_id=topic_id,
            name=reader.text("name", "title", skip_mappings=True)
            or _first_localized_text(localized_name),
            localized_name=localized_name,
            slug=reader.text("slug"),
            parent_id=None,
        )


class ChannelTalkDocumentArticleCategory(BaseModel):
    model_config = ConfigDict(extra="ignore")

    article_category_id: str
    article_id: str | None = None
    name: str | None = None
    localized_name: dict[str, Any] | None = None
    slug: str | None = None

    @field_validator("article_category_id")
    @classmethod
    def validate_article_category_id(cls, value: str) -> str:
        return require_text(value, "article_category_id")

    @classmethod
    def from_api_payload(cls, payload: Any) -> "ChannelTalkDocumentArticleCategory":
        if not isinstance(payload, Mapping):
            raise ValueError("article category payload must be an object")
        root_reader = _PayloadReader(payload)
        category_payload = payload.get("category")
        source = category_payload if isinstance(category_payload, Mapping) else payload
        reader = _PayloadReader(source)
        article_category_id = _required_reader_text(
            reader,
            "article category payload missing category id",
            "id",
        )
        localized_name = _mapping_copy(source.get("name") or source.get("title"))
        return cls(
            article_category_id=article_category_id,
            article_id=root_reader.text("articleId"),
            name=reader.text("name", "title", skip_mappings=True)
            or _first_localized_text(localized_name),
            localized_name=localized_name,
            slug=reader.text("slug"),
        )


class ChannelTalkDocumentArticle(BaseModel):
    model_config = ConfigDict(extra="ignore")

    article_id: str
    space_id: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    state: ChannelTalkDocumentArticleState | str | None = None
    published_revision_id: str | None = None
    published_at: datetime | None = None
    current_revision_id: str | None = None
    slug: str | None = None
    topic_ids: list[str] = Field(default_factory=list)
    website: ChannelTalkDocumentWebsite | None = None
    author_id: str | None = None
    name: str | None = None
    cover_image_url: str | None = None
    title: str | None = None
    subtitle: str | None = None
    summary: str | None = None
    body: SkipValidation[ChannelTalkDocumentArticleBody] | None = None
    body_html: str | None = None

    @field_validator("article_id")
    @classmethod
    def validate_article_id(cls, value: str) -> str:
        return require_text(value, "article_id")

    @classmethod
    def from_api_payload(cls, payload: Any) -> "ChannelTalkDocumentArticle":
        source = _unwrap_payload(payload, "article")
        reader = _PayloadReader(source)
        article_id = _required_reader_text(
            reader,
            "article payload missing article id",
            "id",
        )
        return cls(
            article_id=article_id,
            space_id=reader.text("spaceId"),
            created_at=reader.datetime("createdAt"),
            updated_at=reader.datetime("updatedAt"),
            state=_parse_article_state(reader.text("state")),
            published_revision_id=reader.text("publishedRevisionId"),
            published_at=reader.datetime("publishedAt"),
            current_revision_id=reader.text("currentRevisionId"),
            slug=reader.text("slug"),
            topic_ids=reader.text_list("topicIds"),
            website=ChannelTalkDocumentWebsite.from_api_payload(source.get("website")),
            author_id=reader.text("authorId"),
            name=reader.text("name"),
            cover_image_url=reader.text("coverImageUrl"),
            title=reader.text("title"),
            subtitle=reader.text("subtitle"),
            summary=reader.text("summary"),
            body=source.get("body"),
            body_html=reader.raw_text("bodyHtml"),
        )

    @property
    def website_url(self) -> str | None:
        if self.website is None:
            return None
        return self.website.url


class ChannelTalkDocumentArticleView(BaseModel):
    model_config = ConfigDict(extra="ignore")

    article: ChannelTalkDocumentArticle
    article_category: ChannelTalkDocumentArticleCategory | None = None
    author: ChannelTalkDocumentAuthorMetadata | None = None
    topics: list[ChannelTalkDocumentTopic] = Field(default_factory=list)

    @classmethod
    def from_api_payload(cls, payload: Any) -> "ChannelTalkDocumentArticleView":
        if not isinstance(payload, Mapping):
            return cls(article=ChannelTalkDocumentArticle.from_api_payload(payload))
        reader = _PayloadReader(payload)
        article_payload = reader.mapping("article") or payload
        return cls(
            article=ChannelTalkDocumentArticle.from_api_payload(article_payload),
            article_category=_parse_optional_mapping(
                reader.mapping("articleCategory"),
                ChannelTalkDocumentArticleCategory.from_api_payload,
            ),
            author=_parse_optional_mapping(
                reader.mapping("author"),
                ChannelTalkDocumentAuthorMetadata.from_api_payload,
            ),
            topics=_parse_mapping_list(
                reader.list_value("topics"),
                ChannelTalkDocumentTopic.from_api_payload,
            ),
        )


class ChannelTalkDocumentArticleRevision(BaseModel):
    model_config = ConfigDict(extra="ignore")

    revision_id: str
    article_id: str
    space_id: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    state: ChannelTalkDocumentArticleState | str | None = None
    language: str | None = None
    author_id: str | None = None
    name: str | None = None
    cover_image_url: str | None = None
    title: str | None = None
    subtitle: str | None = None
    summary: str | None = None
    body: SkipValidation[ChannelTalkDocumentArticleBody] | None = None
    body_html: str | None = None

    @field_validator("revision_id", "article_id")
    @classmethod
    def validate_required_text(cls, value: str, info: ValidationInfo) -> str:
        return require_text(value, info.field_name or "field")

    @classmethod
    def from_api_payload(cls, payload: Any) -> "ChannelTalkDocumentArticleRevision":
        source = _unwrap_payload(payload, "revision")
        reader = _PayloadReader(source)
        revision_id = _required_reader_text(
            reader,
            "revision payload missing revision id",
            "id",
        )
        article_id = _required_reader_text(
            reader,
            "revision payload missing article id",
            "articleId",
        )
        return cls(
            revision_id=revision_id,
            article_id=article_id,
            space_id=reader.text("spaceId"),
            created_at=reader.datetime("createdAt"),
            updated_at=reader.datetime("updatedAt"),
            state=_parse_article_state(reader.text("state")),
            language=reader.text("language"),
            author_id=reader.text("authorId"),
            name=reader.text("name"),
            cover_image_url=reader.text("coverImageUrl"),
            title=reader.text("title"),
            subtitle=reader.text("subtitle"),
            summary=reader.text("summary"),
            body=source.get("body"),
            body_html=reader.raw_text("bodyHtml"),
        )


class ChannelTalkDocumentArticleRevisionView(BaseModel):
    model_config = ConfigDict(extra="ignore")

    revision: ChannelTalkDocumentArticleRevision
    author: ChannelTalkDocumentAuthorMetadata | None = None

    @classmethod
    def from_api_payload(cls, payload: Any) -> "ChannelTalkDocumentArticleRevisionView":
        if not isinstance(payload, Mapping):
            return cls(
                revision=ChannelTalkDocumentArticleRevision.from_api_payload(payload)
            )
        reader = _PayloadReader(payload)
        revision_payload = reader.mapping("revision") or payload
        return cls(
            revision=ChannelTalkDocumentArticleRevision.from_api_payload(
                revision_payload
            ),
            author=_parse_optional_mapping(
                reader.mapping("author"),
                ChannelTalkDocumentAuthorMetadata.from_api_payload,
            ),
        )


class ChannelTalkDocumentArticlePage(BaseModel):
    articles: list[ChannelTalkDocumentArticle]
    article_categories: list[ChannelTalkDocumentArticleCategory] = Field(default_factory=list)
    authors: list[ChannelTalkDocumentAuthorMetadata] = Field(default_factory=list)
    topics: list[ChannelTalkDocumentTopic] = Field(default_factory=list)
    next_page_token: str | None = None

    @classmethod
    def from_api_payload(cls, payload: Any) -> "ChannelTalkDocumentArticlePage":
        collection = _parse_article_collection(
            payload,
            error_message="article list payload must be an object or list",
        )
        return cls(
            articles=collection.articles,
            article_categories=collection.article_categories,
            authors=collection.authors,
            topics=collection.topics,
            next_page_token=collection.next_page_token,
        )


ChannelTalkDocumentArticleDetail = ChannelTalkDocumentArticleView


class ChannelTalkDocumentArticleBatchResult(BaseModel):
    articles: list[ChannelTalkDocumentArticle]
    article_categories: list[ChannelTalkDocumentArticleCategory] = Field(default_factory=list)
    authors: list[ChannelTalkDocumentAuthorMetadata] = Field(default_factory=list)
    topics: list[ChannelTalkDocumentTopic] = Field(default_factory=list)

    @classmethod
    def from_api_payload(cls, payload: Any) -> "ChannelTalkDocumentArticleBatchResult":
        collection = _parse_article_collection(
            payload,
            error_message="article batch payload must be an object or list",
        )
        return cls(
            articles=collection.articles,
            article_categories=collection.article_categories,
            authors=collection.authors,
            topics=collection.topics,
        )


ChannelTalkDocumentArticleBatch = ChannelTalkDocumentArticleBatchResult

def _parse_article_state(
    value: str | None,
) -> ChannelTalkDocumentArticleState | str | None:
    if value is None:
        return None
    try:
        return ChannelTalkDocumentArticleState(value)
    except ValueError:
        return value


class _ArticleCollection(NamedTuple):
    articles: list[ChannelTalkDocumentArticle]
    article_categories: list[ChannelTalkDocumentArticleCategory]
    authors: list[ChannelTalkDocumentAuthorMetadata]
    topics: list[ChannelTalkDocumentTopic]
    next_page_token: str | None


def _parse_article_collection(
    payload: Any,
    *,
    error_message: str,
) -> _ArticleCollection:
    if isinstance(payload, list):
        return _ArticleCollection(
            articles=[
                ChannelTalkDocumentArticle.from_api_payload(item) for item in payload
            ],
            article_categories=[],
            authors=[],
            topics=[],
            next_page_token=None,
        )
    if not isinstance(payload, Mapping):
        raise ValueError(error_message)
    reader = _PayloadReader(payload)
    return _ArticleCollection(
        articles=_parse_mapping_list(
            reader.list_value("articles"),
            ChannelTalkDocumentArticle.from_api_payload,
        ),
        article_categories=_parse_mapping_list(
            reader.list_value("articleCategories"),
            ChannelTalkDocumentArticleCategory.from_api_payload,
        ),
        authors=_parse_mapping_list(
            reader.list_value("authors"),
            ChannelTalkDocumentAuthorMetadata.from_api_payload,
        ),
        topics=_parse_mapping_list(
            reader.list_value("topics"),
            ChannelTalkDocumentTopic.from_api_payload,
        ),
        next_page_token=reader.text("next"),
    )
