from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import ValidationInfo
from pydantic import field_validator
from pydantic import model_validator

from catchup.connectors.channel_talk.schemas.document_article import (
    ChannelTalkDocumentArticle,
)
from catchup.connectors.channel_talk.schemas.document_article import (
    ChannelTalkDocumentArticleRevisionView,
)
from catchup.connectors.channel_talk.schemas.document_article import (
    ChannelTalkDocumentArticleState,
)
from catchup.connectors.channel_talk.schemas.document_article import (
    ChannelTalkDocumentArticleView,
)
from catchup.connectors.channel_talk.schemas.document_connection import (
    ChannelTalkDocumentCredentialsRecord,
)
from catchup.utils.validation import require_text

DEFAULT_ARTICLE_FULL_SYNC_STATES: tuple[ChannelTalkDocumentArticleState, ...] = (
    ChannelTalkDocumentArticleState.PUBLISHED,
    ChannelTalkDocumentArticleState.UNPUBLISHED,
    ChannelTalkDocumentArticleState.DRAFT,
)


class ChannelTalkArticleFullSyncConnection(BaseModel):
    """Documents article full-sync boundary credentials."""

    model_config = ConfigDict(extra="forbid")

    channel_id: str
    space_id: str
    access_key: str
    access_secret: str

    @field_validator("channel_id", "space_id", "access_key", "access_secret")
    @classmethod
    def _validate_required_text(cls, value: str, info: ValidationInfo) -> str:
        return require_text(value, info.field_name or "field")

    @classmethod
    def from_credentials_record(
        cls,
        record: ChannelTalkDocumentCredentialsRecord,
    ) -> "ChannelTalkArticleFullSyncConnection":
        return cls(
            channel_id=record.channel_id,
            space_id=record.space_id,
            access_key=require_text(record.access_key, "access_key"),
            access_secret=require_text(record.access_secret, "access_secret"),
        )


class ChannelTalkFetchedArticle(BaseModel):
    """Article summary plus the best available batch/detail payload."""

    model_config = ConfigDict(extra="forbid")

    language: str
    state: ChannelTalkDocumentArticleState | str | None = None
    list_item: ChannelTalkDocumentArticle
    detail: ChannelTalkDocumentArticleView | None = None
    published_revision: ChannelTalkDocumentArticleRevisionView | None = None
    updated_at: datetime | None = None
    published_at: datetime | None = None

    @field_validator("language")
    @classmethod
    def _validate_language(cls, value: str) -> str:
        return require_text(value, "language")

    @model_validator(mode="after")
    def _fill_derived_fields(self) -> "ChannelTalkFetchedArticle":
        detail_article = self.detail.article if self.detail is not None else None
        if self.state is None:
            self.state = (
                detail_article.state
                if detail_article is not None
                else self.list_item.state
            )
        if self.updated_at is None:
            self.updated_at = (
                detail_article.updated_at
                if detail_article is not None
                else self.list_item.updated_at
            )
        if self.published_at is None:
            self.published_at = (
                detail_article.published_at
                if detail_article is not None
                else self.list_item.published_at
            )
        return self

    @property
    def article_id(self) -> str:
        return self.list_item.article_id

    @property
    def ordering_timestamp(self) -> datetime | None:
        return self.updated_at or self.published_at


class ChannelTalkFetchedArticlesResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bundles: tuple[ChannelTalkFetchedArticle, ...] = ()
    fetched_count: int = 0
    article_ids: tuple[str, ...] = ()
    next_checkpoint_state: ChannelTalkDocumentArticleState | None = None
    next_checkpoint_cursor: str | None = None

    @field_validator("article_ids")
    @classmethod
    def _validate_article_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(require_text(item, "article_ids") for item in value)

    @model_validator(mode="after")
    def _validate_checkpoint_and_fill_summary_fields(
        self,
    ) -> "ChannelTalkFetchedArticlesResult":
        if self.fetched_count == 0 and self.bundles:
            self.fetched_count = len(self.bundles)
        if not self.article_ids and self.bundles:
            self.article_ids = tuple(bundle.article_id for bundle in self.bundles)
        if (
            self.next_checkpoint_cursor is not None
            and self.next_checkpoint_state is None
        ):
            raise ValueError(
                "next_checkpoint_state is required with next_checkpoint_cursor"
            )
        return self
