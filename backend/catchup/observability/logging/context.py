from __future__ import annotations

from typing import Any
from structlog.contextvars import bind_contextvars, clear_contextvars, get_contextvars

from catchup.audit.schemas import AuditActor
from catchup.configs.config import settings


# 요청 시작 / 종료 시점에 context clear
def clear_request_context() -> None:
    clear_contextvars()


def get_request_context() -> dict[str, Any]:
    return get_contextvars()


def bind_base_context(
    trace_id: str,
    remote_addr: str,
) -> None:
    bind_contextvars(
        trace_id=trace_id,
        service=settings.SERVICE_NAME,
        version=settings.APP_VERSIONS,
        environment=str(settings.ENV),
        remote_addr=remote_addr,
    )


# actor 초기화 후 주입
def bind_actor_context(actor: AuditActor | None) -> None:
    # actor가 없으면 필드 값이 None으로 채워진 빈 객체 생성
    data = actor.model_dump() if actor else AuditActor().model_dump()
    bind_contextvars(actor=data)
