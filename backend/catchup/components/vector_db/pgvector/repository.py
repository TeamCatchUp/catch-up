"""
PGVector Repository

PostgreSQL + pgvector를 사용한 벡터 저장소.
langchain-postgres 패키지를 사용하여 LangChain Document를 직접 저장/검색.

사용법:
    repository = PGVectorRepository()
    await repository.initialize()

    # 문서 저장
    await repository.add_documents(documents, ids)

    # 벡터 검색
    results = await repository.search("검색 쿼리", k=5)

    # 문서 삭제
    await repository.delete_documents(ids)
"""

import asyncio
import logging
from typing import Any

from langchain.embeddings import Embeddings
from langchain_cohere import CohereEmbeddings
from langchain_core.documents import Document
from langchain_postgres import PGVector

from sqlalchemy import delete as sa_delete

from catchup.configs.config import settings

logger = logging.getLogger(__name__)

_embedding_semaphore = asyncio.Semaphore(settings.EMBEDDING_MAX_CONCURRENCY)


class PGVectorRepository:
    """
    PGVector 벡터 저장소 Repository

    PostgreSQL의 pgvector 확장을 사용하여 LangChain Document의
    임베딩을 저장하고 시맨틱 검색을 제공합니다.

    Attributes:
        embeddings: Cohere 임베딩 모델
        vector_store: langchain-postgres PGVector 인스턴스
        _initialized: 초기화 완료 여부
    """

    def __init__(
            self,
            embeddings: Embeddings,
            collection_name: str | None = None,
        ):
        """
        PGVector Repository 초기화

        Args:
            collection_name: 벡터 저장소 컬렉션 이름 (기본값: settings에서 가져옴)
        """
        self.collection_name = collection_name or settings.PGVECTOR_COLLECTION_NAME

        # Cohere Embeddings 설정 (embed-v4.0, 1536 dimensions)
        self.embeddings = embeddings

        self.vector_store: PGVector | None = None
        self._initialized = False

    async def initialize(self) -> None:
        """
        PGVector 벡터 저장소 초기화

        PostgreSQL 연결을 설정하고 pgvector 확장이 활성화되어 있는지 확인합니다.
        FastAPI 서버 시작 시점(lifespan)에 호출됩니다.

        Raises:
            Exception: PostgreSQL 연결 또는 pgvector 확장 오류 시
        """
        if self._initialized:
            return

        logger.info(
            f"Initializing PGVector repository with collection '{self.collection_name}'"
        )

        try:
            # langchain-postgres PGVector 인스턴스 생성
            # 동기 메서드이지만 asyncio에서 호출 가능
            self.vector_store = PGVector(
                embeddings=self.embeddings,
                collection_name=self.collection_name,
                connection=settings.sqlalchemy_database_url,
                use_jsonb=True,  # metadata를 JSONB로 저장 (필터링 지원)
            )

            self._initialized = True
            logger.info(
                f"PGVector repository initialized successfully. "
                f"Collection: {self.collection_name}, "
                f"Embedding dimensions: {settings.PGVECTOR_EMBEDDING_DIMENSIONS}"
            )

        except Exception as e:
            logger.error(f"Failed to initialize PGVector repository: {e}")
            raise

    def _ensure_initialized(self) -> None:
        """초기화 확인"""
        if not self._initialized or self.vector_store is None:
            raise RuntimeError(
                "PGVectorRepository not initialized. "
                "Call await repository.initialize() first."
            )

    async def add_documents(
        self,
        documents: list[Document],
        ids: list[str] | None = None,
    ) -> list[str]:
        """
        문서를 벡터 저장소에 추가

        Args:
            documents: 저장할 LangChain Document 리스트
            ids: 각 문서의 고유 ID (없으면 자동 생성)
                 형식: "jira:issue:CATCH-145", "jira:epic:CATCH-100" 등

        Returns:
            저장된 문서의 ID 리스트

        Example:
            docs = [Document(page_content="...", metadata={...})]
            ids = ["jira:issue:CATCH-145"]
            await repository.add_documents(docs, ids)
        """
        self._ensure_initialized()

        if not documents:
            logger.warning("No documents to add")
            return []

        logger.info(f"Adding {len(documents)} documents to PGVector")

        try:
            # 임베딩 생성 및 저장 (rate limit 적용)
            async with _embedding_semaphore:
                # langchain-postgres의 add_documents는 동기 메서드
                # asyncio.to_thread로 비동기 실행
                result_ids = await asyncio.to_thread(
                    self.vector_store.add_documents,
                    documents,
                    ids=ids,
                )

            logger.info(f"Successfully added {len(result_ids)} documents")
            return result_ids

        except Exception as e:
            logger.error(f"Failed to add documents: {e}")
            raise

    async def generate_embeddings(
        self,
        documents: list[Document],
    ) -> list[list[float]]:
        """
        문서 임베딩만 생성 (DB 저장 없음)

        EMBEDDING_BATCH_SIZE 단위로 서브배치 분할하여 Embedding API를 호출합니다.
        서브배치별로 _embedding_semaphore를 획득하므로, 전체 동시 API 호출 수가
        EMBEDDING_MAX_CONCURRENCY 이내로 제한됩니다.

        Args:
            documents: 임베딩을 생성할 Document 리스트

        Returns:
            임베딩 벡터 리스트 (documents와 동일 순서)
        """
        self._ensure_initialized()

        if not documents:
            return []

        texts = [doc.page_content for doc in documents]
        batch_size = settings.EMBEDDING_BATCH_SIZE

        logger.info(f"Generating embeddings for {len(documents)} documents (batch_size={batch_size})")

        try:
            # 서브배치 분할 후 병렬 호출
            async def _embed_sub_batch(sub_texts: list[str]) -> list[list[float]]:
                async with _embedding_semaphore:
                    return await asyncio.to_thread(
                        self.embeddings.embed_documents, sub_texts
                    )

            tasks = [
                _embed_sub_batch(texts[i : i + batch_size])
                for i in range(0, len(texts), batch_size)
            ]
            sub_results = await asyncio.gather(*tasks)

            # 서브배치 결과를 순서대로 합침
            embeddings = [emb for sub in sub_results for emb in sub]

            logger.info(f"Successfully generated {len(embeddings)} embeddings")
            return embeddings

        except Exception as e:
            logger.error(f"Failed to generate embeddings: {e}")
            raise

    async def store_with_embeddings(
        self,
        documents: list[Document],
        embeddings: list[list[float]],
        ids: list[str],
    ) -> list[str]:
        """
        사전 생성된 임베딩과 함께 문서 저장 (임베딩 생성 없음)

        generate_embeddings로 생성한 임베딩을 받아 DB INSERT만 수행합니다.
        Embedding API 호출이 없으므로 _embedding_semaphore를 사용하지 않습니다.

        Args:
            documents: 저장할 Document 리스트
            embeddings: 사전 생성된 임베딩 벡터 리스트
            ids: 문서 ID 리스트

        Returns:
            저장된 문서 ID 리스트
        """
        self._ensure_initialized()

        if not documents:
            return []

        texts = [doc.page_content for doc in documents]
        metadatas = [doc.metadata for doc in documents]

        logger.info(f"Storing {len(documents)} documents with pre-computed embeddings")

        try:
            result_ids = await asyncio.to_thread(
                self.vector_store.add_embeddings,
                texts=texts,
                embeddings=embeddings,
                metadatas=metadatas,
                ids=ids,
            )

            logger.info(f"Successfully stored {len(result_ids)} documents")
            return result_ids

        except Exception as e:
            logger.error(f"Failed to store documents with embeddings: {e}")
            raise

    async def add_documents_batch(
        self,
        documents: list[Document],
        ids: list[str] | None = None,
        batch_size: int = 50,
    ) -> list[str]:
        """
        대량의 문서를 배치로 나누어 추가

        Args:
            documents: 저장할 Document 리스트
            ids: 문서 ID 리스트
            batch_size: 배치당 문서 수

        Returns:
            저장된 문서의 ID 리스트
        """
        self._ensure_initialized()

        if not documents:
            return []

        all_ids: list[str] = []
        total_batches = (len(documents) + batch_size - 1) // batch_size

        for i in range(0, len(documents), batch_size):
            batch_docs = documents[i : i + batch_size]
            batch_ids = ids[i : i + batch_size] if ids else None
            batch_num = (i // batch_size) + 1

            logger.info(
                f"Processing batch {batch_num}/{total_batches} "
                f"({len(batch_docs)} documents)"
            )

            result_ids = await self.add_documents(batch_docs, batch_ids)
            all_ids.extend(result_ids)

            # Rate limiting: 배치 간 딜레이
            if i + batch_size < len(documents):
                await asyncio.sleep(settings.JIRA_API_RATE_LIMIT_DELAY)

        logger.info(f"Batch upload complete: {len(all_ids)} documents added")
        return all_ids

    async def delete_documents(self, ids: list[str]) -> None:
        """
        문서 삭제

        Args:
            ids: 삭제할 문서 ID 리스트
                 형식: ["jira:issue:CATCH-145", "jira:epic:CATCH-100"]
        """
        self._ensure_initialized()

        if not ids:
            logger.warning("No document IDs to delete")
            return

        logger.info(f"Deleting {len(ids)} documents from PGVector")

        try:
            await asyncio.to_thread(
                self.vector_store.delete,
                ids=ids,
            )
            logger.info(f"Successfully deleted {len(ids)} documents")

        except Exception as e:
            logger.error(f"Failed to delete documents: {e}")
            raise

    async def search(
        self,
        query: str,
        k: int = 5,
        filter: dict[str, Any] | None = None,
    ) -> list[Document]:
        """
        벡터 시맨틱 검색

        Args:
            query: 검색 쿼리 (자연어)
            k: 반환할 결과 수
            filter: 메타데이터 필터 (예: {"entity_type": "issue"})

        Returns:
            관련성 높은 Document 리스트

        Example:
            # 기본 검색
            results = await repository.search("로그인 버그", k=5)

            # 필터링 검색 (Issue만)
            results = await repository.search(
                "로그인 버그",
                k=5,
                filter={"entity_type": "issue"}
            )
        """
        self._ensure_initialized()

        logger.info(f"Searching for: '{query}' (k={k}, filter={filter})")

        try:
            async with _embedding_semaphore:
                # similarity_search는 동기 메서드
                results = await asyncio.to_thread(
                    self.vector_store.similarity_search,
                    query,
                    k=k,
                    filter=filter,
                )

            logger.info(f"Search returned {len(results)} results")
            return results

        except Exception as e:
            logger.error(f"Search failed: {e}")
            raise

    async def search_with_score(
        self,
        query: str,
        k: int = 5,
        filter: dict[str, Any] | None = None,
    ) -> list[tuple[Document, float]]:
        """
        점수 포함 벡터 검색

        Args:
            query: 검색 쿼리
            k: 반환할 결과 수
            filter: 메타데이터 필터

        Returns:
            (Document, score) 튜플 리스트
            score는 유사도 점수 (낮을수록 유사)
        """
        self._ensure_initialized()

        logger.info(f"Searching with score for: '{query}' (k={k})")

        try:
            async with _embedding_semaphore:
                results = await asyncio.to_thread(
                    self.vector_store.similarity_search_with_score,
                    query,
                    k=k,
                    filter=filter,
                )

            logger.info(f"Search with score returned {len(results)} results")
            return results

        except Exception as e:
            logger.error(f"Search with score failed: {e}")
            raise

    async def upsert_documents(
        self,
        documents: list[Document],
        ids: list[str],
    ) -> list[str]:
        """
        문서 Upsert (존재하면 업데이트, 없으면 추가)

        증분 동기화 시 사용. 기존 문서를 삭제 후 새로 추가.

        Args:
            documents: 저장할 Document 리스트
            ids: 문서 ID 리스트

        Returns:
            저장된 문서 ID 리스트
        """
        self._ensure_initialized()

        if not documents or not ids:
            return []

        if len(documents) != len(ids):
            raise ValueError("documents와 ids의 길이가 일치해야 합니다.")

        logger.info(f"Upserting {len(documents)} documents")

        # 기존 문서 삭제 후 새로 추가 (atomic하지 않음, 필요시 트랜잭션 추가)
        await self.delete_documents(ids)
        return await self.add_documents(documents, ids)

    async def get_collection_stats(self) -> dict[str, Any]:
        """
        컬렉션 통계 정보 조회

        Returns:
            컬렉션 통계 (문서 수 등)
        """
        self._ensure_initialized()

        # langchain-postgres는 직접 통계 메서드를 제공하지 않음
        # 필요시 raw SQL 쿼리로 구현 가능
        return {
            "collection_name": self.collection_name,
            "embedding_dimensions": settings.PGVECTOR_EMBEDDING_DIMENSIONS,
            "initialized": self._initialized,
        }
    
    async def delete_by_id_prefix(self, prefix: str) -> None:
        self._ensure_initialized()

        if not prefix:
            return

        with self.vector_store._make_sync_session() as session:
            stmt = sa_delete(self.vector_store.EmbeddingStore).where(
                self.vector_store.EmbeddingStore.id.like(f"{prefix}%")
            )
            result = session.execute(stmt)
            session.commit()

        logger.info(f"Deleted {result.rowcount} documents with prefix '{prefix}'")