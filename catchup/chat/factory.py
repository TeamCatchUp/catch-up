from functools import lru_cache

from catchup.chat.service import ChatService


@lru_cache(maxsize=1)
def get_chat_service() -> ChatService:
    return ChatService()
