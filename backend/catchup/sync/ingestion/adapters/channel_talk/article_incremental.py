from __future__ import annotations

from langchain_core.documents import Document

from catchup.components.embedder.constants import EmbeddingProvider
from catchup.components.embedder.factory import get_embedding_service
from catchup.components.vector_db.factory import get_pgvector_repository
from catchup.components.vector_db.factory import get_v2_knowledge_repository
from catchup.components.vector_db.factory import get_v2_vector_store
from catchup.components.vector_db.pgvector.repository import PGVectorRepository
from catchup.components.vector_db.v2 import V2KnowledgeRepository
from catchup.components.vector_db.v2 import VectorStore
from catchup.connectors.channel_talk.document_space.article_full_sync_fetcher import (
    ChannelTalkArticleFullSyncFetcher,
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
    ChannelTalkArticleIncrementalExecutionRequest,
)
from catchup.sync.ingestion.adapters.channel_talk.article_models import (
    ChannelTalkArticleIncrementalExecutionResult,
)
from catchup.sync.ingestion.adapters.channel_talk.article_models import (
    ChannelTalkArticlePreparedDocument,
)
from catchup.sync.ingestion.adapters.channel_talk.article_models import (
    ChannelTalkArticleSyncExecutionRequest,
)
from catchup.sync.ingestion.adapters.channel_talk.article_v2_document_builder import (
    ChannelTalkArticleV2DocumentBuilder,
)
from catchup.sync.ingestion.document_builders.channel_talk_article import (
    ArticleTransformer,
)
from catchup.sync.ingestion.dual_write import DualWriter
from catchup.sync.ingestion.pipeline import run_sync_ingestion
from catchup.sync.ingestion.schemas import SyncWindow

CHANNEL_TALK_ARTICLE_LANGUAGE = "ko"


class ChannelTalkArticleIncrementalIngestionAdapter:
    """Exact-refresh ingestion adapter for Channel Talk Documents article records."""

    def __init__(
        self,
        *,
        enable_v2_dual_write: bool = False,
        vector_store: VectorStore | None = None,
        v2_knowledge_repository: V2KnowledgeRepository | None = None,
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
        self._v2_knowledge_repository = v2_knowledge_repository

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
        delete_record_ids: list[str] = []
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
            delete_record_ids.append(bundle.article_id)

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
            delete_record_ids=tuple(dict.fromkeys(delete_record_ids)),
            v2_documents=tuple(v2_documents),
            v2_failed_ids=v2_failed_ids,
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
            v2_documents=transformed.v2_documents,
        )

    async def persist(
        self,
        *,
        execution: ChannelTalkArticleIncrementalExecutionRequest,
        sync_window: SyncWindow,
        transformed: ChannelTalkArticleFullSyncTransformResult,
        summary: ChannelTalkArticleFullSyncSummaryResult,
    ) -> ChannelTalkArticleFullSyncPersistResult:
        _ = sync_window
        repository = await self._get_repository()
        v2_failed_ids = tuple(transformed.v2_failed_ids)

        for prefix in transformed.delete_prefixes:
            await repository.delete_by_id_prefix(prefix)
        v2_failed_ids = await self._delete_v2_chunk_records(
            record_ids=transformed.delete_record_ids,
            existing_failed_ids=v2_failed_ids,
            channel_id=execution.channel_id,
            space_id=execution.space_id,
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

    def _get_v2_knowledge_repository(self) -> V2KnowledgeRepository | None:
        if not self._enable_v2_dual_write:
            return None
        if self._v2_knowledge_repository is None:
            self._v2_knowledge_repository = get_v2_knowledge_repository()
        return self._v2_knowledge_repository

    async def _delete_v2_chunk_records(
        self,
        *,
        record_ids: tuple[str, ...],
        existing_failed_ids: tuple[str, ...],
        channel_id: str,
        space_id: str,
    ) -> tuple[str, ...]:
        if not record_ids or not self._enable_v2_dual_write:
            return existing_failed_ids

        v2_knowledge_repository = self._get_v2_knowledge_repository()
        if v2_knowledge_repository is None:
            return tuple(
                dict.fromkeys(
                    (
                        *existing_failed_ids,
                        *(
                            _article_chunk_prefix(channel_id, space_id, record_id)
                            for record_id in record_ids
                        ),
                    )
                )
            )

        failed_ids = list(existing_failed_ids)
        for record_id in record_ids:
            try:
                await v2_knowledge_repository.delete_multiple_chunks_by_id(
                    source="channel_talk",
                    entity_type="document_article",
                    scope_id=channel_id,
                    target_id=space_id,
                    record_id=record_id,
                )
            except Exception:
                failed_ids.append(_article_chunk_prefix(channel_id, space_id, record_id))
        return tuple(dict.fromkeys(failed_ids))

    def _get_fetcher(self) -> ChannelTalkArticleFullSyncFetcher:
        if self._fetcher is None:
            self._fetcher = ChannelTalkArticleFullSyncFetcher()
        return self._fetcher

    @staticmethod
    def _build_repository() -> PGVectorRepository:
        embedder = get_embedding_service(EmbeddingProvider.AWS_BEDROCK).get_embedder()
        return get_pgvector_repository(embeddings=embedder)

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


def _article_chunk_prefix(
    channel_id: str,
    space_id: str,
    article_id: str,
) -> str:
    return (
        "channel_talk:document_article:"
        f"{channel_id}:{space_id}:{CHANNEL_TALK_ARTICLE_LANGUAGE}:{article_id}:chunk:"
    )


ChannelTalkArticleIncrementalAdapter = ChannelTalkArticleIncrementalIngestionAdapter
