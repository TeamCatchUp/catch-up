from abc import ABC, abstractmethod

from langchain.embeddings import Embeddings
from langchain_aws import BedrockEmbeddings
from langchain_cohere import CohereEmbeddings
from langchain_openai import OpenAIEmbeddings
from botocore.config import Config
import boto3

from catchup.configs.config import settings

class BaseEmbeddingService(ABC):
    def __init__(self):
        self.embedder: Embeddings = self._create_embedder()
    
    @abstractmethod
    def _create_embedder(self):
        pass
    
    def get_embedder(self) -> Embeddings:
        return self.embedder
    

class OpenAiEmbeddingService(BaseEmbeddingService):
    def _create_embedder(self):
        return OpenAIEmbeddings(
            model=settings.OPENAI_EMBEDDING_MODEL,
            api_key=settings.OPENAI_API_KEY
        )
    
class CohereEmbeddingService(BaseEmbeddingService):
    def _create_embedder(self):
        return CohereEmbeddings(
            model=settings.COHERE_EMBEDDING_MODEL,
            api_key=settings.COHERE_API_KEY
        )
    
class AwsBedrockEmbeddingService(BaseEmbeddingService):
    def _create_embedder(self):
        config = Config(
            max_pool_connections=settings.EMBEDDING_MAX_CONCURRENCY * 2,
            retries={"max_attempts": 5, "mode": "standard"},
        )
        client = boto3.client(
            "bedrock-runtime",
            region_name=settings.AWS_EMBEDDING_MODEL_REGION,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            config=config,
        )
        return BedrockEmbeddings(
            model_id=settings.AWS_BEDROCK_EMBEDDING_MODEL,
            client=client
        )
