import threading

from cachetools import TTLCache
from cachetools import cached
from cachetools.keys import hashkey

from catchup.components.embedder.constants import EmbeddingProvider
from catchup.components.embedder.service import AwsBedrockEmbeddingService
from catchup.components.embedder.service import BaseEmbeddingService
from catchup.components.embedder.service import CohereEmbeddingService
from catchup.components.embedder.service import OpenAiEmbeddingService

# AWS NAT GW idle timeout(350s)보다 짧게 설정해 만료 전에 커넥션 풀 교체
_cache = TTLCache(maxsize=4, ttl=240)
# TTL 만료 시 여러 스레드가 동시에 인스턴스를 생성하는 thundering herd 방지 목적
_lock = threading.Lock()


@cached(cache=_cache, key=hashkey, lock=_lock)
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
