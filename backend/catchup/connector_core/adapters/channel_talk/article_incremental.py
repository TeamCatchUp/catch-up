from __future__ import annotations

from langchain_core.documents import Document

from catchup.components.embedder.constants import EmbeddingProvider
from catchup.components.embedder.factory import get_embedding_service
from catchup.components.vector_db.factory import get_pgvector_repository
from catchup.components.vector_db.pgvector.repository import PGVectorRepository
from catchup.connector_core.application.sync_ingestion import run_sync_ingestion
from catchup.connector_core.ports.sync_ingestion import SyncWindow
from catchup.connectors.channel_talk.document_space.article_full_sync_fetcher import (
    ChannelTalkArticleFullSyncFetcher,
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
    ChannelTalkArticleIncrementalExecutionRequest,
)
from catchup.connectors.channel_talk.document_space.article_full_sync_models import (
    ChannelTalkArticleIncrementalExecutionResult,
)
from catchup.connectors.channel_talk.document_space.article_full_sync_models import (
    ChannelTalkArticlePreparedDocument,
)
from catchup.connectors.channel_talk.document_space.article_full_sync_models import (
    ChannelTalkArticleSyncExecutionRequest,
)
from catchup.connectors.channel_talk.document_space.article_transformer import (
    ArticleTransformer,
)

CHANNEL_TALK_ARTICLE_LANGUAGE = "ko"


class ChannelTalkArticleIncrementalIngestionAdapter:
    """Exact-refresh ingestion adapter for Channel Talk Documents article records."""

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
        execution: ChannelTalkArticleIncrementalExecutionRequest,
        sync_window: SyncWindow,
    ) -> ChannelTalkArticleFullSyncFetchResult:
        _ = sync_window
        bundle = await self._get_fetcher().fetch_article_bundle_by_id(
            connection=ChannelTalkArticleFullSyncConnection.from_credentials_record(
                execution.document_connection,
            ),
            article_id=execution.article_id,
            language=CHANNEL_TALK_ARTICLE_LANGUAGE,
        )
        return ChannelTalkArticleFullSyncFetchResult(
            channel_id=execution.channel_id,
            space_id=execution.space_id,
            language=CHANNEL_TALK_ARTICLE_LANGUAGE,
            bundles=(bundle,),
            fetched_count=1,
            fetched_article_ids=(bundle.article_id,),
        )

    async def transform(
        self,
        *,
        execution: ChannelTalkArticleIncrementalExecutionRequest,
        sync_window: SyncWindow,
        fetched: ChannelTalkArticleFullSyncFetchResult,
    ) -> ChannelTalkArticleFullSyncTransformResult:
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
        execution: ChannelTalkArticleIncrementalExecutionRequest,
        sync_window: SyncWindow,
        transformed: ChannelTalkArticleFullSyncTransformResult,
    ) -> ChannelTalkArticleFullSyncSummaryResult:
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
        execution: ChannelTalkArticleIncrementalExecutionRequest,
        sync_window: SyncWindow,
        transformed: ChannelTalkArticleFullSyncTransformResult,
        summary: ChannelTalkArticleFullSyncSummaryResult,
    ) -> ChannelTalkArticleFullSyncPersistResult:
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
        execution: ChannelTalkArticleIncrementalExecutionRequest,
        sync_window: SyncWindow,
        fetched: ChannelTalkArticleFullSyncFetchResult,
        transformed: ChannelTalkArticleFullSyncTransformResult,
        summary: ChannelTalkArticleFullSyncSummaryResult,
        persisted: ChannelTalkArticleFullSyncPersistResult,
    ) -> ChannelTalkArticleIncrementalExecutionResult:
        _ = self
        _ = sync_window
        return ChannelTalkArticleIncrementalExecutionResult(
            tenant_id=execution.tenant_id,
            collected_count=len(fetched.fetched_article_ids),
            document_count=len(transformed.documents),
            fetched=fetched,
            transformed=transformed,
            summary=summary,
            persisted=persisted,
        )

    async def sync_article_by_id(
        self,
        *,
        execution: ChannelTalkArticleSyncExecutionRequest,
        article_id: str,
        sync_window: SyncWindow,
    ) -> ChannelTalkArticleFullSyncPersistResult:
        incremental_execution = ChannelTalkArticleIncrementalExecutionRequest(
            tenant_id=execution.tenant_id,
            channel_connection=execution.channel_connection,
            document_connection=execution.document_connection,
            checkpoint=execution.checkpoint,
            audit_context=execution.audit_context,
            article_id=article_id,
        )
        result = await run_sync_ingestion(
            port=self,
            execution=incremental_execution,
            sync_window=sync_window,
        )
        return result.persisted

    async def _get_repository(self) -> PGVectorRepository:
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
        return get_pgvector_repository(embeddings=embedder)


ChannelTalkArticleIncrementalAdapter = ChannelTalkArticleIncrementalIngestionAdapter
