from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable
import structlog
from fastapi import BackgroundTasks, HTTPException, Request, Response
from fastapi.concurrency import run_in_threadpool

from catchup.audit.schemas import AuditActor
from catchup.auth.jwt import verify_token
from catchup.costs.contexts.chat import ChatTokenUsageContext
from catchup.db.engine import SessionLocal
from catchup.db.users import get_user_by_sub
from catchup.observability.logging.context import (
    bind_actor_context,
    bind_base_context,
    clear_request_context,
)
from catchup.events.context import current_bg_tasks


logger = structlog.get_logger()

REQUEST_ID_HEADER = "X-Request-Id"
AMZN_TRACE_HEADER = "X-Amzn-Trace-Id"
AUTHORIZATION_HEADER = "Authorization"
ACCESS_TOKEN_COOKIE = "access_token"

CallNext = Callable[[Request], Awaitable[Response]]

def _extract_amzn_root_trace(raw_header: str) -> str:
    parts = {}
    for segment in raw_header.split(";"):
        if "=" not in segment:
            continue
        key, value = segment.split("=", 1)
        parts[key.strip()] = value.strip()
    
    return parts.get("Root", raw_header)


# X-Request-ID -> X-Amzn-Trace-Id -> 자체 UUID 순으로 시도
def _resolve_trace_id(request: Request) -> str:
    request_id = request.headers.get(REQUEST_ID_HEADER)
    if request_id:
        return request_id.strip()
    
    amzn_trace_id = request.headers.get(AMZN_TRACE_HEADER)
    if amzn_trace_id:
        return _extract_amzn_root_trace(amzn_trace_id.strip())
    
    return str(uuid.uuid4())


def _extract_access_token(request: Request) -> str | None:
    cookie_token = request.cookies.get(ACCESS_TOKEN_COOKIE)
    if cookie_token:
        return cookie_token.strip()
    
    auth_header = request.headers.get(AUTHORIZATION_HEADER, "")
    if auth_header.lower().startswith("bearer "):
        return auth_header[7:].strip()
    
    return None


def _resolve_actor_from_access_token(access_token: str | None) -> AuditActor:
    if not access_token:
        return AuditActor()
    
    try:
        payload = verify_token(access_token, "access")
        sub = payload.get("sub")
        
        if not sub:
            return AuditActor.from_token_payload(payload)
        
        with SessionLocal() as db:
            try:
                user = get_user_by_sub(db, sub)
                if user:
                    snapshot = user.to_snapshot()
                    snapshot["sub"] = sub
                    return AuditActor.from_user_snapshot(snapshot)            
            except Exception as e:
                logger.warning("failed_to_resolve_actor", error=str(e))
                
        return AuditActor.from_token_payload(payload)
    
    except HTTPException:
        # 만료되거나 유효하지 않은 토큰은 그냥 빈 Actor 반환 (조용히 처리)
        return AuditActor()
    except Exception as e:
        logger.error("unexpected_error_resolving_actor", error=str(e))
        return AuditActor()


async def request_context_middleware(
    request: Request,
    call_next: CallNext
) -> Response:
    start_time = time.perf_counter()

    trace_id = _resolve_trace_id(request)
    remote_addr = request.client.host
    
    # 로깅 컨텍스트 바인딩
    clear_request_context()
    bind_base_context(trace_id, remote_addr)

    # Actor 추출 후 바인딩
    access_token = _extract_access_token(request)
    actor = await run_in_threadpool(
        _resolve_actor_from_access_token,
        access_token
    )
    bind_actor_context(actor)

    request.state.trace_id = trace_id
    request.state.actor = actor
    
    logger.debug(
        "request_trace_info",
        trace_id_=request.state.trace_id,
        actor_=request.state.actor.model_dump(mode="json")
    )
    
    # TODO: Contextvar 컨벤션 통일(module->class)
    # BackgroundTasks를 ContextVars로 설정
    bg_tasks = BackgroundTasks()
    token = current_bg_tasks.set(bg_tasks)
    
    # 채팅 토큰 사용량 컨텍스트 초기화
    ChatTokenUsageContext.init()
    
    try:
        # 비즈니스 로직 수행
        response: Response = await call_next(request)
        
        process_time = time.perf_counter() - start_time
        logger.info(
            "http_request_finished",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration=f"{process_time:.4f}s",
            event_type="SYSTEM",
            event_action=f"{request.method} {request.url.path}"
        )
        
        response.headers[REQUEST_ID_HEADER] = trace_id
        if response.background is None:
            response.background = bg_tasks
        else:
            response.background.tasks.extend(bg_tasks.tasks)
        
        return response
    finally:
        current_bg_tasks.reset(token)
        clear_request_context()
