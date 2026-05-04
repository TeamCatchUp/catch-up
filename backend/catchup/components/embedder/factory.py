from catchup.components.embedder.constants import EmbeddingProvider
from catchup.components.embedder.service import AwsBedrockEmbeddingService
from catchup.components.embedder.service import BaseEmbeddingService
from catchup.components.embedder.service import CohereEmbeddingService
from catchup.components.embedder.service import OpenAiEmbeddingService


def get_embedding_service(
    provider: EmbeddingProvider,
    max_attempts: int = AwsBedrockEmbeddingService.DEFAULT_MAX_ATTEMPTS,
) -> BaseEmbeddingService:
    if provider == EmbeddingProvider.OPENAI:
        return OpenAiEmbeddingService()

    if provider == EmbeddingProvider.COHERE:
        return CohereEmbeddingService()

    if provider == EmbeddingProvider.AWS_BEDROCK:
        return AwsBedrockEmbeddingService(max_attempts=max_attempts)
    
    raise ValueError(f"Unknown provider: {provider}")
