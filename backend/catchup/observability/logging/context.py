from __future__ import annotations

from typing import Any

from structlog.contextvars import bind_contextvars, clear_contextvars, get_contextvars

from catchup.configs.config import settings

DEFAULT_ACTOR = {
    "user_id": None,
    "email": None,
    "role": None,
    "department": None,
}

# 요청 시작 / 종료 시점에 context clear
def clear_request_context() -> None:
    clear_contextvars()

def bind_base_context(trace_id: str) -> None:
    bind_contextvars(
        trace_id = trace_id,
        service=settings.SERVICE_NAME,
        version=settings.APP_VERSIONS,
        environment=str(settings.ENV),
    )

# actor 초기화 후 주입
def bind_actor_context(actor: dict[str, Any] | None) -> None:
    normalized_actor = dict(DEFAULT_ACTOR)
    if actor:
        for key in DEFAULT_ACTOR:
            normalized_actor[key] = actor.get(key)
        bind_contextvars(actor = normalized_actor)


def get_request_context() -> dict[str, Any]:
    return get_contextvars()