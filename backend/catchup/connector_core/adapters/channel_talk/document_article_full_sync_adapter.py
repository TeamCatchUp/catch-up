from __future__ import annotations

from collections.abc import Iterable
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from bs4 import BeautifulSoup
from langchain_core.documents import Document
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import ValidationInfo
from pydantic import field_validator
from pydantic import model_validator

from catchup.components.embedder.constants import EmbeddingProvider
from catchup.components.embedder.factory import get_embedding_service
from catchup.components.vector_db.factory import get_pgvector_repository
from catchup.components.vector_db.pgvector.repository import PGVectorRepository
from catchup.connector_core.document_format import (
    ChannelTalkDocumentArticleChunkMetadata,
)
from catchup.connector_core.document_format import (
    ChannelTalkDocumentArticleCoreMetadata,
)
from catchup.connector_core.document_format import (
    ChannelTalkDocumentArticleLogicalMetadata,
)
from catchup.connector_core.document_format import (
    ChannelTalkDocumentArticlePublicationMetadata,
)
from catchup.connector_core.document_format import DocumentBaseMetadata
from catchup.connector_core.domain.structure import ConnectorKey
from catchup.connector_core.ports.full_sync import FullSyncExecutionRequest
from catchup.connector_core.ports.full_sync import FullSyncExecutionResult
from catchup.connector_core.ports.full_sync import FullSyncWindow
from catchup.connectors.channel_talk.document_article_full_sync_fetcher import (
    DEFAULT_DOCUMENT_ARTICLE_FULL_SYNC_STATES,
)
from catchup.connectors.channel_talk.document_article_full_sync_fetcher import (
    ChannelTalkDocumentArticleFullSyncConnection,
)
from catchup.connectors.channel_talk.document_article_full_sync_fetcher import (
    ChannelTalkDocumentArticleFullSyncFetcher,
)
from catchup.connectors.channel_talk.document_article_full_sync_fetcher import (
    ChannelTalkFetchedDocumentArticle,
)
from catchup.connectors.channel_talk.document_article_full_sync_fetcher import (
    ChannelTalkFetchedDocumentArticlesResult,
)
from catchup.connectors.channel_talk.full_sync_target_contract import (
    CHANNEL_TALK_DOCUMENT_ARTICLE_RUNTIME_TARGET,
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
    ChannelTalkDocumentCredentialsRecord,
)
from catchup.sync.audit import SyncAuditContext
from catchup.utils.validation import require_text

ARTICLE_CHUNK_TARGET_CHARS = 2000
ARTICLE_CHUNK_MAX_CHARS = 4000
ARTICLE_CHUNK_MIN_CHARS = 400

ARTICLE_STATE_DESCRIPTIONS = {
    "published": "This article is published and can be treated as public/current documentation.",
    "unpublished": "This article is unpublished and may not currently be visible to end users.",
    "draft": "This article is a draft and may not be finalized or publicly visible.",
}

FILE_ATTACHMENT_EXTENSIONS = (
    ".pdf",
    ".doc",
    ".docx",
    ".ppt",
    ".pptx",
    ".xls",
    ".xlsx",
    ".csv",
    ".tsv",
    ".zip",
)


@dataclass
class _ArticleContentBlock:
    block_type: str
    text: str


@dataclass
class _ArticleLeafSection:
    hierarchy: list[str]
    content_blocks: list[_ArticleContentBlock]
    parent_key: str


@dataclass
class _ArticleChunk:
    content: str
    section_hierarchy: list[str]


class ChannelTalkDocumentArticleFullSyncCheckpoint(BaseModel):
    """Adapter-local checkpoint placeholder until document article paging lands."""

    model_config = ConfigDict(extra="forbid")

    tenant_id: str
    target: Literal["document_article"] = CHANNEL_TALK_DOCUMENT_ARTICLE_RUNTIME_TARGET
    space_id: str
    state: ChannelTalkDocumentArticleState | None = None
    next_cursor: str | None = None

    @field_validator("tenant_id", "space_id")
    @classmethod
    def _validate_required_text(cls, value: str, info: ValidationInfo) -> str:
        return require_text(value, info.field_name or "field")


class ChannelTalkDocumentArticleFullSyncExecutionRequest(FullSyncExecutionRequest):
    """Execution request for the Channel Talk Documents article full-sync lane."""

    connector: Literal[ConnectorKey.CHANNEL_TALK] = ConnectorKey.CHANNEL_TALK
    target: Literal["document_article"] = CHANNEL_TALK_DOCUMENT_ARTICLE_RUNTIME_TARGET
    channel_connection: ChannelTalkCredentialsRecord
    document_connection: ChannelTalkDocumentCredentialsRecord
    checkpoint: ChannelTalkDocumentArticleFullSyncCheckpoint | None = None
    audit_context: SyncAuditContext | None = None

    @model_validator(mode="after")
    def _validate_connection_alignment(
        self,
    ) -> "ChannelTalkDocumentArticleFullSyncExecutionRequest":
        if self.channel_connection.channel_id != self.tenant_id:
            raise ValueError("channel_connection.channel_id must match tenant_id")
        if self.document_connection.channel_id != self.tenant_id:
            raise ValueError("document_connection.channel_id must match tenant_id")
        if self.checkpoint is not None and self.checkpoint.tenant_id != self.tenant_id:
            raise ValueError("checkpoint.tenant_id must match tenant_id")
        if (
            self.checkpoint is not None
            and self.checkpoint.space_id != self.document_connection.space_id
        ):
            raise ValueError("checkpoint.space_id must match document space_id")
        if (
            self.checkpoint is not None
            and self.checkpoint.state is not None
            and self.checkpoint.state not in DEFAULT_DOCUMENT_ARTICLE_FULL_SYNC_STATES
        ):
            raise ValueError("checkpoint.state must be included in fetch states")
        return self

    @property
    def channel_id(self) -> str:
        return self.tenant_id

    @property
    def space_id(self) -> str:
        return self.document_connection.space_id

    @property
    def space_name(self) -> str:
        return self.document_connection.space_name


class ChannelTalkDocumentArticleFullSyncFetchResult(BaseModel):
    """Typed fetch result for the document article lane."""

    model_config = ConfigDict(extra="forbid")

    channel_id: str
    space_id: str
    language: str
    bundles: tuple[ChannelTalkFetchedDocumentArticle, ...] = ()
    fetched_count: int = 0
    fetched_article_ids: tuple[str, ...] = ()
    next_checkpoint: ChannelTalkDocumentArticleFullSyncCheckpoint | None = None

    @field_validator("channel_id", "space_id", "language")
    @classmethod
    def _validate_required_text(cls, value: str, info: ValidationInfo) -> str:
        return require_text(value, info.field_name or "field")

    @field_validator("fetched_article_ids")
    @classmethod
    def _validate_article_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(require_text(item, "fetched_article_ids") for item in value)

    @model_validator(mode="after")
    def _validate_summary_alignment(
        self,
    ) -> "ChannelTalkDocumentArticleFullSyncFetchResult":
        if self.fetched_count != len(self.bundles):
            raise ValueError("fetched_count must match bundles")
        if self.fetched_article_ids != tuple(
            bundle.article_id for bundle in self.bundles
        ):
            raise ValueError("fetched_article_ids must match bundles")
        return self


class ChannelTalkDocumentArticlePreparedDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: str
    article_id: str
    page_content: str
    logical_metadata: ChannelTalkDocumentArticleLogicalMetadata
    storage_metadata: dict[str, object]

    @field_validator("document_id", "article_id", "page_content")
    @classmethod
    def _validate_required_text(cls, value: str, info: ValidationInfo) -> str:
        return require_text(value, info.field_name or "field")

    @property
    def contextual_content(self) -> str:
        return self.logical_metadata.base.contextual_content


class ChannelTalkDocumentArticleFullSyncTransformResult(BaseModel):
    """Typed transform result for materialized article chunks."""

    model_config = ConfigDict(extra="forbid")

    documents: tuple[ChannelTalkDocumentArticlePreparedDocument, ...] = ()
    delete_prefixes: tuple[str, ...] = ()
    prepared_document_ids: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _fill_prepared_document_ids(
        self,
    ) -> "ChannelTalkDocumentArticleFullSyncTransformResult":
        if not self.prepared_document_ids and self.documents:
            self.prepared_document_ids = tuple(
                document.document_id for document in self.documents
            )
        return self


class ChannelTalkDocumentArticleFullSyncSummaryResult(BaseModel):
    """Typed summary placeholder; article summarization is added in a later slice."""

    model_config = ConfigDict(extra="forbid")

    summary_applied: bool = False
    document_count: int = 0


class ChannelTalkDocumentArticleFullSyncPersistResult(BaseModel):
    """Persist result for article chunk materialization."""

    model_config = ConfigDict(extra="forbid")

    persisted_count: int = 0
    persisted_ids: tuple[str, ...] = ()
    deleted_prefixes: tuple[str, ...] = ()


class ChannelTalkDocumentArticleFullSyncExecutionResult(FullSyncExecutionResult):
    """Final typed result for a document article full-sync run."""

    connector: Literal[ConnectorKey.CHANNEL_TALK] = ConnectorKey.CHANNEL_TALK
    target: Literal["document_article"] = CHANNEL_TALK_DOCUMENT_ARTICLE_RUNTIME_TARGET
    collected_count: int = 0
    document_count: int = 0
    fetched: ChannelTalkDocumentArticleFullSyncFetchResult
    transformed: ChannelTalkDocumentArticleFullSyncTransformResult
    summary: ChannelTalkDocumentArticleFullSyncSummaryResult
    persisted: ChannelTalkDocumentArticleFullSyncPersistResult

    @property
    def channel_id(self) -> str:
        return self.tenant_id

    @property
    def space_id(self) -> str:
        return self.fetched.space_id


