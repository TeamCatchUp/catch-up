import logging

from langchain_cohere import CohereRerank
from langchain_core.documents import Document

from app.core.config import settings
from app.rag.models.retrieve import BaseSearchResult

logger = logging.getLogger(__name__)


class RerankService:
    def __init__(self):
        self.reranker = CohereRerank(
            cohere_api_key=settings.COHERE_API_KEY, model="rerank-multilingual-v3.0"
        )

    def get_reranker(self):
        return self.reranker

    async def rerank(
        self,
        query: str,
        documents: list[BaseSearchResult],
        top_n: int = 5
    ) -> list[BaseSearchResult]:
        
        if not documents:
            return []
        
        # BaseSearchResult -> Document
        input_docs = [
            Document(
                page_content=doc.text,
                metadata={"original_doc": doc}
            )
            for doc in documents
        ]

        self.reranker.top_n = top_n
        
        # Rerank 호출
        reranked_docs: list[Document] = await self.reranker.acompress_documents(
            documents=input_docs,
            query=query
        )

        logger.info(f"Reranked docs count: {len(reranked_docs)}")
        
        # Document -> BaseSearchResult
        result_models = []
        for doc in reranked_docs:
            original_model: BaseSearchResult = doc.metadata.get("original_doc")
            new_score = doc.metadata.get("relevance_score")
            original_model.relevance_score = new_score
            result_models.append(original_model)

        return result_models
