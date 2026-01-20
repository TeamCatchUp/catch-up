from functools import lru_cache

from app.rag.repository.meili import LangChainMeiliRepository
from app.rag.service.github import GithubService
from app.rag.service.llm import LlmService
from app.rag.service.rerank import RerankService


@lru_cache(maxsize=1)
def get_vector_repository() -> LangChainMeiliRepository:
    return LangChainMeiliRepository()


@lru_cache(maxsize=1)
def get_llm_service() -> LlmService:
    return LlmService()


@lru_cache(maxsize=1)
def get_rerank_service() -> RerankService:
    return RerankService()

@lru_cache(maxsize=1)
def get_github_service() -> GithubService:
    return GithubService()