class ChannelTalkDocumentArticleFullSyncAdapter:
    """Runtime seam for Channel Talk Documents article full sync."""

    def __init__(
        self,
        *,
        fetcher: ChannelTalkDocumentArticleFullSyncFetcher | None = None,
        language: str = "ko",
        repository_factory=None,
    ) -> None:
        self.fetcher = fetcher or ChannelTalkDocumentArticleFullSyncFetcher()
        self.language = require_text(language, "language")
        self._repository_factory = repository_factory or self._build_repository
        self._repository: PGVectorRepository | None = None

    async def fetch(
        self,
        *,
        execution: ChannelTalkDocumentArticleFullSyncExecutionRequest,
        sync_window: FullSyncWindow,
    ) -> ChannelTalkDocumentArticleFullSyncFetchResult:
        fetched_articles = await self.fetcher.fetch_articles(
            connection=ChannelTalkDocumentArticleFullSyncConnection.from_credentials_record(
                execution.document_connection,
            ),
            language=self.language,
            sync_window=sync_window,
            states=DEFAULT_DOCUMENT_ARTICLE_FULL_SYNC_STATES,
            checkpoint_state=(
                execution.checkpoint.state if execution.checkpoint is not None else None
            ),
            checkpoint_cursor=(
                execution.checkpoint.next_cursor
                if execution.checkpoint is not None
                else None
            ),
        )
        return ChannelTalkDocumentArticleFullSyncFetchResult(
            channel_id=execution.channel_id,
            space_id=execution.space_id,
            language=self.language,
            bundles=fetched_articles.bundles,
            fetched_count=fetched_articles.fetched_count,
            fetched_article_ids=fetched_articles.article_ids,
            next_checkpoint=self._build_next_checkpoint(
                execution=execution,
                fetched_articles=fetched_articles,
            ),
        )

    async def transform(
        self,
        *,
        execution: ChannelTalkDocumentArticleFullSyncExecutionRequest,
        sync_window: FullSyncWindow,
        fetched: ChannelTalkDocumentArticleFullSyncFetchResult,
    ) -> ChannelTalkDocumentArticleFullSyncTransformResult:
        documents: list[ChannelTalkDocumentArticlePreparedDocument] = []
        delete_prefixes: list[str] = []
        seen_article_ids: set[str] = set()

        for bundle in fetched.bundles:
            if bundle.article_id in seen_article_ids:
                continue
            seen_article_ids.add(bundle.article_id)
            article_documents, delete_prefix = self._build_prepared_documents(
                execution=execution,
                sync_window=sync_window,
                bundle=bundle,
            )
            documents.extend(article_documents)
            delete_prefixes.append(delete_prefix)

        return ChannelTalkDocumentArticleFullSyncTransformResult(
            documents=tuple(documents),
            delete_prefixes=tuple(dict.fromkeys(delete_prefixes)),
        )

    async def summarize(
        self,
        *,
        execution: ChannelTalkDocumentArticleFullSyncExecutionRequest,
        sync_window: FullSyncWindow,
        transformed: ChannelTalkDocumentArticleFullSyncTransformResult,
    ) -> ChannelTalkDocumentArticleFullSyncSummaryResult:
        _ = execution
        _ = sync_window
        return ChannelTalkDocumentArticleFullSyncSummaryResult(
            summary_applied=False,
            document_count=len(transformed.documents),
        )

    async def persist(
        self,
        *,
        execution: ChannelTalkDocumentArticleFullSyncExecutionRequest,
        sync_window: FullSyncWindow,
        transformed: ChannelTalkDocumentArticleFullSyncTransformResult,
        summary: ChannelTalkDocumentArticleFullSyncSummaryResult,
    ) -> ChannelTalkDocumentArticleFullSyncPersistResult:
        _ = execution
        _ = sync_window
        _ = summary
        repository = await self._get_repository()

        for prefix in transformed.delete_prefixes:
            await repository.delete_by_id_prefix(prefix)

        if not transformed.documents:
            return ChannelTalkDocumentArticleFullSyncPersistResult(
                persisted_count=0,
                persisted_ids=(),
                deleted_prefixes=transformed.delete_prefixes,
            )

        documents = [
            Document(
                id=document.document_id,
                page_content=document.page_content,
                metadata=document.storage_metadata,
            )
            for document in transformed.documents
        ]
        document_ids = [document.document_id for document in transformed.documents]
        persisted_ids = await repository.add_documents(documents, ids=document_ids)
        return ChannelTalkDocumentArticleFullSyncPersistResult(
            persisted_count=len(persisted_ids),
            persisted_ids=tuple(persisted_ids),
            deleted_prefixes=transformed.delete_prefixes,
        )

    def build_result(
        self,
        *,
        execution: ChannelTalkDocumentArticleFullSyncExecutionRequest,
        sync_window: FullSyncWindow,
        fetched: ChannelTalkDocumentArticleFullSyncFetchResult,
        transformed: ChannelTalkDocumentArticleFullSyncTransformResult,
        summary: ChannelTalkDocumentArticleFullSyncSummaryResult,
        persisted: ChannelTalkDocumentArticleFullSyncPersistResult,
    ) -> ChannelTalkDocumentArticleFullSyncExecutionResult:
        _ = sync_window
        return ChannelTalkDocumentArticleFullSyncExecutionResult(
            tenant_id=execution.tenant_id,
            collected_count=len(fetched.fetched_article_ids),
            document_count=len(transformed.documents),
            fetched=fetched,
            transformed=transformed,
            summary=summary,
            persisted=persisted,
        )

    @staticmethod
    def _build_next_checkpoint(
        *,
        execution: ChannelTalkDocumentArticleFullSyncExecutionRequest,
        fetched_articles: ChannelTalkFetchedDocumentArticlesResult,
    ) -> ChannelTalkDocumentArticleFullSyncCheckpoint | None:
        if fetched_articles.next_checkpoint_state is None:
            return None
        return ChannelTalkDocumentArticleFullSyncCheckpoint(
            tenant_id=execution.tenant_id,
            space_id=execution.space_id,
            state=fetched_articles.next_checkpoint_state,
            next_cursor=fetched_articles.next_checkpoint_cursor,
        )

    async def _get_repository(self) -> PGVectorRepository:
        if self._repository is None:
            repository = self._repository_factory()
            try:
                repository.ensure_initialized()
            except RuntimeError:
                await repository.initialize(None)
            self._repository = repository
        assert self._repository is not None
        return self._repository

    @staticmethod
    def _build_repository() -> PGVectorRepository:
        return get_pgvector_repository(
            embeddings=get_embedding_service(
                EmbeddingProvider.AWS_BEDROCK
            ).get_embedder()
        )

    def _build_prepared_documents(
        self,
        *,
        execution: ChannelTalkDocumentArticleFullSyncExecutionRequest,
        sync_window: FullSyncWindow,
        bundle: ChannelTalkFetchedDocumentArticle,
    ) -> tuple[list[ChannelTalkDocumentArticlePreparedDocument], str]:
        view = bundle.detail
        current_article = self._select_article(bundle)
        source_revision = self._select_published_revision(bundle)
        language = require_text(bundle.language or self.language, "language")
        delete_prefix = self._build_delete_prefix(
            channel_id=execution.channel_id,
            space_id=execution.space_id,
            language=language,
            article_id=current_article.article_id,
        )
        if source_revision is None:
            return [], delete_prefix

        state = ChannelTalkDocumentArticleState.PUBLISHED.value
        raw_content = self._normalize_source_content(source_revision)
        url = current_article.website_url
        header = self._build_context_header(
            execution=execution,
            source=source_revision,
            state=state,
            language=language,
            url=url,
        )
        chunks = self._chunk_article_content(
            header=header,
            body=raw_content,
        )
        chunk_count = len(chunks)

        prepared_documents: list[ChannelTalkDocumentArticlePreparedDocument] = []
        for chunk_index, page_content in enumerate(chunks):
            logical_metadata = self._build_logical_metadata(
                execution=execution,
                sync_window=sync_window,
                bundle=bundle,
                view=view,
                current_article=current_article,
                source_revision=source_revision,
                language=language,
                state=state,
                url=url,
                contextual_content=page_content,
                chunk_index=chunk_index,
                chunk_count=chunk_count,
            )
            document_id = self._build_document_id(
                channel_id=execution.channel_id,
                space_id=execution.space_id,
                language=language,
                article_id=current_article.article_id,
                chunk_index=chunk_index,
            )
            prepared_documents.append(
                ChannelTalkDocumentArticlePreparedDocument(
                    document_id=document_id,
                    article_id=current_article.article_id,
                    page_content=page_content,
                    logical_metadata=logical_metadata,
                    storage_metadata=logical_metadata.to_storage_metadata(),
                )
            )

        return prepared_documents, delete_prefix

    @staticmethod
    def _select_article(
        bundle: ChannelTalkFetchedDocumentArticle,
    ) -> ChannelTalkDocumentArticle:
        if bundle.detail is not None:
            return bundle.detail.article
        return bundle.list_item

    @staticmethod
    def _select_published_revision(
        bundle: ChannelTalkFetchedDocumentArticle,
    ) -> ChannelTalkDocumentArticleRevision | None:
        if bundle.published_revision is None:
            return None
        revision = bundle.published_revision.revision
        if revision.state != ChannelTalkDocumentArticleState.PUBLISHED:
            return None
        return revision

    def _build_logical_metadata(
        self,
        *,
        execution: ChannelTalkDocumentArticleFullSyncExecutionRequest,
        sync_window: FullSyncWindow,
        bundle: ChannelTalkFetchedDocumentArticle,
        view: ChannelTalkDocumentArticleView | None,
        current_article: ChannelTalkDocumentArticle,
        source_revision: ChannelTalkDocumentArticleRevision,
        language: str,
        state: str,
        url: str | None,
        contextual_content: str,
        chunk_index: int,
        chunk_count: int,
    ) -> ChannelTalkDocumentArticleLogicalMetadata:
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
                created_at=source_revision.created_at or current_article.created_at,
                updated_at=source_revision.updated_at or current_article.updated_at,
                synced_at=sync_window.window_end,
                contextual_content=contextual_content,
            ),
            document_article_core=ChannelTalkDocumentArticleCoreMetadata(
                channel_id=execution.channel_id,
                space_id=execution.space_id,
                space_name=execution.space_name,
                article_id=current_article.article_id,
                language=language,
                state=state,
                title=source_revision.title,
                subtitle=source_revision.subtitle,
                summary=source_revision.summary,
                slug=current_article.slug,
                url=url,
                author_id=source_revision.author_id
                or (author.author_id if author else None),
                author_name=author.name if author else None,
                topic_ids=topic_ids,
                topic_names=topic_names,
                category_id=(
                    category.article_category_id if category is not None else None
                ),
                category_name=category.name if category is not None else None,
            ),
            publication=ChannelTalkDocumentArticlePublicationMetadata(
                created_at=source_revision.created_at or current_article.created_at,
                updated_at=source_revision.updated_at or current_article.updated_at,
                published_at=current_article.published_at or bundle.published_at,
                published_revision_id=source_revision.revision_id,
                current_revision_id=current_article.current_revision_id,
            ),
            chunk=ChannelTalkDocumentArticleChunkMetadata(
                chunk_index=chunk_index,
                chunk_count=chunk_count,
            ),
        )

    def _build_context_header(
        self,
        *,
        execution: ChannelTalkDocumentArticleFullSyncExecutionRequest,
        source: ChannelTalkDocumentArticleRevision,
        state: str,
        language: str,
        url: str | None,
    ) -> str:
        state_description = ARTICLE_STATE_DESCRIPTIONS.get(
            state,
            "This article has an unrecognized Channel Talk state; use the state metadata when deciding how authoritative it is.",
        )
        lines = [
            "[Channel Talk Document Article]",
            f"Document State: {state}",
            f"State Meaning: {state_description}",
        ]
        optional_lines = [
            ("Title", source.title),
            ("Subtitle", source.subtitle),
            ("Space", execution.space_name),
            ("Language", language),
            ("URL", url),
        ]
        for label, value in optional_lines:
            if value:
                lines.append(f"{label}: {value}")
        return "\n".join(lines)

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

    def _normalize_source_content(
        self,
        source: ChannelTalkDocumentArticleRevision,
    ) -> str:
        if isinstance(source.body, (list, tuple, Mapping)):
            block_text = self._normalize_block_body(source.body)
            if block_text:
                return block_text
        if isinstance(source.body, str) and source.body.strip():
            return self._normalize_plain_text(source.body)
        if source.body_html and source.body_html.strip():
            return self._normalize_html(source.body_html)
        fallback_parts = [
            source.summary,
            source.subtitle,
            source.title,
        ]
        return self._normalize_plain_text(
            "\n\n".join(part for part in fallback_parts if part)
        )

    @staticmethod
    def _normalize_html(value: str) -> str:
        soup = BeautifulSoup(value, "lxml")
        for element in soup(["script", "style", "noscript", "svg"]):
            element.decompose()
        for table in soup.find_all("table"):
            table.replace_with(
                "\n"
                + ChannelTalkDocumentArticleFullSyncAdapter._format_html_table(table)
                + "\n"
            )
        for heading in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
            for image in heading.find_all("img"):
                label = image.get("alt") or image.get("title")
                image.replace_with(label.strip() if isinstance(label, str) else "")
        for media in soup.find_all(["figure"]):
            media_text = ChannelTalkDocumentArticleFullSyncAdapter._format_html_figure(
                media
            )
            if media_text:
                media.replace_with(f"\n{media_text}\n")
        for media in soup.find_all(["img", "video"]):
            media_text = (
                ChannelTalkDocumentArticleFullSyncAdapter._format_html_media_element(
                    media
                )
            )
            media.replace_with(f"\n{media_text}\n" if media_text else "")
        for media in soup.find_all(["iframe", "embed"]):
            src = (
                media.get("src")
                or media.get("href")
                or media.get("data-node-attrs-src")
            )
            media_text = ChannelTalkDocumentArticleFullSyncAdapter._format_link_text(
                "Embed",
                src,
            )
            media.replace_with(f"\n{media_text}\n" if media_text else "")
        for heading in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
            level = int(heading.name[1])
            text = heading.get_text(" ", strip=True)
            if text:
                heading.string = f"{'#' * level} {text}"
        for link in soup.find_all("a"):
            label = link.get_text(" ", strip=True)
            href = link.get("href")
            if ChannelTalkDocumentArticleFullSyncAdapter._is_html_file_attachment(link):
                link.replace_with(
                    ChannelTalkDocumentArticleFullSyncAdapter._format_file_attachment(
                        ChannelTalkDocumentArticleFullSyncAdapter._html_file_name(link)
                    )
                )
                continue
            if link.get("data-node-type") == "embed":
                label = label if label and label != href else "Embed"
            link_text = ChannelTalkDocumentArticleFullSyncAdapter._format_link_text(
                label,
                href,
            )
            if link_text:
                link.replace_with(link_text)
        block_tags = ["br", "p", "div", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6"]
        for breaker in soup.find_all(block_tags):
            breaker.append("\n")
        return ChannelTalkDocumentArticleFullSyncAdapter._normalize_plain_text(
            soup.get_text("\n")
        )

    @staticmethod
    def _normalize_block_body(value: object) -> str:
        parts = list(
            ChannelTalkDocumentArticleFullSyncAdapter._iter_block_text_blocks(value)
        )
        return ChannelTalkDocumentArticleFullSyncAdapter._normalize_plain_text(
            "\n\n".join(parts)
        )

    @staticmethod
    def _iter_block_text_blocks(value: object) -> Iterable[str]:
        if isinstance(value, str):
            text = value.strip()
            if text:
                yield text
            return
        if isinstance(value, (list, tuple)):
            for item in value:
                yield from ChannelTalkDocumentArticleFullSyncAdapter._iter_block_text_blocks(
                    item
                )
            return
        if not isinstance(value, Mapping):
            return

        node_type = str(value.get("type") or "").strip()
        attrs = ChannelTalkDocumentArticleFullSyncAdapter._mapping_value(
            value.get("attrs")
        )
        if node_type == "heading":
            text = ChannelTalkDocumentArticleFullSyncAdapter._extract_block_inline_text(
                value
            )
            if text:
                level = ChannelTalkDocumentArticleFullSyncAdapter._int_value(
                    attrs.get("level"),
                    default=1,
                )
                yield f"{'#' * min(max(level, 1), 6)} {text}"
            return
        if node_type in {"text", "paragraph"}:
            text = ChannelTalkDocumentArticleFullSyncAdapter._extract_block_inline_text(
                value
            )
            if text:
                yield text
            return
        if node_type in {"image", "video"}:
            media_text = ChannelTalkDocumentArticleFullSyncAdapter._format_media_block_from_attrs(
                node_type=node_type,
                attrs=attrs,
            )
            if media_text:
                yield media_text
            return
        if node_type == "embed":
            embed_text = ChannelTalkDocumentArticleFullSyncAdapter._format_link_text(
                "Embed",
                ChannelTalkDocumentArticleFullSyncAdapter._first_text(
                    attrs,
                    "src",
                    "url",
                    "href",
                ),
            )
            if embed_text:
                yield embed_text
            return
        if node_type in {"file", "attachment", "attachments"}:
            yield ChannelTalkDocumentArticleFullSyncAdapter._format_file_attachment(
                ChannelTalkDocumentArticleFullSyncAdapter._file_name_from_attrs(attrs)
            )
            return
        if node_type == "table":
            table_text = ChannelTalkDocumentArticleFullSyncAdapter._format_block_table(
                value
            )
            if table_text:
                yield table_text
            return
        if node_type in {"bullets", "bulletList"}:
            list_text = ChannelTalkDocumentArticleFullSyncAdapter._format_block_list(
                value,
                ordered=False,
            )
            if list_text:
                yield list_text
            return
        if node_type == "orderedList":
            list_text = ChannelTalkDocumentArticleFullSyncAdapter._format_block_list(
                value,
                ordered=True,
            )
            if list_text:
                yield list_text
            return
        if node_type in {"code", "codeBlock"}:
            text = ChannelTalkDocumentArticleFullSyncAdapter._extract_block_inline_text(
                value
            )
            if text:
                yield f"```\n{text}\n```"
            return

        child_blocks = list(
            ChannelTalkDocumentArticleFullSyncAdapter._iter_block_text_blocks(
                value.get("content", ())
            )
        )
        if child_blocks:
            yield "\n".join(child_blocks)
            return

        text = ChannelTalkDocumentArticleFullSyncAdapter._extract_block_inline_text(
            value
        )
        if text:
            yield text

    @staticmethod
    def _iter_block_strings(value: object) -> Iterable[str]:
        preferred_keys = (
            "text",
            "plainText",
            "title",
            "subtitle",
            "summary",
            "content",
            "body",
            "children",
            "items",
        )
        if isinstance(value, str):
            text = value.strip()
            if text:
                yield text
            return
        if isinstance(value, Mapping):
            seen: set[str] = set()
            for key in preferred_keys:
                if key in value:
                    seen.add(key)
                    yield from ChannelTalkDocumentArticleFullSyncAdapter._iter_block_strings(
                        value[key]
                    )
            for key, nested in value.items():
                if key in seen:
                    continue
                if isinstance(nested, (Mapping, list, tuple)):
                    yield from ChannelTalkDocumentArticleFullSyncAdapter._iter_block_strings(
                        nested
                    )
            return
        if isinstance(value, (list, tuple)):
            for item in value:
                yield from ChannelTalkDocumentArticleFullSyncAdapter._iter_block_strings(
                    item
                )

    @staticmethod
    def _extract_block_inline_text(value: object) -> str:
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, (list, tuple)):
            return "".join(
                ChannelTalkDocumentArticleFullSyncAdapter._extract_block_inline_text(
                    item
                )
                for item in value
            ).strip()
        if not isinstance(value, Mapping):
            return ""

        node_type = str(value.get("type") or "").strip()
        attrs = ChannelTalkDocumentArticleFullSyncAdapter._mapping_value(
            value.get("attrs")
        )
        if node_type == "plain":
            text = ChannelTalkDocumentArticleFullSyncAdapter._first_text(
                attrs,
                "text",
                "name",
                "title",
            )
            return ChannelTalkDocumentArticleFullSyncAdapter._apply_link_marks(
                text,
                value.get("marks"),
            )
        if node_type == "emoji":
            return ChannelTalkDocumentArticleFullSyncAdapter._first_text(
                attrs,
                "name",
                "text",
            )
        if node_type in {"image", "video"}:
            return ChannelTalkDocumentArticleFullSyncAdapter._format_media_block_from_attrs(
                node_type=node_type,
                attrs=attrs,
            )
        if node_type in {"file", "attachment", "attachments"}:
            return ChannelTalkDocumentArticleFullSyncAdapter._format_file_attachment(
                ChannelTalkDocumentArticleFullSyncAdapter._file_name_from_attrs(attrs)
            )
        if node_type == "embed":
            return ChannelTalkDocumentArticleFullSyncAdapter._format_link_text(
                "Embed",
                ChannelTalkDocumentArticleFullSyncAdapter._first_text(
                    attrs,
                    "src",
                    "url",
                    "href",
                ),
            )

        if "content" in value:
            return "".join(
                ChannelTalkDocumentArticleFullSyncAdapter._extract_block_inline_text(
                    item
                )
                for item in ChannelTalkDocumentArticleFullSyncAdapter._sequence_value(
                    value.get("content")
                )
            ).strip()
        return ChannelTalkDocumentArticleFullSyncAdapter._first_text(
            attrs,
            "text",
            "plainText",
            "title",
            "name",
            "label",
        )

    @staticmethod
    def _format_block_table(value: Mapping[str, object]) -> str:
        rows: list[list[str]] = []
        for row in ChannelTalkDocumentArticleFullSyncAdapter._sequence_value(
            value.get("content")
        ):
            if not isinstance(row, Mapping):
                continue
            cells = []
            for cell in ChannelTalkDocumentArticleFullSyncAdapter._sequence_value(
                row.get("content")
            ):
                cell_text = (
                    ChannelTalkDocumentArticleFullSyncAdapter._extract_block_cell_text(
                        cell
                    )
                )
                cells.append(cell_text)
            if cells:
                rows.append(cells)
        return ChannelTalkDocumentArticleFullSyncAdapter._format_markdown_table(rows)

    @staticmethod
    def _extract_block_cell_text(value: object) -> str:
        blocks = list(
            ChannelTalkDocumentArticleFullSyncAdapter._iter_block_text_blocks(value)
        )
        if blocks:
            return " ".join(block.replace("\n", " ") for block in blocks).strip()
        return ChannelTalkDocumentArticleFullSyncAdapter._extract_block_inline_text(
            value
        )

    @staticmethod
    def _format_block_list(value: Mapping[str, object], *, ordered: bool) -> str:
        lines: list[str] = []
        start = ChannelTalkDocumentArticleFullSyncAdapter._int_value(
            ChannelTalkDocumentArticleFullSyncAdapter._mapping_value(
                value.get("attrs")
            ).get("start"),
            default=1,
        )
        for index, item in enumerate(
            ChannelTalkDocumentArticleFullSyncAdapter._sequence_value(
                value.get("content")
            ),
            start=start,
        ):
            item_blocks = list(
                ChannelTalkDocumentArticleFullSyncAdapter._iter_block_text_blocks(item)
            )
            item_text = "\n".join(item_blocks).strip()
            if not item_text:
                continue
            marker = f"{index}. " if ordered else "- "
            item_lines = item_text.splitlines()
            lines.append(marker + item_lines[0])
            lines.extend(f"  {line}" for line in item_lines[1:])
        return "\n".join(lines)

    @staticmethod
    def _format_html_table(table) -> str:
        rows: list[list[str]] = []
        for row in table.find_all("tr"):
            cells = row.find_all(["th", "td"], recursive=False)
            if not cells:
                cells = row.find_all(["th", "td"])
            row_values = [cell.get_text(" ", strip=True) for cell in cells]
            if row_values:
                rows.append(row_values)
        return ChannelTalkDocumentArticleFullSyncAdapter._format_markdown_table(rows)

    @staticmethod
    def _format_markdown_table(rows: list[list[str]]) -> str:
        rows = [
            [cell.strip() for cell in row]
            for row in rows
            if any(cell.strip() for cell in row)
        ]
        if not rows:
            return ""
        column_count = max(len(row) for row in rows)
        normalized_rows = [row + [""] * (column_count - len(row)) for row in rows]
        header = normalized_rows[0]
        data_rows = normalized_rows[1:]
        lines = [
            "| "
            + " | ".join(
                ChannelTalkDocumentArticleFullSyncAdapter._escape_markdown_table_cell(
                    cell
                )
                for cell in header
            )
            + " |",
            "| " + " | ".join("---" for _ in range(column_count)) + " |",
        ]
        for row in data_rows:
            lines.append(
                "| "
                + " | ".join(
                    ChannelTalkDocumentArticleFullSyncAdapter._escape_markdown_table_cell(
                        cell
                    )
                    for cell in row
                )
                + " |"
            )
        return "\n".join(lines)

    @staticmethod
    def _escape_markdown_table_cell(value: str) -> str:
        return " ".join(value.split()).replace("|", "\\|")

    @staticmethod
    def _format_html_figure(figure) -> str:
        media = figure.find(["img", "video"])
        if media is None:
            return ""
        caption = ""
        figcaption = figure.find("figcaption")
        if figcaption is not None:
            caption = figcaption.get_text(" ", strip=True)
        return ChannelTalkDocumentArticleFullSyncAdapter._format_html_media_element(
            media,
            caption=caption,
        )

    @staticmethod
    def _format_html_media_element(media, *, caption: str | None = None) -> str:
        node_type = "video" if media.name == "video" else "image"
        attrs = {
            "alt": media.get("alt"),
            "title": media.get("title"),
            "src": media.get("src") or media.get("data-node-attrs-src"),
            "caption": caption,
        }
        return ChannelTalkDocumentArticleFullSyncAdapter._format_media_block_from_attrs(
            node_type=node_type,
            attrs=attrs,
        )

    @staticmethod
    def _format_media_block_from_attrs(
        *,
        node_type: str,
        attrs: Mapping[str, object],
    ) -> str:
        label = "Video" if node_type == "video" else "Image"
        file_name = ChannelTalkDocumentArticleFullSyncAdapter._first_text(
            attrs,
            "alt",
            "title",
            "name",
            "fileName",
            "file_name",
            "filename",
        )
        caption = ChannelTalkDocumentArticleFullSyncAdapter._caption_text(
            attrs.get("caption")
        )
        lines = [f"[{label}] {file_name}" if file_name else f"[{label}]"]
        if caption:
            lines.append(f"Caption: {caption}")
        return "\n".join(lines)

    @staticmethod
    def _caption_text(value: object) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        blocks = list(
            ChannelTalkDocumentArticleFullSyncAdapter._iter_block_text_blocks(value)
        )
        if blocks:
            return " ".join(blocks).strip()
        return ChannelTalkDocumentArticleFullSyncAdapter._extract_block_inline_text(
            value
        )

    @staticmethod
    def _format_link_text(label: object, href: object) -> str:
        text = str(label or "").strip()
        url = str(href or "").strip()
        if text and url and url not in text:
            return f"{text} ({url})"
        return text or url

    @staticmethod
    def _format_file_attachment(file_name: object) -> str:
        normalized = str(file_name or "").strip() or "첨부 파일"
        return f"{normalized} [파일 첨부]"

    @staticmethod
    def _html_file_name(link) -> str:
        for key in (
            "download",
            "title",
            "data-node-attrs-name",
            "data-node-attrs-file-name",
            "data-node-attrs-filename",
        ):
            value = link.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        label = link.get_text(" ", strip=True)
        if label:
            return label
        href = str(link.get("href") or "").rstrip("/")
        return href.rsplit("/", 1)[-1]

    @staticmethod
    def _is_html_file_attachment(link) -> bool:
        node_type = str(link.get("data-node-type") or "").strip()
        if node_type in {"file", "attachment"}:
            return True
        mime = str(link.get("data-node-attrs-mime") or link.get("type") or "").lower()
        if mime and not mime.startswith(("text/html", "image/", "video/")):
            return True
        href = str(link.get("href") or "").lower()
        return any(
            href.split("?", 1)[0].endswith(ext) for ext in FILE_ATTACHMENT_EXTENSIONS
        )

    @staticmethod
    def _file_name_from_attrs(attrs: Mapping[str, object]) -> str:
        file_name = ChannelTalkDocumentArticleFullSyncAdapter._first_text(
            attrs,
            "name",
            "fileName",
            "file_name",
            "filename",
            "title",
            "alt",
        )
        if file_name:
            return file_name
        src = ChannelTalkDocumentArticleFullSyncAdapter._first_text(
            attrs,
            "src",
            "url",
            "href",
        ).rstrip("/")
        if src:
            return src.rsplit("/", 1)[-1]
        return ""

    @staticmethod
    def _apply_link_marks(text: str, marks: object) -> str:
        if not text:
            return ""
        for mark in ChannelTalkDocumentArticleFullSyncAdapter._sequence_value(marks):
            if not isinstance(mark, Mapping):
                continue
            if str(mark.get("type") or "") != "link":
                continue
            attrs = ChannelTalkDocumentArticleFullSyncAdapter._mapping_value(
                mark.get("attrs")
            )
            href = ChannelTalkDocumentArticleFullSyncAdapter._first_text(
                attrs,
                "href",
                "url",
                "src",
            )
            return ChannelTalkDocumentArticleFullSyncAdapter._format_link_text(
                text,
                href,
            )
        return text

    @staticmethod
    def _first_text(source: Mapping[str, object], *keys: str) -> str:
        for key in keys:
            value = source.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""

    @staticmethod
    def _mapping_value(value: object) -> Mapping[str, object]:
        return value if isinstance(value, Mapping) else {}

    @staticmethod
    def _sequence_value(value: object) -> tuple[object, ...]:
        if isinstance(value, (list, tuple)):
            return tuple(value)
        if value is None:
            return ()
        return (value,)

    @staticmethod
    def _int_value(value: object, *, default: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _normalize_plain_text(value: str) -> str:
        lines = [" ".join(line.split()) for line in value.splitlines()]
        compacted: list[str] = []
        previous_blank = False
        for line in lines:
            if not line:
                if not previous_blank and compacted:
                    compacted.append("")
                previous_blank = True
                continue
            compacted.append(line)
            previous_blank = False
        return "\n".join(compacted).strip()

    def _chunk_article_content(self, *, header: str, body: str) -> tuple[str, ...]:
        budget = self._article_chunk_budget(header)
        leaves = self._build_article_leaf_sections(body)
        if not leaves:
            return (header,)

        merged = self._merge_small_article_sections(leaves, max_chars=budget["max"])
        split = self._split_large_article_sections(
            merged,
            target_chars=budget["target"],
            max_chars=budget["max"],
        )
        post_merged = self._merge_post_split_article_sections(
            split,
            max_chars=budget["max"],
        )
        chunks = self._build_article_chunks(
            header=header,
            leaves=post_merged,
        )
        return tuple(chunk.content for chunk in chunks) or (header,)

    @staticmethod
    def _article_chunk_budget(header: str) -> dict[str, int]:
        return {
            "target": max(
                ARTICLE_CHUNK_TARGET_CHARS - len(header) - 2,
                ARTICLE_CHUNK_MIN_CHARS,
            ),
            "max": max(
                ARTICLE_CHUNK_MAX_CHARS - len(header) - 2,
                ARTICLE_CHUNK_MIN_CHARS,
            ),
        }

    def _build_article_leaf_sections(self, body: str) -> list[_ArticleLeafSection]:
        paragraphs = self._split_paragraphs(body)
        leaves: list[_ArticleLeafSection] = []
        hierarchy: list[str] = []
        blocks: list[_ArticleContentBlock] = []

        def flush() -> None:
            nonlocal blocks
            if not blocks:
                return
            leaves.append(
                _ArticleLeafSection(
                    hierarchy=list(hierarchy),
                    content_blocks=blocks,
                    parent_key=" > ".join(hierarchy[:-1]),
                )
            )
            blocks = []

        for paragraph in paragraphs:
            heading = self._parse_article_heading(paragraph)
            if heading is not None:
                flush()
                level, text = heading
                if level is None:
                    hierarchy = [text]
                else:
                    hierarchy = hierarchy[: max(level - 1, 0)] + [text]
                continue

            blocks.append(
                _ArticleContentBlock(
                    block_type=self._infer_article_block_type(paragraph),
                    text=paragraph,
                )
            )

        flush()
        return leaves

    @staticmethod
    def _parse_article_heading(paragraph: str) -> tuple[int | None, str] | None:
        lines = [line.strip() for line in paragraph.splitlines() if line.strip()]
        if len(lines) != 1:
            return None
        line = lines[0]
        if line.startswith("#"):
            marker, _, text = line.partition(" ")
            if marker and set(marker) == {"#"} and text.strip():
                return min(len(marker), 6), text.strip()
        if len(line) <= 120:
            number, separator, text = line.partition(". ")
            if separator and number.replace(".", "").isdigit() and text.strip():
                return None, line
        return None

    @staticmethod
    def _infer_article_block_type(text: str) -> str:
        stripped = text.strip()
        lines = [line for line in stripped.splitlines() if line.strip()]
        if stripped.startswith("```"):
            return "code"
        if len(lines) >= 2 and all(line.strip().startswith("|") for line in lines[:2]):
            return "table"
        list_markers = ("- ", "* ", "• ")
        numbered_count = 0
        list_count = 0
        for line in lines:
            compact = line.strip()
            if compact.startswith(list_markers):
                list_count += 1
                continue
            first, separator, _ = compact.partition(". ")
            if separator and first.isdigit():
                numbered_count += 1
        if lines and (list_count + numbered_count) / len(lines) >= 0.5:
            return "list"
        return "text"

    def _merge_small_article_sections(
        self,
        leaves: list[_ArticleLeafSection],
        *,
        max_chars: int,
    ) -> list[_ArticleLeafSection]:
        if len(leaves) <= 1:
            return leaves

        merged: list[_ArticleLeafSection] = []
        i = 0
        while i < len(leaves):
            current = leaves[i]
            current_len = self._calc_article_leaf_length(current)
            if current_len >= ARTICLE_CHUNK_MIN_CHARS:
                merged.append(current)
                i += 1
                continue

            if i + 1 < len(leaves):
                next_leaf = leaves[i + 1]
                next_len = self._calc_article_leaf_length(next_leaf)
                if (
                    current.parent_key == next_leaf.parent_key
                    and current_len + next_len <= max_chars
                ):
                    leaves[i + 1] = _ArticleLeafSection(
                        hierarchy=current.hierarchy,
                        content_blocks=current.content_blocks
                        + next_leaf.content_blocks,
                        parent_key=current.parent_key,
                    )
                    i += 1
                    continue

            merged.append(current)
            i += 1

        return merged

    def _split_large_article_sections(
        self,
        leaves: list[_ArticleLeafSection],
        *,
        target_chars: int,
        max_chars: int,
    ) -> list[_ArticleLeafSection]:
        result: list[_ArticleLeafSection] = []
        for leaf in leaves:
            if self._calc_article_leaf_length(leaf) <= target_chars:
                result.append(leaf)
                continue
            result.extend(
                self._split_article_leaf(
                    leaf,
                    target_chars=target_chars,
                    max_chars=max_chars,
                )
            )
        return result

    def _split_article_leaf(
        self,
        leaf: _ArticleLeafSection,
        *,
        target_chars: int,
        max_chars: int,
    ) -> list[_ArticleLeafSection]:
        split_result: list[_ArticleLeafSection] = []
        current_blocks: list[_ArticleContentBlock] = []
        current_len = 0

        def emit_current() -> None:
            nonlocal current_blocks, current_len
            if not current_blocks:
                return
            split_result.append(
                _ArticleLeafSection(
                    hierarchy=list(leaf.hierarchy),
                    content_blocks=current_blocks,
                    parent_key=leaf.parent_key,
                )
            )
            current_blocks = []
            current_len = 0

        for block in leaf.content_blocks:
            block_len = len(block.text)
            if block_len > max_chars:
                emit_current()
                for sub_block in self._split_oversized_article_block(
                    block,
                    max_chars=max_chars,
                ):
                    split_result.append(
                        _ArticleLeafSection(
                            hierarchy=list(leaf.hierarchy),
                            content_blocks=[sub_block],
                            parent_key=leaf.parent_key,
                        )
                    )
                continue

            if current_blocks and current_len + block_len > target_chars:
                emit_current()

            current_blocks.append(block)
            current_len += block_len

        emit_current()
        return split_result

    def _split_oversized_article_block(
        self,
        block: _ArticleContentBlock,
        *,
        max_chars: int,
    ) -> list[_ArticleContentBlock]:
        if block.block_type == "table":
            return self._split_table_article_block(block, max_chars=max_chars)
        if block.block_type == "list":
            return self._split_list_article_block(block, max_chars=max_chars)
        if block.block_type == "code":
            return [block]
        return self._split_text_article_block(block, max_chars=max_chars)

    @staticmethod
    def _split_table_article_block(
        block: _ArticleContentBlock,
        *,
        max_chars: int,
    ) -> list[_ArticleContentBlock]:
        lines = block.text.splitlines()
        if len(lines) < 3:
            return [block]
        header_lines = lines[:2]
        data_lines = lines[2:]
        header_text = "\n".join(header_lines)
        result: list[_ArticleContentBlock] = []
        current_data: list[str] = []
        current_len = len(header_text)

        for data_line in data_lines:
            line_len = len(data_line) + 1
            if current_data and current_len + line_len > max_chars:
                result.append(
                    _ArticleContentBlock(
                        block_type="table",
                        text=f"{header_text}\n" + "\n".join(current_data),
                    )
                )
                current_data = []
                current_len = len(header_text)
            current_data.append(data_line)
            current_len += line_len

        if current_data:
            result.append(
                _ArticleContentBlock(
                    block_type="table",
                    text=f"{header_text}\n" + "\n".join(current_data),
                )
            )
        return result or [block]

    @staticmethod
    def _split_list_article_block(
        block: _ArticleContentBlock,
        *,
        max_chars: int,
    ) -> list[_ArticleContentBlock]:
        groups: list[list[str]] = []
        current_group: list[str] = []
        for line in block.text.splitlines():
            stripped = line.strip()
            is_top_level = bool(stripped) and line == line.lstrip()
            if is_top_level and current_group:
                groups.append(current_group)
                current_group = [line]
                continue
            current_group.append(line)
        if current_group:
            groups.append(current_group)

        result: list[_ArticleContentBlock] = []
        current_lines: list[str] = []
        current_len = 0
        for group in groups:
            group_len = len("\n".join(group))
            if current_lines and current_len + group_len > max_chars:
                result.append(
                    _ArticleContentBlock(
                        block_type="list",
                        text="\n".join(current_lines),
                    )
                )
                current_lines = []
                current_len = 0
            current_lines.extend(group)
            current_len += group_len
        if current_lines:
            result.append(
                _ArticleContentBlock(
                    block_type="list",
                    text="\n".join(current_lines),
                )
            )
        return result or [block]

    @staticmethod
    def _split_text_article_block(
        block: _ArticleContentBlock,
        *,
        max_chars: int,
    ) -> list[_ArticleContentBlock]:
        result: list[_ArticleContentBlock] = []
        current_lines: list[str] = []
        current_len = 0
        for line in block.text.splitlines() or [block.text]:
            if len(line) > max_chars:
                if current_lines:
                    result.append(
                        _ArticleContentBlock(
                            block_type="text",
                            text="\n".join(current_lines),
                        )
                    )
                    current_lines = []
                    current_len = 0
                result.extend(
                    _ArticleContentBlock(
                        block_type="text",
                        text=line[index : index + max_chars].strip(),
                    )
                    for index in range(0, len(line), max_chars)
                    if line[index : index + max_chars].strip()
                )
                continue

            line_len = len(line) + 1
            if current_lines and current_len + line_len > max_chars:
                result.append(
                    _ArticleContentBlock(
                        block_type="text",
                        text="\n".join(current_lines),
                    )
                )
                current_lines = []
                current_len = 0
            current_lines.append(line)
            current_len += line_len

        if current_lines:
            result.append(
                _ArticleContentBlock(
                    block_type="text",
                    text="\n".join(current_lines),
                )
            )
        return result or [block]

    def _merge_post_split_article_sections(
        self,
        leaves: list[_ArticleLeafSection],
        *,
        max_chars: int,
    ) -> list[_ArticleLeafSection]:
        if len(leaves) <= 1:
            return leaves

        result = list(leaves)
        i = 0
        while i < len(result):
            current = result[i]
            if self._calc_article_leaf_length(current) >= ARTICLE_CHUNK_MIN_CHARS:
                i += 1
                continue

            prev = result[i - 1] if i > 0 else None
            next_leaf = result[i + 1] if i + 1 < len(result) else None
            direction = self._choose_article_merge_direction(
                prev=prev,
                current=current,
                next_leaf=next_leaf,
                max_chars=max_chars,
            )
            if direction is None:
                i += 1
                continue

            if direction == "prev" and prev is not None:
                result[i - 1] = _ArticleLeafSection(
                    hierarchy=prev.hierarchy,
                    content_blocks=prev.content_blocks + current.content_blocks,
                    parent_key=prev.parent_key,
                )
                result.pop(i)
                continue

            if direction == "next" and next_leaf is not None:
                result[i] = _ArticleLeafSection(
                    hierarchy=next_leaf.hierarchy,
                    content_blocks=current.content_blocks + next_leaf.content_blocks,
                    parent_key=next_leaf.parent_key,
                )
                result.pop(i + 1)
                continue

            i += 1

        return result

    def _choose_article_merge_direction(
        self,
        *,
        prev: _ArticleLeafSection | None,
        current: _ArticleLeafSection,
        next_leaf: _ArticleLeafSection | None,
        max_chars: int,
    ) -> str | None:
        candidates: list[tuple[str, _ArticleLeafSection]] = []
        current_len = self._calc_article_leaf_length(current)
        if (
            prev is not None
            and prev.hierarchy == current.hierarchy
            and current_len + self._calc_article_leaf_length(prev) <= max_chars
        ):
            candidates.append(("prev", prev))
        if (
            next_leaf is not None
            and next_leaf.hierarchy == current.hierarchy
            and current_len + self._calc_article_leaf_length(next_leaf) <= max_chars
        ):
            candidates.append(("next", next_leaf))
        if not candidates:
            return None
        if len(candidates) == 1:
            return candidates[0][0]

        prev_leaf = candidates[0][1]
        next_candidate = candidates[1][1]
        prev_prefix = self._common_prefix_len(current.hierarchy, prev_leaf.hierarchy)
        next_prefix = self._common_prefix_len(
            current.hierarchy,
            next_candidate.hierarchy,
        )
        if prev_prefix != next_prefix:
            return "prev" if prev_prefix > next_prefix else "next"

        prev_len = self._calc_article_leaf_length(prev_leaf)
        next_len = self._calc_article_leaf_length(next_candidate)
        return "prev" if prev_len <= next_len else "next"

    def _build_article_chunks(
        self,
        *,
        header: str,
        leaves: list[_ArticleLeafSection],
    ) -> list[_ArticleChunk]:
        chunks: list[_ArticleChunk] = []
        for leaf in leaves:
            body = "\n\n".join(
                block.text for block in leaf.content_blocks if block.text
            ).strip()
            section_prefix = self._build_article_section_prefix(leaf.hierarchy)
            content_parts = [header]
            if section_prefix:
                content_parts.append(section_prefix)
            heading_text = leaf.hierarchy[-1] if leaf.hierarchy else ""
            if heading_text and not body.startswith(heading_text):
                content_parts.append(heading_text)
            if body:
                content_parts.append(body)
            chunks.append(
                _ArticleChunk(
                    content="\n\n".join(content_parts).strip(),
                    section_hierarchy=list(leaf.hierarchy),
                )
            )
        return chunks

    @staticmethod
    def _build_article_section_prefix(hierarchy: list[str]) -> str:
        if not hierarchy:
            return ""
        return f"[Section: {' > '.join(hierarchy)}]"

    @staticmethod
    def _calc_article_leaf_length(leaf: _ArticleLeafSection) -> int:
        return sum(len(block.text or "") for block in leaf.content_blocks)

    @staticmethod
    def _common_prefix_len(left: list[str], right: list[str]) -> int:
        count = 0
        for left_item, right_item in zip(left, right):
            if left_item != right_item:
                break
            count += 1
        return count

    def _split_body_into_chunks(
        self,
        body: str,
        *,
        max_chars: int,
        target_chars: int,
    ) -> tuple[str, ...]:
        paragraphs = self._split_paragraphs(body)
        chunks: list[str] = []
        current = ""

        for paragraph in paragraphs:
            for part in self._hard_split(paragraph, max_chars=max_chars):
                candidate = part if not current else f"{current}\n\n{part}"
                if len(candidate) <= target_chars or not current:
                    current = candidate
                    continue
                chunks.append(current)
                current = part

        if current:
            chunks.append(current)
        if len(chunks) >= 2 and len(chunks[-1]) < ARTICLE_CHUNK_MIN_CHARS:
            candidate = f"{chunks[-2]}\n\n{chunks[-1]}"
            if len(candidate) <= max_chars:
                chunks[-2] = candidate
                chunks.pop()
        return tuple(chunks)

    @staticmethod
    def _split_paragraphs(body: str) -> tuple[str, ...]:
        if not body:
            return ()
        paragraphs = [
            paragraph.strip()
            for paragraph in body.replace("\r\n", "\n").split("\n\n")
            if paragraph.strip()
        ]
        if paragraphs:
            return tuple(paragraphs)
        return tuple(line.strip() for line in body.splitlines() if line.strip())

    @staticmethod
    def _hard_split(paragraph: str, *, max_chars: int) -> tuple[str, ...]:
        if len(paragraph) <= max_chars:
            return (paragraph,)
        return tuple(
            paragraph[index : index + max_chars].strip()
            for index in range(0, len(paragraph), max_chars)
            if paragraph[index : index + max_chars].strip()
        )

    @staticmethod
    def _stringify_state(
        state: ChannelTalkDocumentArticleState | str | None,
    ) -> str:
        if isinstance(state, ChannelTalkDocumentArticleState):
            return state.value
        if state is None:
            return "unknown"
        return require_text(str(state), "state")

    @staticmethod
    def _build_document_id(
        *,
        channel_id: str,
        space_id: str,
        language: str,
        article_id: str,
        chunk_index: int,
    ) -> str:
        return (
            "channel_talk:document_article:"
            f"{channel_id}:{space_id}:{language}:{article_id}:chunk:{chunk_index}"
        )

    @staticmethod
    def _build_delete_prefix(
        *,
        channel_id: str,
        space_id: str,
        language: str,
        article_id: str,
    ) -> str:
        return (
            "channel_talk:document_article:"
            f"{channel_id}:{space_id}:{language}:{article_id}:chunk:"
        )
