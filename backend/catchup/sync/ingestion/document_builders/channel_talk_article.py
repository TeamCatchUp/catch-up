from __future__ import annotations

import re
from typing import Protocol
from typing import TypeAlias
from urllib.parse import quote
from urllib.parse import unquote

from catchup.connectors.channel_talk.document_space.article_chunker import (
    ArticleChunker,
)
from catchup.connectors.channel_talk.document_space.article_content_normalizer import (
    ArticleContentNormalizer,
)
from catchup.connectors.channel_talk.document_space.article_ids import (
    build_article_delete_prefix,
)
from catchup.connectors.channel_talk.document_space.article_ids import (
    build_article_document_id,
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
from catchup.sync.ingestion.adapters.channel_talk.article_models import (
    ArticleBuildResult,
)
from catchup.sync.ingestion.adapters.channel_talk.article_models import (
    ArticlePreparedDocumentPayload,
)
from catchup.sync.ingestion.adapters.channel_talk.article_models import (
    ChannelTalkFetchedArticle,
)
from catchup.sync.ingestion.document_format import (
    ChannelTalkDocumentArticleArticleMetadata,
)
from catchup.sync.ingestion.document_format import (
    ChannelTalkDocumentArticleAuthorMetadata,
)
from catchup.sync.ingestion.document_format import (
    ChannelTalkDocumentArticleChunkMetadata,
)
from catchup.sync.ingestion.document_format import (
    ChannelTalkDocumentArticleCoreMetadata,
)
from catchup.sync.ingestion.document_format import (
    ChannelTalkDocumentArticleLogicalMetadata,
)
from catchup.sync.ingestion.document_format import (
    ChannelTalkDocumentArticlePublicationMetadata,
)
from catchup.sync.ingestion.document_format import (
    ChannelTalkDocumentArticleSpaceMetadata,
)
from catchup.sync.ingestion.document_format import (
    ChannelTalkDocumentArticleTaxonomyMetadata,
)
from catchup.sync.ingestion.document_format import DocumentBaseMetadata
from catchup.sync.ingestion.schemas import SyncWindow
from catchup.utils.validation import require_text

ARTICLE_PUBLIC_BASE_URL = "https://guide.catchup.im"
PublishedArticleSource: TypeAlias = (
    ChannelTalkDocumentArticle | ChannelTalkDocumentArticleRevision
)


class ArticleExecution(Protocol):
    @property
    def channel_id(self) -> str: ...

    @property
    def channel_name(self) -> str: ...

    @property
    def space_id(self) -> str: ...

    @property
    def space_name(self) -> str: ...


class ArticleTransformer:
    """Fetched article bundle을 vector DB에 저장할 prepared document 단위로 조립한다."""

    def __init__(
        self,
        *,
        language: str,
        content_normalizer: ArticleContentNormalizer | None = None,
        chunker: ArticleChunker | None = None,
    ) -> None:
        self.language = require_text(language, "language")
        self._content_normalizer = content_normalizer or ArticleContentNormalizer()
        self._chunker = chunker or ArticleChunker()

    def transform(
        self,
        *,
        execution: ArticleExecution,
        sync_window: SyncWindow,
        bundle: ChannelTalkFetchedArticle,
    ) -> ArticleBuildResult:
        # Source 선택 단계: detail이 있으면 최신 article view를 사용하고,
        # 문서화 대상 content는 published revision으로만 제한한다.
        view = bundle.detail
        current_article = self._select_article(bundle)
        published_source = self._select_published_source(bundle)
        language = require_text(bundle.language or self.language, "language")

        # Delete prefix는 published revision이 없어도 반환한다.
        # 그래야 unpublished/draft 상태가 기존 published chunk를 제거할 수 있다.
        delete_prefix = build_article_delete_prefix(
            channel_id=execution.channel_id,
            space_id=execution.space_id,
            language=language,
            article_id=current_article.article_id,
        )
        if published_source is None:
            return ArticleBuildResult(documents=[], delete_prefix=delete_prefix)

        # Content 준비 단계: API body를 plain text로 정규화한 뒤,
        # 제목/섹션 구조를 보존하는 chunk 단위로 나눈다.
        state = ChannelTalkDocumentArticleState.PUBLISHED.value
        raw_content = self._content_normalizer.normalize_source_content(published_source)
        url = self._resolve_public_article_url(
            article=current_article,
            language=language,
            title=published_source.title,
        )
        header = self._build_context_header(source=published_source)
        chunks = self._chunker.chunk_article_content(
            header=header,
            body=raw_content,
        )
        chunk_count = len(chunks)

        # Document 조립 단계: chunk마다 동일한 logical metadata schema를 채우고,
        # deterministic id를 부여해 persist 단계의 replace-by-prefix 흐름과 맞춘다.
        prepared_documents: list[ArticlePreparedDocumentPayload] = []
        for chunk_index, page_content in enumerate(chunks):
            logical_metadata = self._build_logical_metadata(
                execution=execution,
                sync_window=sync_window,
                bundle=bundle,
                view=view,
                current_article=current_article,
                published_source=published_source,
                language=language,
                state=state,
                url=url,
                raw_content=raw_content,
                contextual_content=page_content,
                chunk_index=chunk_index,
                chunk_count=chunk_count,
            )
            document_id = build_article_document_id(
                channel_id=execution.channel_id,
                space_id=execution.space_id,
                language=language,
                article_id=current_article.article_id,
                chunk_index=chunk_index,
            )
            prepared_documents.append(
                ArticlePreparedDocumentPayload(
                    document_id=document_id,
                    article_id=current_article.article_id,
                    page_content=page_content,
                    logical_metadata=logical_metadata,
                    storage_metadata=logical_metadata.to_storage_metadata(),
                )
            )

        return ArticleBuildResult(
            documents=prepared_documents,
            delete_prefix=delete_prefix,
        )

    @staticmethod
    def _select_article(
        bundle: ChannelTalkFetchedArticle,
    ) -> ChannelTalkDocumentArticle:
        if bundle.detail is not None:
            return bundle.detail.article
        return bundle.list_item

    @staticmethod
    def _select_published_source(
        bundle: ChannelTalkFetchedArticle,
    ) -> PublishedArticleSource | None:
        if bundle.published_revision is None:
            return ArticleTransformer._select_current_published_article(bundle)
        revision = bundle.published_revision.revision
        if revision.state != ChannelTalkDocumentArticleState.PUBLISHED:
            return None
        return revision

    @staticmethod
    def _select_current_published_article(
        bundle: ChannelTalkFetchedArticle,
    ) -> ChannelTalkDocumentArticle | None:
        article = ArticleTransformer._select_article(bundle)
        if article.published_revision_id is None:
            return None
        if article.state != ChannelTalkDocumentArticleState.PUBLISHED:
            return None
        if article.current_revision_id != article.published_revision_id:
            return None
        return article

    def _build_logical_metadata(
        self,
        *,
        execution: ArticleExecution,
        sync_window: SyncWindow,
        bundle: ChannelTalkFetchedArticle,
        view: ChannelTalkDocumentArticleView | None,
        current_article: ChannelTalkDocumentArticle,
        published_source: PublishedArticleSource,
        language: str,
        state: str,
        url: str | None,
        raw_content: str,
        contextual_content: str,
        chunk_index: int,
        chunk_count: int,
    ) -> ChannelTalkDocumentArticleLogicalMetadata:
        # Metadata 조립 단계: article/view/revision에 흩어진 정보를
        # 검색 저장소가 기대하는 logical metadata 형태로 한 번에 정규화한다.
        author = self._select_author(
            view=view, published_revision=bundle.published_revision
        )
        category = view.article_category if view is not None else None
        topics = view.topics if view is not None else []
        topic_ids = list(
            dict.fromkeys(
                [
                    *current_article.topic_ids,
                    *(topic.topic_id for topic in topics),
                ]
            )
        )
        topic_names = [topic.name for topic in topics if topic.name is not None]

        return ChannelTalkDocumentArticleLogicalMetadata(
            base=DocumentBaseMetadata(
                source="channel_talk",
                record_id=current_article.article_id,
                url=url,
                created_at=published_source.created_at or current_article.created_at,
                updated_at=published_source.updated_at or current_article.updated_at,
                synced_at=sync_window.window_end,
                contextual_content=contextual_content,
            ),
            document_article_core=ChannelTalkDocumentArticleCoreMetadata(
                article=ChannelTalkDocumentArticleArticleMetadata(
                    article_id=current_article.article_id,
                    language=language,
                    state=state,
                    title=published_source.title,
                    subtitle=published_source.subtitle,
                    summary=published_source.summary,
                    body_text=raw_content,
                    slug=current_article.slug,
                    url=url,
                ),
                space=ChannelTalkDocumentArticleSpaceMetadata(
                    channel_id=execution.channel_id,
                    space_id=execution.space_id,
                    channel_name=execution.channel_name,
                    space_name=execution.space_name,
                ),
                author=ChannelTalkDocumentArticleAuthorMetadata(
                    author_id=published_source.author_id
                    or (author.author_id if author else None),
                    author_name=author.name if author else None,
                ),
                taxonomy=ChannelTalkDocumentArticleTaxonomyMetadata(
                    topic_ids=topic_ids,
                    topic_names=topic_names,
                    category_id=(
                        category.article_category_id if category is not None else None
                    ),
                    category_name=category.name if category is not None else None,
                ),
                publication=ChannelTalkDocumentArticlePublicationMetadata(
                    created_at=published_source.created_at
                    or current_article.created_at,
                    updated_at=published_source.updated_at
                    or current_article.updated_at,
                    published_at=current_article.published_at or bundle.published_at,
                    published_revision_id=self._published_revision_id(
                        published_source
                    ),
                    current_revision_id=current_article.current_revision_id,
                ),
                chunk=ChannelTalkDocumentArticleChunkMetadata(
                    chunk_index=chunk_index,
                    chunk_count=chunk_count,
                ),
            ),
        )

    @staticmethod
    def _resolve_public_article_url(
        *,
        article: ChannelTalkDocumentArticle,
        language: str,
        title: str | None,
    ) -> str | None:
        # URL 생성 단계: website_url이 있으면 우선 사용하고,
        # 없으면 public guide URL 규칙을 deterministic하게 재구성한다.
        if article.website_url:
            return article.website_url
        if not article.slug:
            return None

        normalized_language = quote(unquote(language.strip()), safe="")
        public_slug = ArticleTransformer._build_public_article_slug(
            title=title,
            slug=article.slug,
        )
        normalized_slug = quote(unquote(public_slug), safe="")
        if not normalized_language or not normalized_slug:
            return None
        return (
            f"{ARTICLE_PUBLIC_BASE_URL}/"
            f"{normalized_language}/articles/{normalized_slug}"
        )

    @staticmethod
    def _build_public_article_slug(*, title: str | None, slug: str) -> str:
        normalized_slug = unquote(slug.strip())
        if not normalized_slug:
            return ""
        if not title or not re.fullmatch(r"[0-9a-fA-F]{8,}", normalized_slug):
            return normalized_slug
        title_slug = "-".join(title.strip().split())
        return f"{title_slug}-{normalized_slug}" if title_slug else normalized_slug

    @staticmethod
    def _build_context_header(*, source: PublishedArticleSource) -> str:
        for value in (source.title, source.subtitle, source.summary):
            if value and value.strip():
                return value.strip()
        return source.article_id.strip() if source.article_id else ""

    @staticmethod
    def _published_revision_id(source: PublishedArticleSource) -> str | None:
        if isinstance(source, ChannelTalkDocumentArticleRevision):
            return source.revision_id
        return source.published_revision_id

    @staticmethod
    def _select_author(
        *,
        view: ChannelTalkDocumentArticleView | None,
        published_revision: ChannelTalkDocumentArticleRevisionView | None,
    ):
        if published_revision is not None and published_revision.author is not None:
            return published_revision.author
        if view is not None:
            return view.author
        return None
