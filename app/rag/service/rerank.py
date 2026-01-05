import logging

from langchain_core.documents import Document
from langchain_cohere import CohereRerank
from app.core.config import settings


logger = logging.getLogger(__name__)


class RerankService():
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
            documents: list[dict],
            top_n: int = 5
        ) -> list[dict]:
        
        # dict -> Document
        input_docs = [
            Document(page_content=doc.get("text", ""), metadata=doc)
            for doc in documents
        ]
        
        self.reranker.top_n = top_n
        
        reranked_docs = await self.reranker.acompress_documents(
            documents=input_docs,
            query=query
        )
        
        logger.info(f"reranked docs: {reranked_docs}")
        
        # Document -> dict
        result_docs = [
            {
                "text": doc.page_content,
                **doc.metadata
            }
            for doc in reranked_docs
        ]
        
        logger.info(f"result_docs: {result_docs[0]}")
                
        return result_docs