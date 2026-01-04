import logging
from typing import Optional

import meilisearch
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings

from app.core.config import settings, MeiliEnvironment
from app.rag.repository.base import VectorStoreRepository

logger = logging.getLogger(__name__)


class LangChainMeiliRepository(VectorStoreRepository):
    def __init__(self):
        self.embeddings = OpenAIEmbeddings()

        self.client = meilisearch.Client(
            settings.MEILI_HTTP_ADDR, settings.MEILI_KEY, timeout=10
        )

    def initialize(self, index_names: list[str] = None):
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
                task = self.client.create_index(index_name, config)
                self.client.wait_for_task(task.task_uid)
                logger.info(f"Created index '{index_name}'. (Skipped if exists)")
            except Exception as e:
                logger.warning(f"Failed to create index for '{index_name}': {e}")

            index = self.client.index(index_name)

            # 임베더 설정
            try:
                task = index.update_embedders(
                    {"default": {"source": "userProvided", "dimensions": 1536}}
                )
                self.client.wait_for_task(task.task_uid)

                logger.info(f"Updated embedders for '{index_name}'.")

            except Exception as e:
                logger.warning(f"Failed to update embedders for '{index_name}': {e}")

            # 필터링 가능한 속성 정의
            try:
                task = index.update_filterable_attributes(
                    [
                        "metadata.category",
                        "metadata.source",
                        "metadata.file_path",
                        "metadata.file_name",
                    ]
                )
                self.client.wait_for_task(task.task_uid)
                logger.info(f"Updated filters for '{index_name}'.")
            except Exception as e:
                logger.warning(f"Failed to update filters for '{index_name}': {e}")

            logger.info(f"embedders: {index.get_embedders()}")
            

    def retrieve(
        self,
        query: str,
        index_name: Optional[str] = None,
        k: int = 3,
        semantic_ratio: float = 0.5,
        filters: Optional[dict] = None,
    ) -> list[Document]:
        
        # 검색 대상 인덱스
        target_index = index_name or settings.MEILI_DEFAULT_INDEX

        # Meilisearch 인덱스 객체
        index = self.client.index(target_index)
        
        # 사용자 자연어 쿼리 임베딩
        vector = self.embeddings.embed_query(query)

        # 검색 파라미터 설정 (hybrid search)
        search_params = {
            "vector": vector,
            "limit": k,
            "hybrid": {
                "semanticRatio": semantic_ratio,
                "embedder": "default",
            },
        }

        # 필터 존재 시 추가
        if filters:
            search_params["filter"] = filters

        # Meilisearch 검색
        results = index.search(query, search_params)
        logger.info(f"Search results count: {len(results.get('hits', []))}")

        # 반환할 검색 결과 리스트
        docs = []
        for hit in results.get("hits", []):
            content = hit.get("text") or hit.get("content") or "" # 본문 내용
            
            # 메타 데이터에서 제외할 필드명
            excluded_keys = [
                "text",
                "content",
                "_vectors",
                "_semantics",
                "_formatted"
            ]
            
            # 메타 데이터 필터링
            metadata = {
                    k: v
                    for k, v in hit.items()
                    if k not in excluded_keys
                }
            # 검색 결과 리스트에 추가
            docs.append(Document(page_content=content, metadata=metadata))

        return docs
