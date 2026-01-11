import asyncio
import logging
from typing import Any, Optional

from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from meilisearch_python_sdk import AsyncClient
from meilisearch_python_sdk.models.search import Hybrid, SearchParams

from app.core.config import settings

logger = logging.getLogger(__name__)

# Embedding Rate Limit 제한
embedding_semaphore = asyncio.Semaphore(10)


class LangChainMeiliRepository:
    def __init__(self):
        self.embeddings = OpenAIEmbeddings(model=settings.OPENAI_EMBEDDING_MODEL)

        self.embeddings.dimensions = 3072

        self.client = AsyncClient(
            settings.MEILI_HTTP_ADDR, settings.MEILI_KEY, timeout=30
        )

    async def initialize(self, index_names: list[str] = None):
        """
        사용할 모든 인덱스에 대해 초기 설정을 수행한다.

        인덱스가 없다면 생성하고, hybrid search를 위한 embedder를 설정한다.
        FastAPI 서버 최초 실행 시점에 lifespan을 통해 실행된다.
        """
        logger.info(f"Initializing meilisearch indicies...")
        targets: list[str] = index_names or [settings.MEILI_DEFAULT_INDEX]

        config = {"primaryKey": "id"}

        for index_name in targets:
            # 인덱스 생성
            try:
                await self.client.create_index(index_name, config)
                logger.info(f"Created index '{index_name}'. (Skipped if exists)")
            except Exception as e:
                logger.warning(f"Failed to create index for '{index_name}': {e}")

            index = self.client.index(index_name)

            # 임베더 설정
            try:
                await index.update_embedders(
                    {"default": {"source": "userProvided", "dimensions": 1536}}
                )

                logger.info(f"Updated embedders for '{index_name}'.")

            except Exception as e:
                logger.warning(f"Failed to update embedders for '{index_name}': {e}")

            # 필터링 가능한 속성 정의
            try:
                await index.update_filterable_attributes(
                    [
                        "metadata.category",
                        "metadata.source",
                        "metadata.file_path",
                        "metadata.file_name",
                    ]
                )
                logger.info(f"Updated filters for '{index_name}'.")
            except Exception as e:
                logger.warning(f"Failed to update filters for '{index_name}': {e}")

            logger.info(f"embedders: {await index.get_embedders()}")

    async def search(
        self,
        query: str,
        index_name: Optional[str] = None,
        k: int = 3,
        semantic_ratio: float = 0.5,
        filters: Optional[dict] = None,
    ) -> list[Document]:
        """단일 쿼리, 단일 인덱스 검색"""

        # 검색 대상 인덱스
        target_index = index_name or settings.MEILI_DEFAULT_INDEX

        # Meilisearch 인덱스 객체
        index = self.client.index(target_index)

        async with embedding_semaphore:
            vector = await self.embeddings.aembed_query(
                query
            )  # 사용자 자연어 쿼리 임베딩

        # 검색 파라미터 설정 (hybrid search)
        search_params = {
            "vector": vector,
            "limit": k,
            "hybrid": Hybrid(semantic_ratio=semantic_ratio, embedder="default"),
        }

        # 필터 존재 시 추가
        if filters:
            search_params["filter"] = filters

        # Meilisearch 검색
        results = await index.search(query, **search_params)
        logger.info(f"Search results count: {len(results.hits)}")

        # 반환할 검색 결과 리스트
        docs = []
        for hit in results.hits:
            content = hit.get("text") or hit.get("content") or ""  # 본문 내용

            # 메타 데이터에서 제외할 필드명
            excluded_keys = ["text", "content", "_vectors", "_semantics", "_formatted"]

            # 메타 데이터 필터링
            metadata = {k: v for k, v in hit.items() if k not in excluded_keys}
            # 검색 결과 리스트에 추가
            docs.append(Document(page_content=content, metadata=metadata))

        return docs

    async def multi_search(
        self, search_requests: list[dict[str, Any]]
    ) -> list[list[Document]]:
        """다중 쿼리, 다중 인덱스 검색"""

        if not search_requests:
            return []

        queries = [req["query"] for req in search_requests]

        async with embedding_semaphore:
            vectors = await self.embeddings.aembed_documents(queries)

        multisearch_queries = []
        for i, req in enumerate(search_requests):
            search_query = SearchParams(
                index_uid=req["index_name"],
                query=req["query"],
                vector=vectors[i],
                limit=req.get("k", 5),
                hybrid=Hybrid(
                    semantic_ratio=req.get("semantic_ratio", 0.5), embedder="default"
                ),
            )

            if req.get("filter"):
                search_query["filter"] = req.get("filter")

            multisearch_queries.append(search_query)

        response = await self.client.multi_search(multisearch_queries)

        all_results = []

        for result_set in response:
            docs = []
            for hit in result_set.hits:
                content = hit.get("text") or hit.get("content") or ""

                excluded_keys = [
                    "text",
                    "content",
                    "_vectors",
                    "_semantics",
                    "_formatted",
                ]
                metadata = {k: v for k, v in hit.items() if k not in excluded_keys}

                docs.append(Document(page_content=content, metadata=metadata))
            all_results.append(docs)

        return all_results
