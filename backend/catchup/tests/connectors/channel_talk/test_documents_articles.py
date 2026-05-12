from __future__ import annotations

from datetime import datetime
from datetime import timezone
from unittest import IsolatedAsyncioTestCase

import httpx

from catchup.connectors.channel_talk.document_space.client import (
    DEFAULT_ARTICLE_LIST_LIMIT,
)
from catchup.connectors.channel_talk.document_space.client import (
    ChannelTalkDocumentsApiClient,
)
from catchup.connectors.channel_talk.exceptions import ChannelTalkUpstreamError
from catchup.connectors.channel_talk.exceptions import ChannelTalkValidationError
from catchup.connectors.channel_talk.schemas.document_article import (
    ChannelTalkDocumentArticle,
)
from catchup.connectors.channel_talk.schemas.document_article import (
    ChannelTalkDocumentArticleBatch,
)
from catchup.connectors.channel_talk.schemas.document_article import (
    ChannelTalkDocumentArticleDetail,
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


def _article_payload() -> dict[str, object]:
    return {
        "id": "article-1",
        "spaceId": "space-123",
        "createdAt": 1776839445123,
        "updatedAt": 1776839545123,
        "state": "published",
        "publishedRevisionId": "revision-published-1",
        "publishedAt": 1776839645123,
        "currentRevisionId": "revision-current-1",
        "slug": "getting-started",
        "topicIds": ["topic-1", "topic-2"],
        "website": {"url": "https://help.example.com/articles/getting-started"},
        "authorId": "author-1",
        "name": "Getting started",
        "coverImageUrl": "https://cdn.example.com/cover.png",
        "title": "Getting started with CatchUp",
        "subtitle": "Install and configure the integration",
        "summary": "A short setup guide.",
        "body": "# Getting started\nInstall the integration.",
        "bodyHtml": "<h1>Getting started</h1><p>Install the integration.</p>",
    }


def _revision_payload() -> dict[str, object]:
    return {
        "id": "revision-published-1",
        "spaceId": "space-123",
        "articleId": "article-1",
        "language": "ko",
        "state": "published",
        "authorId": "author-1",
        "createdAt": 1776839445123,
        "updatedAt": 1776839545123,
        "title": "Published revision title",
        "summary": "Published revision summary.",
        "body": "# Published revision\nOnly public content.",
        "bodyHtml": "<h1>Published revision</h1><p>Only public content.</p>",
    }


class ChannelTalkDocumentsArticleSchemaTests(IsolatedAsyncioTestCase):
    async def test_article_parser_handles_epoch_milliseconds_and_content_fields(self) -> None:
        article = ChannelTalkDocumentArticle.from_api_payload(_article_payload())

        self.assertEqual(article.article_id, "article-1")
        self.assertEqual(article.space_id, "space-123")
        self.assertEqual(
            article.created_at,
            datetime.fromtimestamp(1776839445123 / 1000, tz=timezone.utc),
        )
        self.assertEqual(
            article.updated_at,
            datetime.fromtimestamp(1776839545123 / 1000, tz=timezone.utc),
        )
        self.assertEqual(article.state, "published")
        self.assertEqual(article.published_revision_id, "revision-published-1")
        self.assertEqual(
            article.published_at,
            datetime.fromtimestamp(1776839645123 / 1000, tz=timezone.utc),
        )
        self.assertEqual(article.current_revision_id, "revision-current-1")
        self.assertEqual(article.slug, "getting-started")
        self.assertEqual(article.topic_ids, ["topic-1", "topic-2"])
        self.assertEqual(
            article.website_url,
            "https://help.example.com/articles/getting-started",
        )
        self.assertEqual(article.author_id, "author-1")
        self.assertEqual(article.name, "Getting started")
        self.assertEqual(article.cover_image_url, "https://cdn.example.com/cover.png")
        self.assertEqual(article.title, "Getting started with CatchUp")
        self.assertEqual(article.subtitle, "Install and configure the integration")
        self.assertEqual(article.summary, "A short setup guide.")
        self.assertEqual(article.body, "# Getting started\nInstall the integration.")
        self.assertEqual(
            article.body_html,
            "<h1>Getting started</h1><p>Install the integration.</p>",
        )

    async def test_article_parser_preserves_block_body_payloads(self) -> None:
        blocks = [
            {
                "type": "paragraph",
                "children": [{"text": "Install the integration."}],
            }
        ]
        payload = _article_payload()
        payload["body"] = blocks

        article = ChannelTalkDocumentArticle.from_api_payload(payload)

        self.assertEqual(article.body, blocks)

    async def test_article_page_parser_returns_articles_cursor_and_related_payloads(self) -> None:
        page = ChannelTalkDocumentArticlePage.from_api_payload(
            {
                "articles": [_article_payload()],
                "articleCategories": [
                    {
                        "id": "category-1",
                        "name": "Guides",
                    }
                ],
                "authors": [
                    {
                        "id": "author-1",
                        "name": "Kim",
                    }
                ],
                "topics": [
                    {
                        "id": "topic-1",
                        "name": "Setup",
                    }
                ],
                "next": "cursor-2",
            }
        )

        self.assertEqual(page.next_page_token, "cursor-2")
        self.assertEqual(page.articles[0].article_id, "article-1")
        self.assertEqual(page.article_categories[0].article_category_id, "category-1")
        self.assertEqual(page.authors[0].author_id, "author-1")
        self.assertEqual(page.topics[0].topic_id, "topic-1")

    async def test_article_detail_parser_returns_article_and_related_payloads(self) -> None:
        detail = ChannelTalkDocumentArticleDetail.from_api_payload(
            {
                "article": _article_payload(),
                "articleCategory": {
                    "articleId": "article-1",
                    "category": {
                        "id": "category-1",
                        "name": {
                            "ko": "가이드",
                            "en": "Guides",
                        },
                    },
                },
                "author": {
                    "id": "author-1",
                    "profile": {
                        "ko": {
                            "name": "캐치업",
                        },
                        "en": {
                            "name": "CatchUp",
                        },
                    },
                },
                "topics": [
                    {
                        "id": "topic-1",
                        "name": {
                            "ko": "설정",
                            "en": "Setup",
                        },
                    }
                ],
            }
        )

        self.assertEqual(detail.article.article_id, "article-1")
        self.assertEqual(detail.article_category.article_category_id, "category-1")
        self.assertEqual(detail.article_category.article_id, "article-1")
        self.assertEqual(detail.article_category.name, "가이드")
        self.assertEqual(detail.article_category.localized_name["en"], "Guides")
        self.assertEqual(detail.author.author_id, "author-1")
        self.assertEqual(detail.author.name, "캐치업")
        self.assertEqual(detail.author.profile["en"]["name"], "CatchUp")
        self.assertEqual(detail.topics[0].topic_id, "topic-1")
        self.assertEqual(detail.topics[0].name, "설정")
        self.assertEqual(detail.topics[0].localized_name["en"], "Setup")

    async def test_article_batch_parser_returns_articles_and_related_payloads(self) -> None:
        batch = ChannelTalkDocumentArticleBatch.from_api_payload(
            {
                "articles": [_article_payload()],
                "articleCategories": [
                    {
                        "id": "category-1",
                        "name": "Guides",
                    }
                ],
                "authors": [
                    {
                        "id": "author-1",
                        "name": "Kim",
                    }
                ],
                "topics": [
                    {
                        "id": "topic-1",
                        "name": "Setup",
                    }
                ],
            }
        )

        self.assertEqual(batch.articles[0].article_id, "article-1")
        self.assertEqual(batch.article_categories[0].article_category_id, "category-1")
        self.assertEqual(batch.authors[0].author_id, "author-1")
        self.assertEqual(batch.topics[0].topic_id, "topic-1")

    async def test_article_revision_parser_keeps_revision_and_article_identity(
        self,
    ) -> None:
        view = ChannelTalkDocumentArticleRevisionView.from_api_payload(
            {
                "revision": _revision_payload(),
                "author": {
                    "id": "author-1",
                    "name": "Kim",
                },
            }
        )

        self.assertEqual(view.revision.revision_id, "revision-published-1")
        self.assertEqual(view.revision.article_id, "article-1")
        self.assertEqual(view.revision.state, "published")
        self.assertEqual(view.revision.title, "Published revision title")
        self.assertEqual(view.revision.body_html, "<h1>Published revision</h1><p>Only public content.</p>")
        self.assertEqual(view.author.author_id, "author-1")


class ChannelTalkDocumentsArticleClientTests(IsolatedAsyncioTestCase):
    async def test_list_articles_sends_filter_query_params(self) -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.url.path, "/open/v1/spaces/$me/articles")
            self.assertEqual(request.url.params["language"], "ko")
            self.assertEqual(request.url.params["state"], "published")
            self.assertEqual(request.url.params["topicId"], "topic-1")
            self.assertEqual(request.url.params["limit"], "25")
            self.assertEqual(request.url.params["since"], "cursor-1")
            self.assertEqual(request.url.params["order"], "desc")
            return httpx.Response(200, json={"articles": [], "next": "cursor-2"})

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
            client = ChannelTalkDocumentsApiClient(access_key="documents-key", access_secret="documents-secret", http_client=http_client)
            page = await client.list_articles(
                language="ko",
                state="published",
                topic_id="topic-1",
                limit=25,
                since="cursor-1",
                order="desc",
            )

        self.assertEqual(page.next_page_token, "cursor-2")

    async def test_list_articles_uses_sync_page_size_and_default_order(self) -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.url.path, "/open/v1/spaces/$me/articles")
            self.assertEqual(request.url.params["language"], "ko")
            self.assertEqual(request.url.params["limit"], str(DEFAULT_ARTICLE_LIST_LIMIT))
            self.assertEqual(request.url.params["order"], "asc")
            return httpx.Response(200, json={"articles": []})

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
            client = ChannelTalkDocumentsApiClient(access_key="documents-key", access_secret="documents-secret", http_client=http_client)
            page = await client.list_articles(
                language="ko",
            )

        self.assertEqual(page.articles, [])

    async def test_list_articles_accepts_draft_state(self) -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.url.params["state"], "draft")
            return httpx.Response(200, json={"articles": []})

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
            client = ChannelTalkDocumentsApiClient(access_key="documents-key", access_secret="documents-secret", http_client=http_client)
            await client.list_articles(
                language="ko",
                state=ChannelTalkDocumentArticleState.DRAFT,
            )

    async def test_get_article_uses_article_id_path_and_language_param(self) -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.url.path, "/open/v1/spaces/$me/articles/article-1")
            self.assertEqual(request.url.params["language"], "en")
            return httpx.Response(200, json={"article": _article_payload()})

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
            client = ChannelTalkDocumentsApiClient(access_key="documents-key", access_secret="documents-secret", http_client=http_client)
            detail = await client.get_article(
                article_id="article-1",
                language="en",
            )

        self.assertEqual(detail.article.article_id, "article-1")

    async def test_get_article_revision_uses_article_and_revision_path(self) -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(
                request.url.path,
                "/open/v1/spaces/$me/articles/article-1/revisions/revision-1",
            )
            return httpx.Response(200, json={"revision": _revision_payload()})

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
            client = ChannelTalkDocumentsApiClient(access_key="documents-key", access_secret="documents-secret", http_client=http_client)
            revision = await client.get_article_revision(
                article_id="article-1",
                revision_id="revision-1",
            )

        self.assertEqual(revision.revision.article_id, "article-1")

    async def test_batch_get_articles_sends_repeated_ids_and_language_param(self) -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.url.path, "/open/v1/spaces/$me/articles/batch")
            self.assertEqual(
                request.url.params.get_list("ids[]"),
                ["article-1", "article-2"],
            )
            self.assertEqual(request.url.params["language"], "ko")
            return httpx.Response(200, json={"articles": [_article_payload()]})

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
            client = ChannelTalkDocumentsApiClient(access_key="documents-key", access_secret="documents-secret", http_client=http_client)
            batch = await client.batch_get_articles(
                article_ids=["article-1", "article-2"],
                language="ko",
            )

        self.assertEqual(batch.articles[0].article_id, "article-1")

    async def test_upstream_error_message_exposes_status_and_response_body(
        self,
    ) -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                503,
                json={
                    "code": "maintenance",
                    "message": "documents service maintenance",
                },
            )

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
        ) as http_client:
            client = ChannelTalkDocumentsApiClient(
                access_key="documents-key",
                access_secret="documents-secret",
                http_client=http_client,
            )
            with self.assertRaises(ChannelTalkUpstreamError) as raised:
                await client.list_articles(language="ko")

        message = str(raised.exception)
        self.assertIn("upstream status 503", message)
        self.assertIn("documents service maintenance", message)

    async def test_batch_get_articles_rejects_plain_string_article_ids(self) -> None:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda request: httpx.Response(500))
        ) as http_client:
            client = ChannelTalkDocumentsApiClient(access_key="documents-key", access_secret="documents-secret", http_client=http_client)
            with self.assertRaises(ChannelTalkValidationError):
                await client.batch_get_articles(
                    article_ids="article-1",
                    language="ko",
                )

    async def test_list_articles_rejects_blank_language(self) -> None:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda request: httpx.Response(500))
        ) as http_client:
            client = ChannelTalkDocumentsApiClient(access_key="documents-key", access_secret="documents-secret", http_client=http_client)
            with self.assertRaises(ChannelTalkValidationError):
                await client.list_articles(
                    language=" ",
                )

    async def test_list_articles_rejects_invalid_order(self) -> None:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda request: httpx.Response(500))
        ) as http_client:
            client = ChannelTalkDocumentsApiClient(access_key="documents-key", access_secret="documents-secret", http_client=http_client)
            with self.assertRaises(ChannelTalkValidationError):
                await client.list_articles(
                    language="en",
                    order="newest",
                )

    async def test_list_articles_rejects_invalid_limit(self) -> None:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda request: httpx.Response(500))
        ) as http_client:
            client = ChannelTalkDocumentsApiClient(access_key="documents-key", access_secret="documents-secret", http_client=http_client)
            with self.assertRaises(ChannelTalkValidationError):
                await client.list_articles(
                    language="en",
                    limit=0,
                )

    async def test_get_article_rejects_blank_article_id(self) -> None:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda request: httpx.Response(500))
        ) as http_client:
            client = ChannelTalkDocumentsApiClient(access_key="documents-key", access_secret="documents-secret", http_client=http_client)
            with self.assertRaises(ChannelTalkValidationError):
                await client.get_article(
                    article_id=" ",
                    language="en",
                )

    async def test_batch_get_articles_rejects_more_than_25_article_ids(self) -> None:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda request: httpx.Response(500))
        ) as http_client:
            client = ChannelTalkDocumentsApiClient(access_key="documents-key", access_secret="documents-secret", http_client=http_client)
            with self.assertRaises(ChannelTalkValidationError):
                await client.batch_get_articles(
                    article_ids=[f"article-{index}" for index in range(26)],
                    language="en",
                )
