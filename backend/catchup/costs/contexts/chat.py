from __future__ import annotations

from contextvars import ContextVar
from typing import ClassVar
from catchup.costs.contexts.base import BaseTokenUsageContext


class ChatTokenUsageContext(BaseTokenUsageContext):
    
    _current: ClassVar[ContextVar] = ContextVar(
        "current_chat_token_usage", default=None
    )

    def __init__(self):
        super().__init__()
        self.message_id: int | None = None
        self.rerank_count: int = 0
