from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Protocol

from catchup.connectors.channel_talk.document_space.article_full_sync_models import (
    DEFAULT_ARTICLE_FULL_SYNC_STATES,
)
from catchup.connectors.channel_talk.document_space.article_full_sync_models import (
    ChannelTalkArticleFullSyncConnection,
)
from catchup.connectors.channel_talk.document_space.article_full_sync_models import (
    ChannelTalkFetchedArticle,
)
from catchup.connectors.channel_talk.document_space.article_full_sync_models import (
    ChannelTalkFetchedArticlesResult,
)
from catchup.connectors.channel_talk.document_space.client import ARTICLE_BATCH_MAX_SIZE
from catchup.connectors.channel_talk.document_space.client import (
    DEFAULT_ARTICLE_LIST_LIMIT,
)
from catchup.connectors.channel_talk.document_space.client import (
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


class ChannelTalkArticleSyncWindow(Protocol):
    window_start: datetime
    window_end: datetime


class ChannelTalkArticleClient(Protocol):
    async def get_article(
        self,
        *,
        article_id: str,
        language: str,
    ) -> ChannelTalkDocumentArticleView: ...

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


ArticleClientFactory = Callable[
    [ChannelTalkArticleFullSyncConnection],
    ChannelTalkArticleClient,
]


class ChannelTalkArticleFullSyncFetcher:
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
        connection: ChannelTalkArticleFullSyncConnection,
        language: str,
        sync_window: ChannelTalkArticleSyncWindow,
        states: tuple[ChannelTalkDocumentArticleState, ...] = (
            DEFAULT_ARTICLE_FULL_SYNC_STATES
        ),
        checkpoint_state: ChannelTalkDocumentArticleState | None = None,
        checkpoint_cursor: str | None = None,
    ) -> ChannelTalkFetchedArticlesResult:
        if not states:
            raise ValueError("states must include at least one state")
        if checkpoint_state is not None and checkpoint_state not in states:
            raise ValueError("checkpoint_state must be included in states")

        client = self._client_factory(connection)
        fetched: list[ChannelTalkFetchedArticle] = []
        fetched_pages = 0

        effective_checkpoint_state = self._effective_checkpoint_state(
            states=states,
            checkpoint_state=checkpoint_state,
            checkpoint_cursor=checkpoint_cursor,
        )
        states_to_fetch = self._states_from_checkpoint(
            states=states,
            checkpoint_state=effective_checkpoint_state,
        )

        for state_index, state in enumerate(states_to_fetch):
            next_cursor = checkpoint_cursor if state_index == 0 else None

            while True:
                page = await client.list_articles(
                    language=language,
                    state=state,
                    since=next_cursor,
                    limit=self._page_limit,
                    order="asc",
                )
                fetched_pages += 1

                page_bundles = await self._fetch_page_bundles(
                    client=client,
                    language=language,
                    state=state,
                    articles=page.articles,
                )
                fetched.extend(
                    bundle
                    for bundle in page_bundles
                    if self._is_in_sync_window(
                        bundle=bundle,
                        sync_window=sync_window,
                    )
                )

                budgeted_result = self._build_page_budget_result(
                    fetched=fetched,
                    fetched_pages=fetched_pages,
                    page=page,
                    states=states,
                    state=state,
                )
                if budgeted_result is not None:
                    return budgeted_result

                if page.next_page_token is None:
                    break
                next_cursor = page.next_page_token

        return self._build_result(fetched=fetched)

    async def fetch_article_bundle_by_id(
        self,
        *,
        connection: ChannelTalkArticleFullSyncConnection,
        article_id: str,
        language: str,
    ) -> ChannelTalkFetchedArticle:
        client = self._client_factory(connection)
        detail = await client.get_article(
            article_id=article_id,
            language=language,
        )
        source = detail.article
        published_revision = None
        # 현재 article 자체가 published revision이면 추가 revision API 호출 없이 detail을 사용한다.
        published_revision_id = self._published_revision_id_to_fetch(source)
        if published_revision_id is not None:
            published_revision = await client.get_article_revision(
                article_id=article_id,
                revision_id=published_revision_id,
            )
        return ChannelTalkFetchedArticle(
            language=language,
            state=source.state,
            list_item=source,
            detail=detail,
            published_revision=published_revision,
        )

    @staticmethod
    def _effective_checkpoint_state(
        *,
        states: tuple[ChannelTalkDocumentArticleState, ...],
        checkpoint_state: ChannelTalkDocumentArticleState | None,
        checkpoint_cursor: str | None,
    ) -> ChannelTalkDocumentArticleState | None:
        if checkpoint_state is not None:
            return checkpoint_state
        if checkpoint_cursor is not None:
            return states[0]
        return None

    @staticmethod
    def _states_from_checkpoint(
        *,
        states: tuple[ChannelTalkDocumentArticleState, ...],
        checkpoint_state: ChannelTalkDocumentArticleState | None,
    ) -> tuple[ChannelTalkDocumentArticleState, ...]:
        if checkpoint_state is None:
            return states
        return states[states.index(checkpoint_state) :]

    async def _fetch_page_bundles(
        self,
        *,
        client: ChannelTalkArticleClient,
        language: str,
        state: ChannelTalkDocumentArticleState,
        articles: list[ChannelTalkDocumentArticle],
    ) -> tuple[ChannelTalkFetchedArticle, ...]:
        article_ids = tuple(article.article_id for article in articles)
        # 호출 순서:
        # 1. list_articles 결과의 id들을 batch_get_articles로 보강한다.
        # 2. batch 응답만으로 published content를 확정할 수 없는 문서만
        #    get_article_revision으로 published revision을 가져온다.
        details_by_id = await self._batch_get_article_details(
            client=client,
            article_ids=article_ids,
            language=language,
        )
        published_revisions_by_id = await self._fetch_published_revisions(
            client=client,
            articles=articles,
            details_by_id=details_by_id,
        )
        return tuple(
            ChannelTalkFetchedArticle(
                language=language,
                state=state,
                list_item=article,
                detail=details_by_id.get(article.article_id),
                published_revision=published_revisions_by_id.get(article.article_id),
            )
            for article in articles
        )

    async def _fetch_published_revisions(
        self,
        *,
        client: ChannelTalkArticleClient,
        articles: list[ChannelTalkDocumentArticle],
        details_by_id: dict[str, ChannelTalkDocumentArticleView],
    ) -> dict[str, ChannelTalkDocumentArticleRevisionView]:
        revisions: dict[str, ChannelTalkDocumentArticleRevisionView] = {}
        for article in articles:
            detail = details_by_id.get(article.article_id)
            # batch detail이 있으면 그 값을 기준으로 판단한다.
            source = detail.article if detail is not None else article
            published_revision_id = self._published_revision_id_to_fetch(source)
            if published_revision_id is None:
                continue
            revisions[article.article_id] = await client.get_article_revision(
                article_id=article.article_id,
                revision_id=published_revision_id,
            )
        return revisions

    @staticmethod
    def _published_revision_id_to_fetch(
        source: ChannelTalkDocumentArticle,
    ) -> str | None:
        published_revision_id = source.published_revision_id
        if published_revision_id is None:
            return None
        if (
            source.state == ChannelTalkDocumentArticleState.PUBLISHED
            and source.current_revision_id == published_revision_id
        ):
            return None
        return published_revision_id

    async def _batch_get_article_details(
        self,
        *,
        client: ChannelTalkArticleClient,
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
        bundle: ChannelTalkFetchedArticle,
        sync_window: ChannelTalkArticleSyncWindow,
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

    def _build_page_budget_result(
        self,
        *,
        fetched: list[ChannelTalkFetchedArticle],
        fetched_pages: int,
        page: ChannelTalkDocumentArticlePage,
        states: tuple[ChannelTalkDocumentArticleState, ...],
        state: ChannelTalkDocumentArticleState,
    ) -> ChannelTalkFetchedArticlesResult | None:
        if not self._reached_page_budget(fetched_pages):
            return None

        if page.next_page_token is not None:
            return self._build_result(
                fetched=fetched,
                next_checkpoint_state=state,
                next_checkpoint_cursor=page.next_page_token,
            )

        next_state = self._next_state(states=states, current=state)
        if next_state is None:
            return None
        return self._build_result(
            fetched=fetched,
            next_checkpoint_state=next_state,
        )

    @staticmethod
    def _build_result(
        *,
        fetched: list[ChannelTalkFetchedArticle],
        next_checkpoint_state: ChannelTalkDocumentArticleState | None = None,
        next_checkpoint_cursor: str | None = None,
    ) -> ChannelTalkFetchedArticlesResult:
        return ChannelTalkFetchedArticlesResult(
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
        connection: ChannelTalkArticleFullSyncConnection,
    ) -> ChannelTalkDocumentsApiClient:
        return ChannelTalkDocumentsApiClient(
            access_key=connection.access_key,
            access_secret=connection.access_secret,
        )
