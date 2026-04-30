from __future__ import annotations

from datetime import datetime
from datetime import timezone
from unittest import IsolatedAsyncioTestCase

from catchup.connector_core.adapters.channel_talk.document_article_full_sync_adapter import (
    ChannelTalkDocumentArticleFullSyncAdapter,
)
from catchup.connector_core.adapters.channel_talk.document_article_full_sync_adapter import (
    ChannelTalkDocumentArticleFullSyncExecutionRequest,
)
from catchup.connector_core.adapters.channel_talk.document_article_full_sync_adapter import (
    ChannelTalkDocumentArticleFullSyncFetchResult,
)
from catchup.connector_core.ports.full_sync import FullSyncWindow
from catchup.connectors.channel_talk.document_article_full_sync_fetcher import (
    ChannelTalkFetchedDocumentArticle,
)
from catchup.connectors.channel_talk.schemas.channel_connection import (
    ChannelTalkCredentialsRecord,
)
from catchup.connectors.channel_talk.schemas.document_article import (
    ChannelTalkDocumentArticle,
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
from catchup.connectors.channel_talk.schemas.document_article import (
    ChannelTalkDocumentArticleView,
)
from catchup.connectors.channel_talk.schemas.document_connection import (
    ChannelTalkDocumentAssociationStatus,
)
from catchup.connectors.channel_talk.schemas.document_connection import (
    ChannelTalkDocumentCredentialsRecord,
)


def _window() -> FullSyncWindow:
    return FullSyncWindow(
        window_start=datetime(2026, 4, 21, 0, 0, tzinfo=timezone.utc),
        window_end=datetime(2026, 4, 22, 0, 0, tzinfo=timezone.utc),
    )


def _execution() -> ChannelTalkDocumentArticleFullSyncExecutionRequest:
    return ChannelTalkDocumentArticleFullSyncExecutionRequest(
        tenant_id="channel-123",
        channel_connection=ChannelTalkCredentialsRecord(
            channel_id="channel-123",
            channel_name="Support",
            access_key="access-key",
            access_secret="access-secret",
            webhook_token="webhook-token",
        ),
        document_connection=ChannelTalkDocumentCredentialsRecord(
            channel_id="channel-123",
            space_id="space-123",
            space_name="Help Center",
            access_key="documents-access-key",
            access_secret="documents-access-secret",
            association_status=ChannelTalkDocumentAssociationStatus.API_VERIFIED,
        ),
    )


def _article_view(
    *,
    article_id: str,
    state: ChannelTalkDocumentArticleState | str,
    body_html: str | None = None,
    body=None,
    title: str = "Refund policy",
    slug: str = "refund-policy",
    website_url: str | None = "https://docs.example.com/refund",
) -> ChannelTalkDocumentArticleView:
    article_payload = {
        "id": article_id,
        "spaceId": "space-123",
        "state": (
            state.value
            if isinstance(state, ChannelTalkDocumentArticleState)
            else state
        ),
        "title": title,
        "subtitle": "Customer refunds",
        "summary": "Refund summary",
        "slug": slug,
        "topicIds": ["topic-1"],
        "authorId": "author-1",
        "createdAt": "2026-04-21T09:00:00Z",
        "updatedAt": "2026-04-21T09:30:00Z",
        "publishedAt": "2026-04-21T10:00:00Z",
        "publishedRevisionId": "published-revision-1",
        "currentRevisionId": "current-revision-1",
    }
    if website_url is not None:
        article_payload["website"] = {"url": website_url}
    if body_html is not None:
        article_payload["bodyHtml"] = body_html
    if body is not None:
        article_payload["body"] = body
    return ChannelTalkDocumentArticleView.from_api_payload(
        {
            "article": article_payload,
            "articleCategory": {
                "id": "category-1",
                "name": "Billing",
            },
            "author": {
                "id": "author-1",
                "name": "Writer Kim",
            },
            "topics": [
                {
                    "id": "topic-1",
                    "name": "Payments",
                }
            ],
        }
    )


def _bundle(
    *,
    article_id: str,
    state: ChannelTalkDocumentArticleState | str,
    detail: ChannelTalkDocumentArticleView | None = None,
    list_body: str | None = None,
    published_revision: ChannelTalkDocumentArticleRevisionView | None = None,
) -> ChannelTalkFetchedDocumentArticle:
    list_item = ChannelTalkDocumentArticle(
        article_id=article_id,
        space_id="space-123",
        state=state,
        title="List fallback title",
        body=list_body,
        updated_at=datetime(2026, 4, 21, 9, 30, tzinfo=timezone.utc),
    )
    return ChannelTalkFetchedDocumentArticle(
        language="ko",
        state=state,
        list_item=list_item,
        detail=detail,
        published_revision=published_revision,
    )


def _revision_view(
    *,
    article_id: str,
    body_html: str | None = None,
    body=None,
    title: str = "Published refund policy",
) -> ChannelTalkDocumentArticleRevisionView:
    return ChannelTalkDocumentArticleRevisionView(
        revision=ChannelTalkDocumentArticleRevision(
            revision_id="published-revision-1",
            article_id=article_id,
            space_id="space-123",
            state=ChannelTalkDocumentArticleState.PUBLISHED,
            language="ko",
            author_id="author-1",
            title=title,
            subtitle="Published customer refunds",
            summary="Published refund summary",
            body=body,
            body_html=body_html,
            created_at=datetime(2026, 4, 21, 9, 0, tzinfo=timezone.utc),
            updated_at=datetime(2026, 4, 21, 9, 20, tzinfo=timezone.utc),
        )
    )


class _FakeArticleRepository:
    def __init__(self) -> None:
        self.initialized = False
        self.deleted_prefixes: list[str] = []
        self.added_documents = []
        self.added_ids: list[str] = []
        self.calls: list[str] = []

    def ensure_initialized(self) -> None:
        if not self.initialized:
            raise RuntimeError("not initialized")

    async def initialize(self, ensure_indices) -> None:
        _ = ensure_indices
        self.initialized = True
        self.calls.append("initialize")

    async def delete_by_id_prefix(self, prefix) -> None:
        self.deleted_prefixes.append(prefix)
        self.calls.append("delete")

    async def add_documents(self, documents, ids=None):
        self.added_documents.extend(documents)
        self.added_ids.extend(ids or [])
        self.calls.append("add")
        return ids or []


class ChannelTalkDocumentArticleFullSyncAdapterTests(IsolatedAsyncioTestCase):
    async def test_transform_prepares_only_published_revision_snapshots(
        self,
    ) -> None:
        adapter = ChannelTalkDocumentArticleFullSyncAdapter(language="ko")
        fetched = ChannelTalkDocumentArticleFullSyncFetchResult(
            channel_id="channel-123",
            space_id="space-123",
            language="ko",
            bundles=(
                _bundle(
                    article_id="published-1",
                    state=ChannelTalkDocumentArticleState.PUBLISHED,
                    detail=_article_view(
                        article_id="published-1",
                        state=ChannelTalkDocumentArticleState.PUBLISHED,
                        body_html="<p>Current content should not be used</p>",
                    ),
                    published_revision=_revision_view(
                        article_id="published-1",
                        body_html="<h1>Refunds</h1><p>Read <a href='https://example.com'>guide</a>.</p><script>track()</script>",
                    ),
                ),
                _bundle(
                    article_id="unpublished-1",
                    state=ChannelTalkDocumentArticleState.UNPUBLISHED,
                    detail=_article_view(
                        article_id="unpublished-1",
                        state=ChannelTalkDocumentArticleState.UNPUBLISHED,
                        body=[
                            {
                                "type": "paragraph",
                                "content": [
                                    {"text": "Hidden refund draft text"},
                                ],
                            }
                        ],
                    ),
                ),
                _bundle(
                    article_id="draft-1",
                    state=ChannelTalkDocumentArticleState.DRAFT,
                    detail=_article_view(
                        article_id="draft-1",
                        state=ChannelTalkDocumentArticleState.DRAFT,
                        body_html="<p>Draft current text should not be used</p>",
                    ),
                    published_revision=_revision_view(
                        article_id="draft-1",
                        body_html="<p>Previously published text</p>",
                    ),
                ),
            ),
            fetched_count=3,
            fetched_article_ids=("published-1", "unpublished-1", "draft-1"),
        )

        transformed = await adapter.transform(
            execution=_execution(),
            sync_window=_window(),
            fetched=fetched,
        )

        self.assertEqual(len(transformed.documents), 2)
        states = [
            document.storage_metadata["document_article_core"]["article"]["state"]
            for document in transformed.documents
        ]
        self.assertEqual(states, ["published", "published"])
        for document in transformed.documents:
            self.assertNotIn("[Channel Talk Document Article]", document.page_content)
            self.assertNotIn("Document State:", document.page_content)
            self.assertNotIn("State Meaning:", document.page_content)
            self.assertNotIn("Space:", document.page_content)
            self.assertNotIn("Language:", document.page_content)
            self.assertNotIn("state", document.storage_metadata)
            self.assertNotIn("article_state", document.storage_metadata)
            self.assertNotIn("publication", document.storage_metadata)
            self.assertNotIn("chunk", document.storage_metadata)
            self.assertIn("document_article_core", document.storage_metadata)
            article_core = document.storage_metadata["document_article_core"]
            self.assertIn("article", article_core)
            self.assertIn("space", article_core)
            self.assertIn("author", article_core)
            self.assertIn("taxonomy", article_core)
            self.assertIn("publication", article_core)
            self.assertIn("chunk", article_core)
            self.assertNotIn(
                "summary",
                article_core["article"],
            )
        self.assertIn("Refunds", transformed.documents[0].page_content)
        self.assertIn(
            "guide (https://example.com)",
            transformed.documents[0].page_content,
        )
        self.assertNotIn("track()", transformed.documents[0].page_content)
        self.assertNotIn("Hidden refund draft text", transformed.documents[0].page_content)
        self.assertIn(
            "Previously published text",
            transformed.documents[1].page_content,
        )
        self.assertNotIn("Draft current text should not be used", transformed.documents[1].page_content)
        self.assertEqual(
            transformed.delete_prefixes,
            (
                "channel_talk:document_article:channel-123:space-123:ko:published-1:chunk:",
                "channel_talk:document_article:channel-123:space-123:ko:unpublished-1:chunk:",
                "channel_talk:document_article:channel-123:space-123:ko:draft-1:chunk:",
            ),
        )

    async def test_transform_splits_long_body_with_deterministic_chunk_ids(
        self,
    ) -> None:
        adapter = ChannelTalkDocumentArticleFullSyncAdapter(language="ko")
        long_body = "\n\n".join(f"paragraph {index} " + ("x" * 220) for index in range(40))
        fetched = ChannelTalkDocumentArticleFullSyncFetchResult(
            channel_id="channel-123",
            space_id="space-123",
            language="ko",
            bundles=(
                _bundle(
                    article_id="long-1",
                    state=ChannelTalkDocumentArticleState.PUBLISHED,
                    detail=_article_view(
                        article_id="long-1",
                        state=ChannelTalkDocumentArticleState.PUBLISHED,
                        body="Current body should not be used",
                    ),
                    published_revision=_revision_view(
                        article_id="long-1",
                        body=long_body,
                    ),
                ),
            ),
            fetched_count=1,
            fetched_article_ids=("long-1",),
        )

        transformed = await adapter.transform(
            execution=_execution(),
            sync_window=_window(),
            fetched=fetched,
        )

        self.assertGreater(len(transformed.documents), 1)
        self.assertEqual(
            transformed.delete_prefixes,
            (
                "channel_talk:document_article:channel-123:space-123:ko:long-1:chunk:",
            ),
        )
        for index, document in enumerate(transformed.documents):
            self.assertEqual(
                document.document_id,
                "channel_talk:document_article:"
                f"channel-123:space-123:ko:long-1:chunk:{index}",
            )
            article_core = document.storage_metadata["document_article_core"]
            self.assertEqual(article_core["chunk"]["chunk_index"], index)
            self.assertEqual(
                article_core["chunk"]["chunk_count"],
                len(transformed.documents),
            )

    async def test_transform_preserves_html_heading_hierarchy_in_chunk_context(
        self,
    ) -> None:
        adapter = ChannelTalkDocumentArticleFullSyncAdapter(language="ko")
        body_html = """
        <h1>Install Catch Up</h1>
        <p>Invite the app to the Slack channel before asking questions.</p>
        <p>Use mentions in a thread when the discussion needs context.</p>
        <h2>Troubleshooting</h2>
        <p>Check whether the source document has already been indexed.</p>
        <p>Share the exact Slack channel and question when reporting feedback.</p>
        """
        fetched = ChannelTalkDocumentArticleFullSyncFetchResult(
            channel_id="channel-123",
            space_id="space-123",
            language="ko",
            bundles=(
                _bundle(
                    article_id="heading-1",
                    state=ChannelTalkDocumentArticleState.PUBLISHED,
                    detail=_article_view(
                        article_id="heading-1",
                        state=ChannelTalkDocumentArticleState.PUBLISHED,
                        body_html="<p>Current body should not be used</p>",
                    ),
                    published_revision=_revision_view(
                        article_id="heading-1",
                        body_html=body_html,
                    ),
                ),
            ),
            fetched_count=1,
            fetched_article_ids=("heading-1",),
        )

        transformed = await adapter.transform(
            execution=_execution(),
            sync_window=_window(),
            fetched=fetched,
        )

        rendered = "\n\n".join(
            document.page_content for document in transformed.documents
        )
        self.assertIn("Published refund policy - Install Catch Up", rendered)
        self.assertIn(
            "Published refund policy - Install Catch Up > Troubleshooting",
            rendered,
        )
        self.assertNotIn("[Section:", rendered)
        self.assertNotIn("\n\nInstall Catch Up\n\n", rendered)
        self.assertNotIn("\n\nTroubleshooting\n\n", rendered)
        self.assertNotIn("# Install Catch Up", rendered)

    async def test_transform_uses_title_section_heading_without_duplicate_section_name(
        self,
    ) -> None:
        adapter = ChannelTalkDocumentArticleFullSyncAdapter(language="ko")
        body_html = """
        <h1>나에게 맞는 답변 만들기</h1>
        <h2>마무리</h2>
        <p>프롬프트 빌더는 한 번 설정해두면 Catch Up이 점점 당신의 동료처럼 느껴지게 만드는 기능입니다.</p>
        """
        fetched = ChannelTalkDocumentArticleFullSyncFetchResult(
            channel_id="channel-123",
            space_id="space-123",
            language="ko",
            bundles=(
                _bundle(
                    article_id="closing-1",
                    state=ChannelTalkDocumentArticleState.PUBLISHED,
                    detail=_article_view(
                        article_id="closing-1",
                        state=ChannelTalkDocumentArticleState.PUBLISHED,
                        body_html="<p>Current body should not be used</p>",
                        title="나에게 맞는 답변 만들기",
                    ),
                    published_revision=_revision_view(
                        article_id="closing-1",
                        body_html=body_html,
                        title="나에게 맞는 답변 만들기",
                    ),
                ),
            ),
            fetched_count=1,
            fetched_article_ids=("closing-1",),
        )

        transformed = await adapter.transform(
            execution=_execution(),
            sync_window=_window(),
            fetched=fetched,
        )

        self.assertEqual(len(transformed.documents), 1)
        page_content = transformed.documents[0].page_content
        self.assertTrue(
            page_content.startswith(
                "나에게 맞는 답변 만들기 - 마무리\n\n프롬프트 빌더는"
            )
        )
        self.assertNotIn("[Channel Talk Document Article]", page_content)
        self.assertNotIn("Document State:", page_content)
        self.assertNotIn("State Meaning:", page_content)
        self.assertNotIn("Space:", page_content)
        self.assertNotIn("Language:", page_content)
        self.assertNotIn("[Section:", page_content)
        self.assertNotIn("\n\n마무리\n\n", page_content)

    async def test_transform_preserves_later_section_heading_when_sections_merge(
        self,
    ) -> None:
        adapter = ChannelTalkDocumentArticleFullSyncAdapter(language="ko")
        body_html = """
        <h1>흩어진 사내 정보를 한 번에 찾기</h1>
        <h2>답변을 받으면 이렇게 활용해요</h2>
        <p>출처 카드를 열어 답변의 근거를 확인할 수 있어요.</p>
        <h2>답변이 아쉬울 땐 이렇게 고쳐보세요</h2>
        <p>질문에 프로젝트명과 시점을 더해 다시 물어보세요.</p>
        """
        fetched = ChannelTalkDocumentArticleFullSyncFetchResult(
            channel_id="channel-123",
            space_id="space-123",
            language="ko",
            bundles=(
                _bundle(
                    article_id="merged-sections-1",
                    state=ChannelTalkDocumentArticleState.DRAFT,
                    detail=_article_view(
                        article_id="merged-sections-1",
                        state=ChannelTalkDocumentArticleState.DRAFT,
                        body_html="<p>Current body should not be used</p>",
                        title="흩어진 사내 정보를 한 번에 찾기",
                    ),
                    published_revision=_revision_view(
                        article_id="merged-sections-1",
                        body_html=body_html,
                        title="흩어진 사내 정보를 한 번에 찾기",
                    ),
                ),
            ),
            fetched_count=1,
            fetched_article_ids=("merged-sections-1",),
        )

        transformed = await adapter.transform(
            execution=_execution(),
            sync_window=_window(),
            fetched=fetched,
        )

        self.assertEqual(len(transformed.documents), 1)
        page_content = transformed.documents[0].page_content
        self.assertTrue(
            page_content.startswith(
                "흩어진 사내 정보를 한 번에 찾기 - 답변을 받으면 이렇게 활용해요"
            )
        )
        self.assertNotIn("\n\n답변을 받으면 이렇게 활용해요\n\n", page_content)
        self.assertIn(
            "\n\n답변이 아쉬울 땐 이렇게 고쳐보세요\n\n",
            page_content,
        )

    async def test_transform_stores_public_article_url_from_website_url(
        self,
    ) -> None:
        adapter = ChannelTalkDocumentArticleFullSyncAdapter(language="ko")
        fetched = ChannelTalkDocumentArticleFullSyncFetchResult(
            channel_id="channel-123",
            space_id="space-123",
            language="ko",
            bundles=(
                _bundle(
                    article_id="public-url-1",
                    state=ChannelTalkDocumentArticleState.PUBLISHED,
                    detail=_article_view(
                        article_id="public-url-1",
                        state=ChannelTalkDocumentArticleState.PUBLISHED,
                        body_html="<p>Published body</p>",
                        website_url=(
                            "https://guide.catchup.im/ko/articles/"
                            "%ED%9D%A9%EC%96%B4%EC%A7%84-%EC%82%AC%EB%82%B4-23bb29b0"
                        ),
                    ),
                    published_revision=_revision_view(
                        article_id="public-url-1",
                        body_html="<p>Published body</p>",
                    ),
                ),
            ),
            fetched_count=1,
            fetched_article_ids=("public-url-1",),
        )

        transformed = await adapter.transform(
            execution=_execution(),
            sync_window=_window(),
            fetched=fetched,
        )

        storage_metadata = transformed.documents[0].storage_metadata
        self.assertEqual(
            storage_metadata["url"],
            "https://guide.catchup.im/ko/articles/"
            "%ED%9D%A9%EC%96%B4%EC%A7%84-%EC%82%AC%EB%82%B4-23bb29b0",
        )
        self.assertEqual(
            storage_metadata["document_article_core"]["article"]["url"],
            storage_metadata["url"],
        )

    async def test_transform_builds_public_article_url_from_slug_when_missing(
        self,
    ) -> None:
        adapter = ChannelTalkDocumentArticleFullSyncAdapter(language="ko")
        fetched = ChannelTalkDocumentArticleFullSyncFetchResult(
            channel_id="channel-123",
            space_id="space-123",
            language="ko",
            bundles=(
                _bundle(
                    article_id="slug-url-1",
                    state=ChannelTalkDocumentArticleState.PUBLISHED,
                    detail=_article_view(
                        article_id="slug-url-1",
                        state=ChannelTalkDocumentArticleState.PUBLISHED,
                        body_html="<p>Published body</p>",
                        slug="흩어진-사내-정보를-한-번에-찾기-23bb29b0",
                        website_url=None,
                    ),
                    published_revision=_revision_view(
                        article_id="slug-url-1",
                        body_html="<p>Published body</p>",
                    ),
                ),
            ),
            fetched_count=1,
            fetched_article_ids=("slug-url-1",),
        )

        transformed = await adapter.transform(
            execution=_execution(),
            sync_window=_window(),
            fetched=fetched,
        )

        self.assertEqual(
            transformed.documents[0].storage_metadata["url"],
            "https://guide.catchup.im/ko/articles/"
            "%ED%9D%A9%EC%96%B4%EC%A7%84-%EC%82%AC%EB%82%B4-"
            "%EC%A0%95%EB%B3%B4%EB%A5%BC-%ED%95%9C-%EB%B2%88%EC%97%90-"
            "%EC%B0%BE%EA%B8%B0-23bb29b0",
        )

    async def test_transform_builds_public_article_url_from_short_slug_and_title(
        self,
    ) -> None:
        adapter = ChannelTalkDocumentArticleFullSyncAdapter(language="ko")
        fetched = ChannelTalkDocumentArticleFullSyncFetchResult(
            channel_id="channel-123",
            space_id="space-123",
            language="ko",
            bundles=(
                _bundle(
                    article_id="short-slug-url-1",
                    state=ChannelTalkDocumentArticleState.PUBLISHED,
                    detail=_article_view(
                        article_id="short-slug-url-1",
                        state=ChannelTalkDocumentArticleState.PUBLISHED,
                        body_html="<p>Published body</p>",
                        title="나에게 맞는 답변 만들기",
                        slug="69e7c182",
                        website_url=None,
                    ),
                    published_revision=_revision_view(
                        article_id="short-slug-url-1",
                        body_html="<p>Published body</p>",
                        title="나에게 맞는 답변 만들기",
                    ),
                ),
            ),
            fetched_count=1,
            fetched_article_ids=("short-slug-url-1",),
        )

        transformed = await adapter.transform(
            execution=_execution(),
            sync_window=_window(),
            fetched=fetched,
        )

        self.assertEqual(
            transformed.documents[0].storage_metadata["url"],
            "https://guide.catchup.im/ko/articles/"
            "%EB%82%98%EC%97%90%EA%B2%8C-%EB%A7%9E%EB%8A%94-"
            "%EB%8B%B5%EB%B3%80-%EB%A7%8C%EB%93%A4%EA%B8%B0-69e7c182",
        )

    async def test_transform_keeps_heading_icon_alt_text_in_chunk_body(
        self,
    ) -> None:
        adapter = ChannelTalkDocumentArticleFullSyncAdapter(language="ko")
        body_html = """
        <h1>Catch Up - Slack에서 사용해보세요</h1>
        <h2><img alt="bulb" /> Catch Up 팀은 이렇게 쓰고 있어요</h2>
        <p>저희 팀에서 가장 많이 쓰는 순간은 '논의 중간' 입니다.</p>
        """
        fetched = ChannelTalkDocumentArticleFullSyncFetchResult(
            channel_id="channel-123",
            space_id="space-123",
            language="ko",
            bundles=(
                _bundle(
                    article_id="icon-heading-1",
                    state=ChannelTalkDocumentArticleState.DRAFT,
                    detail=_article_view(
                        article_id="icon-heading-1",
                        state=ChannelTalkDocumentArticleState.DRAFT,
                        body_html="<p>Current body should not be used</p>",
                    ),
                    published_revision=_revision_view(
                        article_id="icon-heading-1",
                        body_html=body_html,
                    ),
                ),
            ),
            fetched_count=1,
            fetched_article_ids=("icon-heading-1",),
        )

        transformed = await adapter.transform(
            execution=_execution(),
            sync_window=_window(),
            fetched=fetched,
        )

        rendered = "\n\n".join(
            document.page_content for document in transformed.documents
        )
        self.assertIn(
            "Published refund policy - Catch Up - Slack에서 사용해보세요 > bulb Catch Up 팀은 이렇게 쓰고 있어요",
            rendered,
        )
        self.assertNotIn("\n\nbulb Catch Up 팀은 이렇게 쓰고 있어요\n\n", rendered)
        self.assertIn("저희 팀에서 가장 많이 쓰는 순간은", rendered)

    async def test_transform_preserves_structured_rich_blocks(self) -> None:
        adapter = ChannelTalkDocumentArticleFullSyncAdapter(language="ko")
        body = [
            {
                "type": "heading",
                "attrs": {"level": 1},
                "content": [{"type": "plain", "attrs": {"text": "Rich content"}}],
            },
            {
                "type": "image",
                "attrs": {
                    "alt": "logo.jpg",
                    "caption": {
                        "type": "text",
                        "content": [
                            {"type": "plain", "attrs": {"text": "회사 로고"}},
                        ],
                    },
                    "mime": "image/jpeg",
                    "src": "https://cdn.example.com/logo.jpg",
                },
            },
            {
                "type": "video",
                "attrs": {
                    "alt": "demo.mp4",
                    "caption": {
                        "type": "text",
                        "content": [
                            {"type": "plain", "attrs": {"text": "사용 방법 영상"}},
                        ],
                    },
                },
            },
            {
                "type": "table",
                "content": [
                    {
                        "type": "tableRow",
                        "content": [
                            {
                                "type": "tableHeaderCell",
                                "content": [
                                    {
                                        "type": "text",
                                        "content": [
                                            {"type": "plain", "attrs": {"text": "상황"}},
                                        ],
                                    }
                                ],
                            },
                            {
                                "type": "tableHeaderCell",
                                "content": [
                                    {
                                        "type": "text",
                                        "content": [
                                            {"type": "plain", "attrs": {"text": "예시"}},
                                        ],
                                    }
                                ],
                            },
                        ],
                    },
                    {
                        "type": "tableRow",
                        "content": [
                            {
                                "type": "tableCell",
                                "content": [
                                    {
                                        "type": "text",
                                        "content": [
                                            {"type": "plain", "attrs": {"text": "논의"}},
                                        ],
                                    }
                                ],
                            },
                            {
                                "type": "tableCell",
                                "content": [
                                    {
                                        "type": "text",
                                        "content": [
                                            {"type": "plain", "attrs": {"text": "요약"}},
                                        ],
                                    }
                                ],
                            },
                        ],
                    },
                ],
            },
            {
                "type": "text",
                "content": [
                    {
                        "type": "plain",
                        "attrs": {"text": "가이드"},
                        "marks": [
                            {
                                "type": "link",
                                "attrs": {"href": "https://example.com/guide"},
                            }
                        ],
                    }
                ],
            },
            {
                "type": "embed",
                "attrs": {
                    "mime": "text/html",
                    "src": "https://app.arcade.software/share/demo",
                },
            },
            {
                "type": "file",
                "attrs": {
                    "name": "guide.pdf",
                    "mime": "application/pdf",
                    "src": "https://cdn.example.com/guide.pdf",
                },
            },
        ]
        fetched = ChannelTalkDocumentArticleFullSyncFetchResult(
            channel_id="channel-123",
            space_id="space-123",
            language="ko",
            bundles=(
                _bundle(
                    article_id="rich-1",
                    state=ChannelTalkDocumentArticleState.PUBLISHED,
                    detail=_article_view(
                        article_id="rich-1",
                        state=ChannelTalkDocumentArticleState.PUBLISHED,
                        body_html="<p>Current body should not be used</p>",
                    ),
                    published_revision=_revision_view(
                        article_id="rich-1",
                        body=body,
                        body_html="<p>HTML fallback should not win</p>",
                    ),
                ),
            ),
            fetched_count=1,
            fetched_article_ids=("rich-1",),
        )

        transformed = await adapter.transform(
            execution=_execution(),
            sync_window=_window(),
            fetched=fetched,
        )

        rendered = "\n\n".join(
            document.contextual_content for document in transformed.documents
        )
        self.assertIn("[Image] logo.jpg", rendered)
        self.assertIn("Caption: 회사 로고", rendered)
        self.assertIn("[Video] demo.mp4", rendered)
        self.assertIn("Caption: 사용 방법 영상", rendered)
        self.assertIn("| 상황 | 예시 |", rendered)
        self.assertIn("| --- | --- |", rendered)
        self.assertIn("| 논의 | 요약 |", rendered)
        self.assertIn("가이드 (https://example.com/guide)", rendered)
        self.assertIn("Embed (https://app.arcade.software/share/demo)", rendered)
        self.assertIn("guide.pdf [파일 첨부]", rendered)
        self.assertNotIn("HTML fallback should not win", rendered)

    async def test_transform_preserves_html_table_media_and_file_fallback(
        self,
    ) -> None:
        adapter = ChannelTalkDocumentArticleFullSyncAdapter(language="ko")
        body_html = """
        <h1>HTML content</h1>
        <figure>
          <img src="https://cdn.example.com/logo.jpg" alt="logo.jpg" />
          <figcaption>회사 로고</figcaption>
        </figure>
        <table>
          <tr><th>상황</th><th>예시</th></tr>
          <tr><td>질문</td><td>답변</td></tr>
        </table>
        <a href="https://example.com">문서</a>
        <a data-node-type="embed" href="https://app.arcade.software/share/demo">https://app.arcade.software/share/demo</a>
        <a data-node-type="file" href="https://cdn.example.com/guide.pdf">guide.pdf</a>
        """
        fetched = ChannelTalkDocumentArticleFullSyncFetchResult(
            channel_id="channel-123",
            space_id="space-123",
            language="ko",
            bundles=(
                _bundle(
                    article_id="html-rich-1",
                    state=ChannelTalkDocumentArticleState.PUBLISHED,
                    detail=_article_view(
                        article_id="html-rich-1",
                        state=ChannelTalkDocumentArticleState.PUBLISHED,
                    ),
                    published_revision=_revision_view(
                        article_id="html-rich-1",
                        body_html=body_html,
                    ),
                ),
            ),
            fetched_count=1,
            fetched_article_ids=("html-rich-1",),
        )

        transformed = await adapter.transform(
            execution=_execution(),
            sync_window=_window(),
            fetched=fetched,
        )

        rendered = "\n\n".join(
            document.contextual_content for document in transformed.documents
        )
        self.assertIn("[Image] logo.jpg", rendered)
        self.assertIn("Caption: 회사 로고", rendered)
        self.assertIn("| 상황 | 예시 |", rendered)
        self.assertIn("| 질문 | 답변 |", rendered)
        self.assertIn("문서 (https://example.com)", rendered)
        self.assertIn("Embed (https://app.arcade.software/share/demo)", rendered)
        self.assertIn("guide.pdf [파일 첨부]", rendered)

    async def test_transform_skips_article_without_published_revision(self) -> None:
        adapter = ChannelTalkDocumentArticleFullSyncAdapter(language="ko")
        fetched = ChannelTalkDocumentArticleFullSyncFetchResult(
            channel_id="channel-123",
            space_id="space-123",
            language="ko",
            bundles=(
                _bundle(
                    article_id="list-only-1",
                    state="archived-preview",
                    detail=None,
                    list_body="List item body only",
                ),
            ),
            fetched_count=1,
            fetched_article_ids=("list-only-1",),
        )

        transformed = await adapter.transform(
            execution=_execution(),
            sync_window=_window(),
            fetched=fetched,
        )

        self.assertEqual(len(transformed.documents), 0)
        self.assertEqual(
            transformed.delete_prefixes,
            (
                "channel_talk:document_article:channel-123:space-123:ko:list-only-1:chunk:",
            ),
        )

    async def test_persist_deletes_article_prefixes_before_adding_chunks(self) -> None:
        repository = _FakeArticleRepository()
        adapter = ChannelTalkDocumentArticleFullSyncAdapter(
            language="ko",
            repository_factory=lambda: repository,
        )
        fetched = ChannelTalkDocumentArticleFullSyncFetchResult(
            channel_id="channel-123",
            space_id="space-123",
            language="ko",
            bundles=(
                _bundle(
                    article_id="persist-1",
                    state=ChannelTalkDocumentArticleState.DRAFT,
                    detail=_article_view(
                        article_id="persist-1",
                        state=ChannelTalkDocumentArticleState.DRAFT,
                        body_html="<p>Do not persist current draft</p>",
                    ),
                    published_revision=_revision_view(
                        article_id="persist-1",
                        body_html="<p>Persist published revision</p>",
                    ),
                ),
            ),
            fetched_count=1,
            fetched_article_ids=("persist-1",),
        )
        transformed = await adapter.transform(
            execution=_execution(),
            sync_window=_window(),
            fetched=fetched,
        )
        summary = await adapter.summarize(
            execution=_execution(),
            sync_window=_window(),
            transformed=transformed,
        )

        persisted = await adapter.persist(
            execution=_execution(),
            sync_window=_window(),
            transformed=transformed,
            summary=summary,
        )

        self.assertEqual(repository.calls, ["initialize", "delete", "add"])
        self.assertEqual(repository.deleted_prefixes, list(transformed.delete_prefixes))
        self.assertEqual(repository.added_ids, list(transformed.prepared_document_ids))
        self.assertEqual(persisted.persisted_count, len(transformed.documents))
        self.assertEqual(persisted.persisted_ids, transformed.prepared_document_ids)
        self.assertEqual(persisted.deleted_prefixes, transformed.delete_prefixes)
        self.assertEqual(summary.document_count, len(transformed.documents))

    async def test_persist_deletes_prefix_without_add_when_no_published_revision(
        self,
    ) -> None:
        repository = _FakeArticleRepository()
        adapter = ChannelTalkDocumentArticleFullSyncAdapter(
            language="ko",
            repository_factory=lambda: repository,
        )
        fetched = ChannelTalkDocumentArticleFullSyncFetchResult(
            channel_id="channel-123",
            space_id="space-123",
            language="ko",
            bundles=(
                _bundle(
                    article_id="stale-1",
                    state=ChannelTalkDocumentArticleState.UNPUBLISHED,
                    detail=_article_view(
                        article_id="stale-1",
                        state=ChannelTalkDocumentArticleState.UNPUBLISHED,
                        body_html="<p>Unpublished body</p>",
                    ),
                ),
            ),
            fetched_count=1,
            fetched_article_ids=("stale-1",),
        )
        transformed = await adapter.transform(
            execution=_execution(),
            sync_window=_window(),
            fetched=fetched,
        )
        summary = await adapter.summarize(
            execution=_execution(),
            sync_window=_window(),
            transformed=transformed,
        )

        persisted = await adapter.persist(
            execution=_execution(),
            sync_window=_window(),
            transformed=transformed,
            summary=summary,
        )

        self.assertEqual(repository.calls, ["initialize", "delete"])
        self.assertEqual(persisted.persisted_count, 0)
        self.assertEqual(persisted.deleted_prefixes, transformed.delete_prefixes)

    async def test_build_result_counts_prepared_documents(self) -> None:
        repository = _FakeArticleRepository()
        adapter = ChannelTalkDocumentArticleFullSyncAdapter(
            language="ko",
            repository_factory=lambda: repository,
        )
        execution = _execution()
        fetched = ChannelTalkDocumentArticleFullSyncFetchResult(
            channel_id="channel-123",
            space_id="space-123",
            language="ko",
            bundles=(
                _bundle(
                    article_id="count-1",
                    state=ChannelTalkDocumentArticleState.PUBLISHED,
                    detail=_article_view(
                        article_id="count-1",
                        state=ChannelTalkDocumentArticleState.PUBLISHED,
                        body_html="<p>Current body should not be used</p>",
                    ),
                    published_revision=_revision_view(
                        article_id="count-1",
                        body_html="<p>Count me</p>",
                    ),
                ),
            ),
            fetched_count=1,
            fetched_article_ids=("count-1",),
        )
        transformed = await adapter.transform(
            execution=execution,
            sync_window=_window(),
            fetched=fetched,
        )
        summary = await adapter.summarize(
            execution=execution,
            sync_window=_window(),
            transformed=transformed,
        )

        result = adapter.build_result(
            execution=execution,
            sync_window=_window(),
            fetched=fetched,
            transformed=transformed,
            summary=summary,
            persisted=await adapter.persist(
                execution=execution,
                sync_window=_window(),
                transformed=transformed,
                summary=summary,
            ),
        )

        self.assertEqual(result.document_count, len(transformed.documents))
