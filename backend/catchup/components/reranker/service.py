import logging

from langchain_cohere import CohereRerank
from langchain_core.documents import Document

from catchup.configs.config import settings

logger = logging.getLogger(__name__)


class RerankService:
    def __init__(self):
        self.reranker = CohereRerank(
            cohere_api_key=settings.COHERE_API_KEY,
            model="rerank-multilingual-v3.0"
        )

    def get_reranker(self):
        return self.reranker

    async def rerank(
        self,
        query: str,
        documents: list[Document],
        top_n: int = 5
    ) -> list[Document]:
        if not documents:
            return []

        self.reranker.top_n = top_n

        # Rerank 호출
        reranked_docs: list[Document] = await self.reranker.acompress_documents(
            documents=documents,
            query=query
        )

        logger.info(f"Reranking 완료: {len(documents)} -> {len(reranked_docs)}건 (Top N: {top_n})")
       
        return reranked_docs
