from __future__ import annotations

from datetime import datetime
from datetime import timezone
from unittest import IsolatedAsyncioTestCase

from catchup.connector_core.ports.sync_ingestion import SyncWindow
from catchup.connectors.channel_talk.document_space.article_full_sync_fetcher import (
    ChannelTalkArticleFullSyncFetcher,
)
from catchup.connectors.channel_talk.document_space.article_full_sync_models import (
    ChannelTalkArticleFullSyncConnection,
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
    ChannelTalkDocumentArticleRevision,
)
from catchup.connectors.channel_talk.schemas.document_article import (
    ChannelTalkDocumentArticleRevisionView,
)
from catchup.connectors.channel_talk.schemas.document_article import (
    ChannelTalkDocumentArticleState,
)
from catchup.connectors.channel_talk.schemas.document_connection import (
    ChannelTalkDocumentAssociationStatus,
)
from catchup.connectors.channel_talk.schemas.document_connection import (
    ChannelTalkDocumentCredentialsRecord,
)


def _window() -> SyncWindow:
    return SyncWindow(
        window_start=datetime(2026, 4, 21, 0, 0, tzinfo=timezone.utc),
        window_end=datetime(2026, 4, 22, 0, 0, tzinfo=timezone.utc),
    )


def _record() -> ChannelTalkDocumentCredentialsRecord:
    return ChannelTalkDocumentCredentialsRecord(
        channel_id="channel-123",
        space_id="space-123",
        space_name="Help Center",
        access_key="documents-key",
        access_secret="documents-secret",
        association_status=ChannelTalkDocumentAssociationStatus.API_VERIFIED,
    )


def _connection() -> ChannelTalkArticleFullSyncConnection:
    return ChannelTalkArticleFullSyncConnection.from_credentials_record(
        _record(),
    )


def _article(
    article_id: str,
    *,
    state: ChannelTalkDocumentArticleState = ChannelTalkDocumentArticleState.PUBLISHED,
    updated_at: datetime | None = None,
    published_at: datetime | None = None,
    published_revision_id: str | None = None,
    current_revision_id: str | None = None,
) -> ChannelTalkDocumentArticle:
    return ChannelTalkDocumentArticle(
        article_id=article_id,
        space_id="space-123",
        updated_at=updated_at,
        published_at=published_at,
        state=state,
        published_revision_id=published_revision_id,
        current_revision_id=current_revision_id,
        title=f"Article {article_id}",
    )


def _revision(
    article_id: str,
    revision_id: str = "revision-published-1",
) -> ChannelTalkDocumentArticleRevisionView:
    return ChannelTalkDocumentArticleRevisionView(
        revision=ChannelTalkDocumentArticleRevision(
            revision_id=revision_id,
            article_id=article_id,
            state=ChannelTalkDocumentArticleState.PUBLISHED,
            title=f"Published {article_id}",
            body_html=f"<p>Published body for {article_id}</p>",
        )
    )


class _FakeDocumentsClient:
    def __init__(
        self,
        *,
        pages: list[ChannelTalkDocumentArticlePage],
        details_by_id: dict[str, ChannelTalkDocumentArticle] | None = None,
        revisions_by_key: dict[tuple[str, str], ChannelTalkDocumentArticleRevisionView] | None = None,
    ) -> None:
        self._pages = list(pages)
        self._details_by_id = details_by_id or {}
        self._revisions_by_key = revisions_by_key or {}
        self.list_calls: list[dict[str, object]] = []
        self.batch_calls: list[tuple[str, ...]] = []
        self.revision_calls: list[tuple[str, str]] = []

    async def list_articles(
        self,
        *,
        language,
        state,
        since,
        limit,
        order,
    ) -> ChannelTalkDocumentArticlePage:
        self.list_calls.append(
            {
                "language": language,
                "state": state,
                "since": since,
                "limit": limit,
                "order": order,
            }
        )
        if not self._pages:
            return ChannelTalkDocumentArticlePage(articles=[])
        return self._pages.pop(0)

    async def batch_get_articles(
        self,
        *,
        article_ids,
        language,
    ) -> ChannelTalkDocumentArticleBatchResult:
        _ = language
        ids = tuple(article_ids)
        self.batch_calls.append(ids)
        return ChannelTalkDocumentArticleBatchResult(
            articles=[
                self._details_by_id[article_id]
                for article_id in ids
                if article_id in self._details_by_id
            ]
        )

    async def get_article_revision(
        self,
        *,
        article_id,
        revision_id,
    ) -> ChannelTalkDocumentArticleRevisionView:
        key = (article_id, revision_id)
        self.revision_calls.append(key)
        return self._revisions_by_key[key]


