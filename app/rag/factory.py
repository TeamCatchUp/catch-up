from functools import lru_cache

from app.rag.repository.base import VectorStoreRepository
from app.rag.repository.meili import LangChainMeiliRepository
from app.rag.service.llm import LlmService


@lru_cache(maxsize=1)
def get_vector_repository() -> VectorStoreRepository:
    return LangChainMeiliRepository()


@lru_cache(maxsize=1)
def get_llm_service() -> LlmService:
    return LlmService()
