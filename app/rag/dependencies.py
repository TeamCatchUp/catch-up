from functools import lru_cache

from app.rag.service.chat import ChatService


@lru_cache(maxsize=1)
def get_chat_service() -> ChatService:
    return ChatService()
