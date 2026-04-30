from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Protocol

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import ValidationInfo
from pydantic import field_validator
from pydantic import model_validator

from catchup.connectors.channel_talk.documents_client import ARTICLE_BATCH_MAX_SIZE
from catchup.connectors.channel_talk.documents_client import DEFAULT_ARTICLE_LIST_LIMIT
from catchup.connectors.channel_talk.documents_client import (
    ChannelTalkDocumentsApiClient,
)
from catchup.connectors.channel_talk.schemas.document_article import (
    ChannelTalkDocumentArticle,
)
from catchup.connectors.channel_talk.schemas.document_article import (
    ChannelTalkDocumentArticleBatchResult,
)
from catchup.connectors.channel_talk.schemas.document_article import (
    ChannelTalkDocumentArticlePage,
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

DEFAULT_DOCUMENT_ARTICLE_FULL_SYNC_STATES: tuple[ChannelTalkDocumentArticleState, ...] = (
    ChannelTalkDocumentArticleState.PUBLISHED,
    ChannelTalkDocumentArticleState.UNPUBLISHED,
    ChannelTalkDocumentArticleState.DRAFT,
)


class ChannelTalkDocumentArticleSyncWindow(Protocol):
    window_start: datetime
    window_end: datetime


class ChannelTalkDocumentArticleClient(Protocol):
    async def list_articles(
        self,
        *,
        language: str,
        state: ChannelTalkDocumentArticleState,
        since: str | None,
        limit: int,
        order: str,
    ) -> ChannelTalkDocumentArticlePage: ...

    async def batch_get_articles(
        self,
        *,
        article_ids: tuple[str, ...],
        language: str,
    ) -> ChannelTalkDocumentArticleBatchResult: ...

    async def get_article_revision(
        self,
        *,
        article_id: str,
        revision_id: str,
    ) -> ChannelTalkDocumentArticleRevisionView: ...


class ChannelTalkDocumentArticleFullSyncConnection(BaseModel):
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
    ) -> "ChannelTalkDocumentArticleFullSyncConnection":
        return cls(
            channel_id=record.channel_id,
            space_id=record.space_id,
            access_key=require_text(record.access_key, "access_key"),
            access_secret=require_text(record.access_secret, "access_secret"),
        )


class ChannelTalkFetchedDocumentArticle(BaseModel):
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
    def _fill_derived_fields(self) -> "ChannelTalkFetchedDocumentArticle":
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


class ChannelTalkFetchedDocumentArticlesResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bundles: tuple[ChannelTalkFetchedDocumentArticle, ...] = ()
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
    ) -> "ChannelTalkFetchedDocumentArticlesResult":
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


ArticleClientFactory = Callable[
    [ChannelTalkDocumentArticleFullSyncConnection],
    ChannelTalkDocumentArticleClient,
]


