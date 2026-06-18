from __future__ import annotations

from langchain_core.documents import Document

from catchup.components.embedder.constants import EmbeddingProvider
from catchup.components.embedder.factory import get_embedding_service
from catchup.components.vector_db.factory import get_pgvector_repository
from catchup.components.vector_db.factory import get_v2_vector_store
from catchup.components.vector_db.pgvector.repository import PGVectorRepository
from catchup.components.vector_db.v2 import VectorStore
from catchup.connectors.channel_talk.document_space.article_full_sync_fetcher import (
    ChannelTalkArticleFullSyncFetcher,
)
from catchup.sync.ingestion.adapters.channel_talk.article_models import (
    DEFAULT_ARTICLE_FULL_SYNC_STATES,
)
from catchup.sync.ingestion.adapters.channel_talk.article_models import (
    ChannelTalkArticleFullSyncCheckpoint,
)
from catchup.sync.ingestion.adapters.channel_talk.article_models import (
    ChannelTalkArticleFullSyncConnection,
)
from catchup.sync.ingestion.adapters.channel_talk.article_models import (
    ChannelTalkArticleFullSyncFetchResult,
)
from catchup.sync.ingestion.adapters.channel_talk.article_models import (
    ChannelTalkArticleFullSyncPersistResult,
)
from catchup.sync.ingestion.adapters.channel_talk.article_models import (
    ChannelTalkArticleFullSyncSummaryResult,
)
from catchup.sync.ingestion.adapters.channel_talk.article_models import (
    ChannelTalkArticleFullSyncTransformResult,
)
from catchup.sync.ingestion.adapters.channel_talk.article_models import (
    ChannelTalkArticlePreparedDocument,
)
from catchup.sync.ingestion.adapters.channel_talk.article_models import (
    ChannelTalkArticleSyncExecutionRequest,
)
from catchup.sync.ingestion.adapters.channel_talk.article_models import (
    ChannelTalkArticleSyncExecutionResult,
)
from catchup.sync.ingestion.adapters.channel_talk.article_models import (
    ChannelTalkFetchedArticlesResult,
)
from catchup.sync.ingestion.adapters.channel_talk.article_v2_document_builder import (
    ChannelTalkArticleV2DocumentBuilder,
)
from catchup.sync.ingestion.document_builders.channel_talk_article import (
    ArticleTransformer,
)
from catchup.sync.ingestion.dual_write import DualWriter
from catchup.sync.ingestion.schemas import SyncWindow

CHANNEL_TALK_ARTICLE_LANGUAGE = "ko"


