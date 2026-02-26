from functools import lru_cache
from catchup.components.embedder.constants import EmbeddingProvider
from catchup.components.embedder.service import AwsBedrockEmbeddingService, BaseEmbeddingService, CohereEmbeddingService, OpenAiEmbeddingService


@lru_cache(maxsize=5)
def get_embedding_service(provider: EmbeddingProvider) -> BaseEmbeddingService:
    if provider == EmbeddingProvider.OPENAI:
        return OpenAiEmbeddingService()
    
    if provider == EmbeddingProvider.COHERE:
        return CohereEmbeddingService()
    
    if provider == EmbeddingProvider.AWS_BEDROCK:
        return AwsBedrockEmbeddingService()
    
    raise ValueError(f"Unknown provider: {provider}")
