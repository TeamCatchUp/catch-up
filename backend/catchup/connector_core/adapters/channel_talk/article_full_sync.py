from __future__ import annotations

from langchain_core.documents import Document

from catchup.components.embedder.constants import EmbeddingProvider
from catchup.components.embedder.factory import get_embedding_service
from catchup.components.vector_db.factory import get_pgvector_repository
from catchup.components.vector_db.pgvector.repository import PGVectorRepository
from catchup.connector_core.ports.sync_ingestion import SyncWindow
from catchup.connectors.channel_talk.document_space.article_full_sync_fetcher import (
    ChannelTalkArticleFullSyncFetcher,
)
from catchup.connectors.channel_talk.document_space.article_full_sync_models import (
    DEFAULT_ARTICLE_FULL_SYNC_STATES,
)
from catchup.connectors.channel_talk.document_space.article_full_sync_models import (
    ChannelTalkArticleFullSyncCheckpoint,
)
from catchup.connectors.channel_talk.document_space.article_full_sync_models import (
    ChannelTalkArticleFullSyncConnection,
)
from catchup.connectors.channel_talk.document_space.article_full_sync_models import (
    ChannelTalkArticleFullSyncFetchResult,
)
from catchup.connectors.channel_talk.document_space.article_full_sync_models import (
    ChannelTalkArticleFullSyncPersistResult,
)
from catchup.connectors.channel_talk.document_space.article_full_sync_models import (
    ChannelTalkArticleFullSyncSummaryResult,
)
from catchup.connectors.channel_talk.document_space.article_full_sync_models import (
    ChannelTalkArticleFullSyncTransformResult,
)
from catchup.connectors.channel_talk.document_space.article_full_sync_models import (
    ChannelTalkArticlePreparedDocument,
)
from catchup.connectors.channel_talk.document_space.article_full_sync_models import (
    ChannelTalkArticleSyncExecutionRequest,
)
from catchup.connectors.channel_talk.document_space.article_full_sync_models import (
    ChannelTalkArticleSyncExecutionResult,
)
from catchup.connectors.channel_talk.document_space.article_full_sync_models import (
    ChannelTalkFetchedArticlesResult,
)
from catchup.connectors.channel_talk.document_space.article_transformer import (
    ArticleTransformer,
)

CHANNEL_TALK_ARTICLE_LANGUAGE = "ko"