class ChannelTalkArticleFullSyncIngestionAdapter:
    """Channel Talk Documents article sweep/list ingestion adapter."""

    def __init__(
        self,
        *,
        enable_v2_dual_write: bool = False,
        vector_store: VectorStore | None = None,
        v2_document_builder: ChannelTalkArticleV2DocumentBuilder | None = None,
    ) -> None:
        self._fetcher: ChannelTalkArticleFullSyncFetcher | None = None
        self._document_builder = ArticleTransformer(
            language=CHANNEL_TALK_ARTICLE_LANGUAGE
        )
        self._v2_document_builder = (
            v2_document_builder or ChannelTalkArticleV2DocumentBuilder()
        )
        self._enable_v2_dual_write = enable_v2_dual_write
        self._repository: PGVectorRepository | None = None
        self._vector_store = vector_store

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
                    chunk_body_text=document.chunk_body_text,
                    logical_metadata=document.logical_metadata,
                    storage_metadata=document.storage_metadata,
                )
                for document in transformed_bundle.documents
            )
            delete_prefixes.append(transformed_bundle.delete_prefix)

        v2_documents = []
        v2_failed_ids: tuple[str, ...] = ()
        if self._enable_v2_dual_write:
            v2_documents, v2_failed_ids = (
                self._v2_document_builder.build_from_prepared_documents(
                    prepared_documents=tuple(documents),
                )
            )

        return ChannelTalkArticleFullSyncTransformResult(
            documents=tuple(documents),
            delete_prefixes=tuple(dict.fromkeys(delete_prefixes)),
            v2_documents=tuple(v2_documents),
            v2_failed_ids=v2_failed_ids,
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
            v2_documents=transformed.v2_documents,
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
        _ = sync_window
        repository = await self._get_repository()
        v2_failed_ids = tuple(transformed.v2_failed_ids)

        for prefix in transformed.delete_prefixes:
            await repository.delete_by_id_prefix(prefix)
        v2_failed_ids = await self._delete_v2_prefixes(
            prefixes=transformed.delete_prefixes,
            existing_failed_ids=v2_failed_ids,
        )

        if not transformed.documents:
            return ChannelTalkArticleFullSyncPersistResult(
                persisted_count=0,
                persisted_ids=(),
                deleted_prefixes=transformed.delete_prefixes,
                v2_error_count=len(v2_failed_ids),
                v2_failed_ids=v2_failed_ids,
            )

        documents = self._to_langchain_documents(transformed.documents)
        document_ids = [document.document_id for document in transformed.documents]
        if summary.v2_documents:
            try:
                vector_store = await self._get_vector_store()
            except Exception:
                persisted_ids = await repository.add_documents(
                    documents,
                    ids=document_ids,
                )
                v2_failed_ids = tuple(
                    dict.fromkeys(
                        (
                            *v2_failed_ids,
                            *(str(document.id) for document in summary.v2_documents),
                        )
                    )
                )
            else:
                result = await DualWriter(
                    repository=repository,
                    vector_store=vector_store,
                ).upsert_documents(
                    source_documents=documents,
                    vector_documents=list(summary.v2_documents),
                    ids=document_ids,
                    audit_context=execution.audit_context,
                    context=(
                        "entity_type=document_article,"
                        f"channel_id={execution.channel_id},"
                        f"space_id={execution.space_id},"
                        f"doc_count={len(documents)}"
                    ),
                )
                persisted_ids = result.persisted_ids
                v2_failed_ids = tuple(
                    dict.fromkeys((*v2_failed_ids, *result.vector_failed_ids))
                )
        else:
            persisted_ids = await repository.add_documents(documents, ids=document_ids)

        return ChannelTalkArticleFullSyncPersistResult(
            persisted_count=len(persisted_ids),
            persisted_ids=tuple(persisted_ids),
            deleted_prefixes=transformed.delete_prefixes,
            v2_error_count=len(v2_failed_ids),
            v2_failed_ids=v2_failed_ids,
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
            persisted_count=persisted.persisted_count,
            failed_count=persisted.v2_error_count,
            v2_failed_count=persisted.v2_error_count,
            v2_failed_ids=persisted.v2_failed_ids,
            fetched=fetched,
            transformed=transformed,
            summary=summary,
            persisted=persisted,
            metadata={
                "v2_failed_count": persisted.v2_error_count,
                "v2_failed_ids": list(persisted.v2_failed_ids),
            },
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

    async def _get_vector_store(self) -> VectorStore | None:
        if not self._enable_v2_dual_write:
            return None
        if self._vector_store is None:
            embeddings = get_embedding_service(
                EmbeddingProvider.AWS_BEDROCK
            ).get_embedder()
            vector_store = get_v2_vector_store(embeddings)
            await vector_store.initialize()
            self._vector_store = vector_store
        return self._vector_store

    async def _delete_v2_prefixes(
        self,
        *,
        prefixes: tuple[str, ...],
        existing_failed_ids: tuple[str, ...],
    ) -> tuple[str, ...]:
        if not prefixes or not self._enable_v2_dual_write:
            return existing_failed_ids

        try:
            vector_store = await self._get_vector_store()
        except Exception:
            return tuple(dict.fromkeys((*existing_failed_ids, *prefixes)))
        if vector_store is None:
            return tuple(dict.fromkeys((*existing_failed_ids, *prefixes)))

        failed_ids = list(existing_failed_ids)
        for prefix in prefixes:
            try:
                await vector_store.delete_by_id_prefix(prefix)
            except Exception:
                failed_ids.append(prefix)
        return tuple(dict.fromkeys(failed_ids))

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

    @staticmethod
    def _to_langchain_documents(
        documents: tuple[ChannelTalkArticlePreparedDocument, ...],
    ) -> list[Document]:
        return [
            Document(
                id=document.document_id,
                page_content=document.page_content,
                metadata=document.storage_metadata,
            )
            for document in documents
        ]


ChannelTalkArticleFullSyncAdapter = ChannelTalkArticleFullSyncIngestionAdapter
