from functools import lru_cache

from catchup.components.reranker.service import AwsBedrockRerankService, BaseRerankService, CohereRerankService
from catchup.components.reranker.constants import RerankerProvider


@lru_cache(maxsize=1)
def get_rerank_service(
    provider: RerankerProvider
) -> BaseRerankService:
    if provider == RerankerProvider.COHERE:
        return CohereRerankService()
    
    if provider == RerankerProvider.AWS_BEDROCK:
        return AwsBedrockRerankService()
    
    raise ValueError(f"Unknown provider: {provider}")
