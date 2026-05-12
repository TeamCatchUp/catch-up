import threading

from cachetools import TTLCache
from cachetools import cached
from cachetools.keys import hashkey

from catchup.components.reranker.constants import RerankerProvider
from catchup.components.reranker.service import AwsBedrockRerankService
from catchup.components.reranker.service import BaseRerankService
from catchup.components.reranker.service import CohereRerankService

# AWS NAT GW idle timeout(350s)보다 짧게 설정해 만료 전에 커넥션 풀 교체
_cache = TTLCache(maxsize=1, ttl=240)
# TTL 만료 시 여러 스레드가 동시에 인스턴스를 생성하는 thundering herd 방지 목적
_lock = threading.Lock()


@cached(cache=_cache, key=hashkey, lock=_lock)
def get_rerank_service(
    provider: RerankerProvider
) -> BaseRerankService:
    if provider == RerankerProvider.COHERE:
        return CohereRerankService()
    
    if provider == RerankerProvider.AWS_BEDROCK:
        return AwsBedrockRerankService()
    
    raise ValueError(f"Unknown provider: {provider}")