class ChannelTalkArticleFullSyncIngestionAdapter:
    """Channel Talk Documents article sweep/list ingestion adapter."""

    def __init__(
        self,
    ) -> None:
        self._fetcher: ChannelTalkArticleFullSyncFetcher | None = None
        self._document_builder = ArticleTransformer(
            language=CHANNEL_TALK_ARTICLE_LANGUAGE
        )
        self._repository: PGVectorRepository | None = None

    async def fetch(
        self,
        *,
        execution: ChannelTalkArticleSyncExecutionRequest,
        sync_window: SyncWindow,
    ) -> ChannelTalkArticleFullSyncFetchResult:
        # API paging은 fetcher가 처리하고, adapter는 pipeline이 이어서 사용할 fetch result와 next checkpoint만 조립
        fetched_articles = await self._get_fetcher().fetch_articles(
            connection=ChannelTalkArticleFullSyncConnection.from_credentials_record(
                execution.document_connection,
            ),
            language=CHANNEL_TALK_ARTICLE_LANGUAGE,
            sync_window=sync_window,
            states=DEFAULT_ARTICLE_FULL_SYNC_STATES,
            checkpoint_state=(
                execution.checkpoint.state if execution.checkpoint is not None else None
            ),
            checkpoint_cursor=(
                execution.checkpoint.next_cursor
                if execution.checkpoint is not None
                else None
            ),
        )
        return ChannelTalkArticleFullSyncFetchResult(
            channel_id=execution.channel_id,
            space_id=execution.space_id,
            language=CHANNEL_TALK_ARTICLE_LANGUAGE,
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
        execution: ChannelTalkArticleSyncExecutionRequest,
        sync_window: SyncWindow,
        fetched: ChannelTalkArticleFullSyncFetchResult,
    ) -> ChannelTalkArticleFullSyncTransformResult:
        # 중복 제거된 article만 adapter에 남기고, content/metadata/id 조립은 ArticleTransformer가 수행한다.
        documents: list[ChannelTalkArticlePreparedDocument] = []
        delete_prefixes: list[str] = []
        seen_article_ids: set[str] = set()

        for bundle in fetched.bundles:
            if bundle.article_id in seen_article_ids:
                continue
            seen_article_ids.add(bundle.article_id)
            transformed_bundle = self._document_builder.transform(
                execution=execution,
                sync_window=sync_window,
                bundle=bundle,
            )
            documents.extend(
                ChannelTalkArticlePreparedDocument(
                    document_id=document.document_id,
                    article_id=document.article_id,
                    page_content=document.page_content,
                    logical_metadata=document.logical_metadata,
                    storage_metadata=document.storage_metadata,
                )
                for document in transformed_bundle.documents
            )
            delete_prefixes.append(transformed_bundle.delete_prefix)

        return ChannelTalkArticleFullSyncTransformResult(
            documents=tuple(documents),
            delete_prefixes=tuple(dict.fromkeys(delete_prefixes)),
        )

    async def summarize(
        self,
        *,
        execution: ChannelTalkArticleSyncExecutionRequest,
        sync_window: SyncWindow,
        transformed: ChannelTalkArticleFullSyncTransformResult,
    ) -> ChannelTalkArticleFullSyncSummaryResult:
        # Channel Talk Article은 Summarize를 수행하지 않는다.
        # pipeline contract를 유지하는 no-op placeholder
        _ = self
        _ = execution
        _ = sync_window
        return ChannelTalkArticleFullSyncSummaryResult(
            summary_applied=False,
            document_count=len(transformed.documents),
        )

    async def persist(
        self,
        *,
        execution: ChannelTalkArticleSyncExecutionRequest,
        sync_window: SyncWindow,
        transformed: ChannelTalkArticleFullSyncTransformResult,
        summary: ChannelTalkArticleFullSyncSummaryResult,
    ) -> ChannelTalkArticleFullSyncPersistResult:
        # TODO : repository에서 Upsert의 원자성을 보장하는 메서드 생성 후 교체
        _ = execution
        _ = sync_window
        _ = summary
        repository = await self._get_repository()

        for prefix in transformed.delete_prefixes:
            await repository.delete_by_id_prefix(prefix)

        if not transformed.documents:
            return ChannelTalkArticleFullSyncPersistResult(
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
        return ChannelTalkArticleFullSyncPersistResult(
            persisted_count=len(persisted_ids),
            persisted_ids=tuple(persisted_ids),
            deleted_prefixes=transformed.delete_prefixes,
        )

    def build_result(
        self,
        *,
        execution: ChannelTalkArticleSyncExecutionRequest,
        sync_window: SyncWindow,
        fetched: ChannelTalkArticleFullSyncFetchResult,
        transformed: ChannelTalkArticleFullSyncTransformResult,
        summary: ChannelTalkArticleFullSyncSummaryResult,
        persisted: ChannelTalkArticleFullSyncPersistResult,
    ) -> ChannelTalkArticleSyncExecutionResult:
        _ = self
        _ = sync_window
        return ChannelTalkArticleSyncExecutionResult(
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
        execution: ChannelTalkArticleSyncExecutionRequest,
        fetched_articles: ChannelTalkFetchedArticlesResult,
    ) -> ChannelTalkArticleFullSyncCheckpoint | None:
        if fetched_articles.next_checkpoint_state is None:
            return None
        return ChannelTalkArticleFullSyncCheckpoint(
            tenant_id=execution.tenant_id,
            space_id=execution.space_id,
            state=fetched_articles.next_checkpoint_state,
            next_cursor=fetched_articles.next_checkpoint_cursor,
        )

    async def _get_repository(self) -> PGVectorRepository:
        # Repository는 persist에서만 필요하므로 처음 쓰는 시점에 만들고 재사용한다.
        # initialize()의 idempotency에 초기화 여부 판단을 맡겨 흐름을 단순하게 유지한다.
        if self._repository is not None:
            return self._repository

        repository = self._build_repository()
        await repository.initialize(None)
        self._repository = repository
        return repository

    def _get_fetcher(self) -> ChannelTalkArticleFullSyncFetcher:
        if self._fetcher is None:
            self._fetcher = ChannelTalkArticleFullSyncFetcher()
        return self._fetcher

    @staticmethod
    def _build_repository() -> PGVectorRepository:
        embedder = get_embedding_service(EmbeddingProvider.AWS_BEDROCK).get_embedder()
        return get_pgvector_repository(
            embeddings=embedder
        )


ChannelTalkArticleFullSyncAdapter = ChannelTalkArticleFullSyncIngestionAdapter
