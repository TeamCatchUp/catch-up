from functools import lru_cache

from catchup.components.reranker.service import RerankService


@lru_cache(maxsize=1)
def get_rerank_service() -> RerankService:
    return RerankService()
