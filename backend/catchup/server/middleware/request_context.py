from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable
from collections.abc import Callable

import structlog
from fastapi import HTTPException
from fastapi import Request
from fastapi import Response
from fastapi.concurrency import run_in_threadpool

from catchup.audit.contexts import AuditContext
from catchup.audit.schemas import AuditActor
from catchup.auth.jwt import verify_token
from catchup.db.engine import SessionLocal
from catchup.db.users import get_user_by_sub
from catchup.observability.logging.context import bind_actor_context
from catchup.observability.logging.context import bind_base_context
from catchup.observability.logging.context import clear_request_context

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
    status_code = 500  # Fallback
    process_time = 0.0
    
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

    logger.debug(
        "request_trace_info",
        trace_id_=trace_id,
        actor_=actor.model_dump(mode="json")
    )

    # 감사 로그 메타데이터 컨텍스트 초기화
    AuditContext.init()
    
    logger.debug(
        "http_request_started",
        method=request.method,
        path=request.url.path,
    )
    
    try:
        # 서비스 로직 수행
        response: Response = await call_next(request)
        status_code = response.status_code
        process_time = time.perf_counter() - start_time        
        response.headers[REQUEST_ID_HEADER] = trace_id
        return response
    finally:
        if status_code >= 500:
            log_fn = logger.error
        elif status_code >= 400:
            log_fn = logger.warning
        else:
            log_fn = logger.info
        
        log_fn(
            "http_request_finished",
            method=request.method,
            path=request.url.path,
            status_code=status_code,
            duration=f"{process_time:.4f}s",
            event_type="SYSTEM",
            event_action=f"{request.method} {request.url.path}"
        )
        clear_request_context()
