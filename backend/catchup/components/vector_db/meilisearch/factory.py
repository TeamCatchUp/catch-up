from functools import lru_cache

from catchup.components.vector_db.meilisearch.meili import LangChainMeiliRepository


@lru_cache(maxsize=1)
def get_vector_repository() -> LangChainMeiliRepository:
    return LangChainMeiliRepository()
