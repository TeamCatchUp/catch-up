import meilisearch
from app.core.config import settings
from app.rag.repository.base import VectorStoreRepository
from langchain_community.vectorstores import Meilisearch
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings


class LangChainMeiliRepository(VectorStoreRepository):
    def __init__(self):
        self.embeddings = OpenAIEmbeddings()

        self.vector_store = Meilisearch(
            embedding=self.embeddings,
            url=settings.MEILI_HTTP_ADDR,
            api_key=settings.MEILI_KEY,
            index_name=settings.MEILI_INDEX,
        )

        self.admin_client = meilisearch.Client(
            settings.MEILI_HTTP_ADDR, settings.MEILI_KEY
        )

    def initialize(self):
        """
        Meilisearch 초기 설정을 주입한다.

        인덱스가 없다면 생성하고, hybrid search를 위한 embedder를 설정한다.
        FastAPI 서버 최초 실행 시점에 lifespan을 통해 실행된다.
        """
        config = {"primaryKey": "id"}

        try:
            self.admin_client.create_index(settings.MEILI_INDEX, config)
        except:
            pass

        index = self.admin_client.index(settings.MEILI_INDEX)

        task = index.update_embedders(
            {"default": {"source": "userProvided", "dimensions": 1536}}
        )

        self.admin_client.wait_for_task(task.task_uid)

        task_filter = index.update_filterable_attributes(["role", "category"])
        self.admin_client.wait_for_task(task_filter.task_uid)

    def retrieve(
        self, query: str, k: int = 3, semantic_ratio: float = 0.5
    ) -> list[Document]:
        """
        Meilisearch vector store에서 검색을 수행한다.

        Meilisearch의 hybrid search를 기반으로 사용자 쿼리와 키워드가 일치하거나 의미적으로 유사한 Document에 대한 List를 반환한다.

        Args:
            - query (str): 사용자의 자연어 질문
            - k (int): 상위 k개의 Document (default: 3)
            - semantic_ratio (float): 의미적 유사도 반영 가중치 (default: 0.5)

        Returns:
            docs (list[Document]):
                상위 K개의 검색 결과
                - Document: langchain Documnet 객체
        """
        docs = self.vector_store.similarity_search(
            query=query,
            k=k,
            hybrid={"semanticRatio": semantic_ratio, "embedder": "default"},
        )

        return docs
