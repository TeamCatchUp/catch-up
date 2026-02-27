from __future__ import annotations

import structlog

from catchup.observability.logging.config import configure_logging
from catchup.observability.logging.context import (
    bind_actor_context,
    bind_base_context,
    clear_request_context,
    get_request_context,
)

def get_logger(name:str | None = None) -> structlog.stdlib.BoundLogger:
    if name:
        return structlog.get_logger(name)
    return structlog.get_logger()

__all__ = [
    "configure_logging",
    "get_logger",
    "clear_request_context",
    "bind_base_context",
    "bind_actor_context", 
    "get_request_context",
]