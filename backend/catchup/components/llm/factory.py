from functools import lru_cache

from catchup.components.llm.service import LlmService


@lru_cache(maxsize=1)
def get_llm_service() -> LlmService:
    return LlmService()