class ChannelTalkArticleFullSyncConnectionTests(IsolatedAsyncioTestCase):
    async def test_connection_is_created_from_document_credentials_record(self) -> None:
        connection = ChannelTalkArticleFullSyncConnection.from_credentials_record(
            _record(),
        )

        self.assertEqual(connection.channel_id, "channel-123")
        self.assertEqual(connection.space_id, "space-123")
        self.assertEqual(connection.access_key, "documents-key")
        self.assertEqual(connection.access_secret, "documents-secret")


class ChannelTalkArticleFullSyncFetcherTests(IsolatedAsyncioTestCase):
    async def test_fetch_articles_sweeps_all_article_states_and_preserves_state(
        self,
    ) -> None:
        published = _article(
            "published-1",
            state=ChannelTalkDocumentArticleState.PUBLISHED,
            updated_at=datetime(2026, 4, 21, 10, 0, tzinfo=timezone.utc),
            published_revision_id="revision-published-1",
        )
        unpublished = _article(
            "unpublished-1",
            state=ChannelTalkDocumentArticleState.UNPUBLISHED,
            updated_at=datetime(2026, 4, 21, 11, 0, tzinfo=timezone.utc),
        )
        draft = _article(
            "draft-1",
            state=ChannelTalkDocumentArticleState.DRAFT,
            updated_at=datetime(2026, 4, 21, 12, 0, tzinfo=timezone.utc),
        )
        client = _FakeDocumentsClient(
            pages=[
                ChannelTalkDocumentArticlePage(articles=[published]),
                ChannelTalkDocumentArticlePage(articles=[unpublished]),
                ChannelTalkDocumentArticlePage(articles=[draft]),
            ],
            details_by_id={
                article.article_id: article
                for article in [published, unpublished, draft]
            },
            revisions_by_key={
                ("published-1", "revision-published-1"): _revision("published-1"),
            },
        )
        fetcher = ChannelTalkArticleFullSyncFetcher(
            client_factory=lambda _connection: client,
        )

        result = await fetcher.fetch_articles(
            connection=_connection(),
            language="ko",
            sync_window=_window(),
        )

        self.assertEqual(
            [call["state"] for call in client.list_calls],
            [
                ChannelTalkDocumentArticleState.PUBLISHED,
                ChannelTalkDocumentArticleState.UNPUBLISHED,
                ChannelTalkDocumentArticleState.DRAFT,
            ],
        )
        self.assertEqual(
            result.article_ids,
            ("published-1", "unpublished-1", "draft-1"),
        )
        self.assertEqual(
            tuple(bundle.state for bundle in result.bundles),
            (
                ChannelTalkDocumentArticleState.PUBLISHED,
                ChannelTalkDocumentArticleState.UNPUBLISHED,
                ChannelTalkDocumentArticleState.DRAFT,
            ),
        )
        self.assertIsNotNone(result.bundles[0].published_revision)
        self.assertIsNone(result.bundles[1].published_revision)
        self.assertIsNone(result.bundles[2].published_revision)

    async def test_fetch_articles_fetches_published_revision_for_draft_current_article(
        self,
    ) -> None:
        listed = _article(
            "article-1",
            state=ChannelTalkDocumentArticleState.PUBLISHED,
            updated_at=datetime(2026, 4, 21, 10, 0, tzinfo=timezone.utc),
            published_revision_id="revision-published-1",
        )
        detailed = listed.model_copy(
            update={
                "state": ChannelTalkDocumentArticleState.DRAFT,
                "published_revision_id": "revision-published-1",
                "current_revision_id": "revision-current-1",
            }
        )
        client = _FakeDocumentsClient(
            pages=[ChannelTalkDocumentArticlePage(articles=[listed])],
            details_by_id={"article-1": detailed},
            revisions_by_key={
                ("article-1", "revision-published-1"): _revision("article-1"),
            },
        )
        fetcher = ChannelTalkArticleFullSyncFetcher(
            client_factory=lambda _connection: client,
        )

        result = await fetcher.fetch_articles(
            connection=_connection(),
            language="ko",
            sync_window=_window(),
        )

        self.assertEqual(
            client.revision_calls,
            [("article-1", "revision-published-1")],
        )
        self.assertEqual(
            result.bundles[0].published_revision.revision.title,
            "Published article-1",
        )

    async def test_fetch_articles_skips_revision_when_batch_article_is_published_source(
        self,
    ) -> None:
        listed = _article(
            "article-1",
            state=ChannelTalkDocumentArticleState.PUBLISHED,
            updated_at=datetime(2026, 4, 21, 10, 0, tzinfo=timezone.utc),
            published_revision_id="revision-published-1",
            current_revision_id="revision-published-1",
        )
        detailed = listed.model_copy(update={"title": "Published detail"})
        client = _FakeDocumentsClient(
            pages=[ChannelTalkDocumentArticlePage(articles=[listed])],
            details_by_id={"article-1": detailed},
        )
        fetcher = ChannelTalkArticleFullSyncFetcher(
            client_factory=lambda _connection: client,
        )

        result = await fetcher.fetch_articles(
            connection=_connection(),
            language="ko",
            sync_window=_window(),
        )

        self.assertEqual(client.revision_calls, [])
        self.assertIsNone(result.bundles[0].published_revision)
        self.assertEqual(result.bundles[0].detail.article.title, "Published detail")

    async def test_fetch_articles_fetches_only_mismatched_published_revisions(
        self,
    ) -> None:
        current_published = _article(
            "published-current",
            state=ChannelTalkDocumentArticleState.PUBLISHED,
            updated_at=datetime(2026, 4, 21, 10, 0, tzinfo=timezone.utc),
            published_revision_id="revision-current-published",
            current_revision_id="revision-current-published",
        )
        draft_with_published = _article(
            "draft-current",
            state=ChannelTalkDocumentArticleState.PUBLISHED,
            updated_at=datetime(2026, 4, 21, 11, 0, tzinfo=timezone.utc),
            published_revision_id="revision-published-old",
        )
        draft_detail = draft_with_published.model_copy(
            update={
                "state": ChannelTalkDocumentArticleState.DRAFT,
                "current_revision_id": "revision-draft-current",
            }
        )
        no_published = _article(
            "no-published",
            state=ChannelTalkDocumentArticleState.DRAFT,
            updated_at=datetime(2026, 4, 21, 12, 0, tzinfo=timezone.utc),
        )
        client = _FakeDocumentsClient(
            pages=[
                ChannelTalkDocumentArticlePage(
                    articles=[current_published, draft_with_published, no_published]
                )
            ],
            details_by_id={
                "published-current": current_published,
                "draft-current": draft_detail,
                "no-published": no_published,
            },
            revisions_by_key={
                ("draft-current", "revision-published-old"): _revision(
                    "draft-current",
                    revision_id="revision-published-old",
                ),
            },
        )
        fetcher = ChannelTalkArticleFullSyncFetcher(
            client_factory=lambda _connection: client,
        )

        result = await fetcher.fetch_articles(
            connection=_connection(),
            language="ko",
            sync_window=_window(),
        )

        self.assertEqual(
            client.revision_calls,
            [("draft-current", "revision-published-old")],
        )
        self.assertIsNone(result.bundles[0].published_revision)
        self.assertIsNotNone(result.bundles[1].published_revision)
        self.assertIsNone(result.bundles[2].published_revision)

    async def test_fetch_articles_batches_list_result_ids_for_details(self) -> None:
        listed = _article(
            "article-1",
            updated_at=datetime(2026, 4, 21, 10, 0, tzinfo=timezone.utc),
        )
        detailed = listed.model_copy(update={"title": "Detailed article"})
        client = _FakeDocumentsClient(
            pages=[ChannelTalkDocumentArticlePage(articles=[listed])],
            details_by_id={"article-1": detailed},
        )
        fetcher = ChannelTalkArticleFullSyncFetcher(
            client_factory=lambda _connection: client,
        )

        result = await fetcher.fetch_articles(
            connection=_connection(),
            language="ko",
            sync_window=_window(),
        )

        self.assertEqual(result.fetched_count, 1)
        self.assertEqual(result.article_ids, ("article-1",))
        self.assertEqual(client.batch_calls, [("article-1",)])
        self.assertEqual(result.bundles[0].detail.article.title, "Detailed article")

    async def test_fetch_articles_respects_batch_size_limit(self) -> None:
        article_ids = [f"article-{index}" for index in range(26)]
        articles = [_article(article_id) for article_id in article_ids]
        client = _FakeDocumentsClient(
            pages=[ChannelTalkDocumentArticlePage(articles=articles)],
            details_by_id={article.article_id: article for article in articles},
        )
        fetcher = ChannelTalkArticleFullSyncFetcher(
            client_factory=lambda _connection: client,
            page_limit=100,
        )

        result = await fetcher.fetch_articles(
            connection=_connection(),
            language="ko",
            sync_window=_window(),
        )

        self.assertEqual(result.fetched_count, 26)
        self.assertEqual([len(batch) for batch in client.batch_calls], [25, 1])

    async def test_fetch_articles_filters_articles_outside_sync_window(self) -> None:
        before = _article(
            "before",
            updated_at=datetime(2026, 4, 20, 23, 59, tzinfo=timezone.utc),
        )
        inside = _article(
            "inside",
            updated_at=datetime(2026, 4, 21, 12, 0, tzinfo=timezone.utc),
        )
        after = _article(
            "after",
            updated_at=datetime(2026, 4, 22, 0, 1, tzinfo=timezone.utc),
        )
        client = _FakeDocumentsClient(
            pages=[ChannelTalkDocumentArticlePage(articles=[before, inside, after])],
            details_by_id={
                article.article_id: article for article in [before, inside, after]
            },
        )
        fetcher = ChannelTalkArticleFullSyncFetcher(
            client_factory=lambda _connection: client,
        )

        result = await fetcher.fetch_articles(
            connection=_connection(),
            language="ko",
            sync_window=_window(),
        )

        self.assertEqual(result.article_ids, ("inside",))

    async def test_fetch_articles_falls_back_to_published_at_for_window(self) -> None:
        outside = _article(
            "outside",
            published_at=datetime(2026, 4, 20, 10, 0, tzinfo=timezone.utc),
        )
        inside = _article(
            "inside",
            published_at=datetime(2026, 4, 21, 10, 0, tzinfo=timezone.utc),
        )
        client = _FakeDocumentsClient(
            pages=[ChannelTalkDocumentArticlePage(articles=[outside, inside])],
            details_by_id={"outside": outside, "inside": inside},
        )
        fetcher = ChannelTalkArticleFullSyncFetcher(
            client_factory=lambda _connection: client,
        )

        result = await fetcher.fetch_articles(
            connection=_connection(),
            language="ko",
            sync_window=_window(),
        )

        self.assertEqual(result.article_ids, ("inside",))

    async def test_fetch_articles_keeps_article_without_timestamps(self) -> None:
        untimed = _article("untimed")
        client = _FakeDocumentsClient(
            pages=[ChannelTalkDocumentArticlePage(articles=[untimed])],
            details_by_id={"untimed": untimed},
        )
        fetcher = ChannelTalkArticleFullSyncFetcher(
            client_factory=lambda _connection: client,
        )

        result = await fetcher.fetch_articles(
            connection=_connection(),
            language="ko",
            sync_window=_window(),
        )

        self.assertEqual(result.article_ids, ("untimed",))

    async def test_fetch_articles_passes_and_returns_checkpoint_cursor(self) -> None:
        article = _article(
            "article-1",
            updated_at=datetime(2026, 4, 21, 10, 0, tzinfo=timezone.utc),
        )
        client = _FakeDocumentsClient(
            pages=[
                ChannelTalkDocumentArticlePage(
                    articles=[article],
                    next_page_token="cursor-2",
                )
            ],
            details_by_id={"article-1": article},
        )
        fetcher = ChannelTalkArticleFullSyncFetcher(
            client_factory=lambda _connection: client,
            max_article_pages_per_run=1,
        )

        result = await fetcher.fetch_articles(
            connection=_connection(),
            language="ko",
            sync_window=_window(),
            checkpoint_cursor="cursor-1",
        )

        self.assertEqual(client.list_calls[0]["since"], "cursor-1")
        self.assertEqual(
            result.next_checkpoint_state,
            ChannelTalkDocumentArticleState.PUBLISHED,
        )
        self.assertEqual(result.next_checkpoint_cursor, "cursor-2")

    async def test_fetch_articles_handles_empty_page_without_batch_call(self) -> None:
        client = _FakeDocumentsClient(
            pages=[ChannelTalkDocumentArticlePage(articles=[])],
        )
        fetcher = ChannelTalkArticleFullSyncFetcher(
            client_factory=lambda _connection: client,
        )

        result = await fetcher.fetch_articles(
            connection=_connection(),
            language="ko",
            sync_window=_window(),
        )

        self.assertEqual(result.fetched_count, 0)
        self.assertEqual(result.article_ids, ())
        self.assertEqual(client.batch_calls, [])

    async def test_fetch_articles_keeps_list_item_when_batch_detail_is_missing(self) -> None:
        article = _article(
            "article-1",
            updated_at=datetime(2026, 4, 21, 10, 0, tzinfo=timezone.utc),
        )
        client = _FakeDocumentsClient(
            pages=[ChannelTalkDocumentArticlePage(articles=[article])],
            details_by_id={},
        )
        fetcher = ChannelTalkArticleFullSyncFetcher(
            client_factory=lambda _connection: client,
        )

        result = await fetcher.fetch_articles(
            connection=_connection(),
            language="ko",
            sync_window=_window(),
        )

        self.assertEqual(result.article_ids, ("article-1",))
        self.assertIsNone(result.bundles[0].detail)
