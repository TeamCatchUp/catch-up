from abc import ABC, abstractmethod
import logging

from langchain_aws import BedrockRerank
from langchain_aws.utils import create_aws_client
from langchain_cohere import CohereRerank
from langchain_core.documents import BaseDocumentCompressor, Document
from langchain_core.runnables import RunnableConfig, run_in_executor

from catchup.configs.config import settings

logger = logging.getLogger(__name__)


class BaseRerankService(ABC):
    def __init__(self):
        self.reranker = self._create_reranker()
        
    @abstractmethod
    def _create_reranker(self) -> BaseDocumentCompressor:
        pass

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
                        
        self._backup_ids(documents)

        self.reranker.top_n = top_n

        # Rerank 호출
        reranked_docs: list[Document] = await self.reranker.acompress_documents(
            documents=documents,
            query=query
        )
        
        self._restore_ids(reranked_docs)

        logger.info(f"Reranking 완료: {len(documents)} -> {len(reranked_docs)}건 (Top N: {top_n})")
       
        return reranked_docs
    
    def _backup_ids(
        self,
        documents: list[Document]
    ) -> None:
        for doc in documents:
            if doc.id:
                doc.metadata["_original_id"] = doc.id
                
    def _restore_ids(
        self,
        documents: list[Document]
    ) -> None:
        for doc in documents:
            if "_original_id" in doc.metadata:
                doc.id = doc.metadata.pop("_original_id")
                
class CohereRerankService(BaseRerankService):
    def _create_reranker(self) -> BaseDocumentCompressor:
        return CohereRerank(
            cohere_api_key=settings.COHERE_API_KEY,
            model="rerank-multilingual-v3.0"
        )
    
class AwsBedrockRerankService(BaseRerankService):
    def _create_reranker(self) -> BaseDocumentCompressor:
        client = create_aws_client(
            service_name="bedrock-agent-runtime",
            region_name=settings.AWS_RERANK_MODEL_REGION
        )
        return BedrockRerank(
            model_arn=settings.AWS_RERANK_MODEL_ARN,
            client=client
        )
    
    async def rerank(
        self,
        query: str,
        documents: list[Document],
        top_n: int = 5
    ) -> list[Document]:
        if not documents:
            return []
                        
        self._backup_ids(documents)

        self.reranker.top_n = top_n

        # Rerank 호출
        reranked_docs: list[Document] = await run_in_executor(
            RunnableConfig(),
            self.reranker.compress_documents,
            documents=documents,
            query=query
        )
        
        self._restore_ids(reranked_docs)

        logger.info(f"Reranking 완료: {len(documents)} -> {len(reranked_docs)}건 (Top N: {top_n})")
       
        return reranked_docs