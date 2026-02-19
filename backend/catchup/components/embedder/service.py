from abc import ABC, abstractmethod

from langchain.embeddings import Embeddings
from langchain_aws import BedrockEmbeddings
from langchain_cohere import CohereEmbeddings
from langchain_openai import OpenAIEmbeddings
from langchain_aws.utils import create_aws_client
from openai import api_key

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
        client = create_aws_client(
            service_name="bedrock-runtime",
            region_name=settings.AWS_EMBEDDING_MODEL_REGION
        )
        return BedrockEmbeddings(
            model_id=settings.AWS_BEDROCK_EMBEDDING_MODEL,
            client=client
        )