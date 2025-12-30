from functools import lru_cache

from app.rag.repository.base import VectorStoreRepository
from app.rag.repository.meili import LangChainMeiliRepository
from app.rag.service.chat import ChatService


@lru_cache  # 싱글톤
def get_vector_repository() -> VectorStoreRepository:
    return LangChainMeiliRepository()


@lru_cache  # 검색 서비스 의존성 주입
def get_chat_service() -> ChatService:
    return ChatService()