class ChannelTalkDocumentArticleFullSyncFetcher:
    def __init__(
        self,
        *,
        client_factory: ArticleClientFactory | None = None,
        page_limit: int = DEFAULT_ARTICLE_LIST_LIMIT,
        max_article_pages_per_run: int | None = None,
    ) -> None:
        if page_limit < 1:
            raise ValueError("page_limit must be positive")
        if max_article_pages_per_run is not None and max_article_pages_per_run < 1:
            raise ValueError("max_article_pages_per_run must be positive")
        self._client_factory = client_factory or self._build_client
        self._page_limit = page_limit
        self._max_article_pages_per_run = max_article_pages_per_run

    async def fetch_articles(
        self,
        *,
        connection: ChannelTalkDocumentArticleFullSyncConnection,
        language: str,
        sync_window: ChannelTalkDocumentArticleSyncWindow,
        states: tuple[ChannelTalkDocumentArticleState, ...] = (
            DEFAULT_DOCUMENT_ARTICLE_FULL_SYNC_STATES
        ),
        checkpoint_state: ChannelTalkDocumentArticleState | None = None,
        checkpoint_cursor: str | None = None,
    ) -> ChannelTalkFetchedDocumentArticlesResult:
        if not states:
            raise ValueError("states must include at least one state")
        if checkpoint_state is not None and checkpoint_state not in states:
            raise ValueError("checkpoint_state must be included in states")
        client = self._client_factory(connection)
        fetched: list[ChannelTalkFetchedDocumentArticle] = []
        fetched_pages = 0
        effective_checkpoint_state = checkpoint_state
        if effective_checkpoint_state is None and checkpoint_cursor is not None:
            effective_checkpoint_state = states[0]
        resume_from_checkpoint = effective_checkpoint_state is not None

        for state in states:
            if resume_from_checkpoint and effective_checkpoint_state != state:
                continue

            next_cursor = (
                checkpoint_cursor if effective_checkpoint_state == state else None
            )
            resume_from_checkpoint = False

            while True:
                page = await client.list_articles(
                    language=language,
                    state=state,
                    since=next_cursor,
                    limit=self._page_limit,
                    order="asc",
                )
                fetched_pages += 1

                article_ids = tuple(article.article_id for article in page.articles)
                details_by_id = await self._batch_get_article_details(
                    client=client,
                    article_ids=article_ids,
                    language=language,
                )
                published_revisions_by_id = await self._fetch_published_revisions(
                    client=client,
                    articles=page.articles,
                    details_by_id=details_by_id,
                )
                page_bundles = tuple(
                    ChannelTalkFetchedDocumentArticle(
                        language=language,
                        state=state,
                        list_item=article,
                        detail=details_by_id.get(article.article_id),
                        published_revision=published_revisions_by_id.get(
                            article.article_id
                        ),
                    )
                    for article in page.articles
                )
                fetched.extend(
                    bundle
                    for bundle in page_bundles
                    if self._is_in_sync_window(bundle=bundle, sync_window=sync_window)
                )

                if self._reached_page_budget(fetched_pages):
                    if page.next_page_token is not None:
                        return self._build_result(
                            fetched=fetched,
                            next_checkpoint_state=state,
                            next_checkpoint_cursor=page.next_page_token,
                        )

                    next_state = self._next_state(states=states, current=state)
                    if next_state is not None:
                        return self._build_result(
                            fetched=fetched,
                            next_checkpoint_state=next_state,
                        )

                if page.next_page_token is None:
                    break
                next_cursor = page.next_page_token

        return self._build_result(fetched=fetched)

    async def _fetch_published_revisions(
        self,
        *,
        client: ChannelTalkDocumentArticleClient,
        articles: list[ChannelTalkDocumentArticle],
        details_by_id: dict[str, ChannelTalkDocumentArticleView],
    ) -> dict[str, ChannelTalkDocumentArticleRevisionView]:
        revisions: dict[str, ChannelTalkDocumentArticleRevisionView] = {}
        for article in articles:
            detail = details_by_id.get(article.article_id)
            source = detail.article if detail is not None else article
            if source.published_revision_id is None:
                continue
            revisions[article.article_id] = await client.get_article_revision(
                article_id=article.article_id,
                revision_id=source.published_revision_id,
            )
        return revisions

    async def _batch_get_article_details(
        self,
        *,
        client: ChannelTalkDocumentArticleClient,
        article_ids: tuple[str, ...],
        language: str,
    ) -> dict[str, ChannelTalkDocumentArticleView]:
        details: dict[str, ChannelTalkDocumentArticleView] = {}
        for chunk in self._chunks(article_ids, ARTICLE_BATCH_MAX_SIZE):
            batch = await client.batch_get_articles(
                article_ids=chunk,
                language=language,
            )
            details.update(self._build_article_views_by_id(batch))
        return details

    @staticmethod
    def _build_article_views_by_id(
        batch: ChannelTalkDocumentArticleBatchResult,
    ) -> dict[str, ChannelTalkDocumentArticleView]:
        categories_by_article_id = {
            category.article_id: category
            for category in batch.article_categories
            if category.article_id is not None
        }
        authors_by_id = {author.author_id: author for author in batch.authors}
        topics_by_id = {topic.topic_id: topic for topic in batch.topics}

        views: dict[str, ChannelTalkDocumentArticleView] = {}
        for article in batch.articles:
            views[article.article_id] = ChannelTalkDocumentArticleView(
                article=article,
                article_category=categories_by_article_id.get(article.article_id),
                author=(
                    authors_by_id.get(article.author_id)
                    if article.author_id is not None
                    else None
                ),
                topics=[
                    topic
                    for topic_id in article.topic_ids
                    if (topic := topics_by_id.get(topic_id)) is not None
                ],
            )
        return views

    @staticmethod
    def _is_in_sync_window(
        *,
        bundle: ChannelTalkFetchedDocumentArticle,
        sync_window: ChannelTalkDocumentArticleSyncWindow,
    ) -> bool:
        timestamp = bundle.ordering_timestamp
        if timestamp is None:
            return True
        return sync_window.window_start <= timestamp <= sync_window.window_end

    def _reached_page_budget(self, fetched_pages: int) -> bool:
        return (
            self._max_article_pages_per_run is not None
            and fetched_pages >= self._max_article_pages_per_run
        )

    @staticmethod
    def _build_result(
        *,
        fetched: list[ChannelTalkFetchedDocumentArticle],
        next_checkpoint_state: ChannelTalkDocumentArticleState | None = None,
        next_checkpoint_cursor: str | None = None,
    ) -> ChannelTalkFetchedDocumentArticlesResult:
        return ChannelTalkFetchedDocumentArticlesResult(
            bundles=tuple(fetched),
            fetched_count=len(fetched),
            article_ids=tuple(bundle.article_id for bundle in fetched),
            next_checkpoint_state=next_checkpoint_state,
            next_checkpoint_cursor=next_checkpoint_cursor,
        )

    @staticmethod
    def _next_state(
        *,
        states: tuple[ChannelTalkDocumentArticleState, ...],
        current: ChannelTalkDocumentArticleState,
    ) -> ChannelTalkDocumentArticleState | None:
        for index, state in enumerate(states):
            if state != current:
                continue
            if index + 1 >= len(states):
                return None
            return states[index + 1]
        return None

    @staticmethod
    def _chunks(
        values: tuple[str, ...],
        size: int,
    ) -> tuple[tuple[str, ...], ...]:
        return tuple(
            values[index : index + size] for index in range(0, len(values), size)
        )

    @staticmethod
    def _build_client(
        connection: ChannelTalkDocumentArticleFullSyncConnection,
    ) -> ChannelTalkDocumentsApiClient:
        return ChannelTalkDocumentsApiClient(
            access_key=connection.access_key,
            access_secret=connection.access_secret,
        )
