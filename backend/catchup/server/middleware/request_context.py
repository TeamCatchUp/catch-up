from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import BackgroundTasks, Request, Response
from fastapi.concurrency import run_in_threadpool

from catchup.auth.jwt import verify_token
from catchup.db.engine import SessionLocal
from catchup.db.users import get_user_by_email, get_user_by_sub
from catchup.observability.logging.context import (
    bind_actor_context,
    bind_base_context,
    clear_request_context,
)
from catchup.events.context import current_bg_tasks


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


def _resolve_actor_from_access_token(access_token: str | None) -> dict[str, Any] | None:
    if not access_token:
        return None
    
    try:
        payload = verify_token(access_token, "access")
    except Exception:
        return None
    
    sub = payload.get("sub")
    email = payload.get("email")

    if not sub:
        return {
            "user_id": None,
            "email": email,
            "role": None,
            "department": None
        }

    db = SessionLocal()
    try:
        user = get_user_by_sub(db, sub)
        if not user and email:
            user = get_user_by_email(db, email)
        if user:
            return {
                "user_id": sub,
                "email": user.email, 
                "role": str(user.role) if user.role else None,
                "department": user.department,
            }
    finally:
        db.close()
    
    return {
        "user_id": sub,
        "email": email,
        "role": None,
        "department": None,
    }


async def request_context_middleware(
    request: Request,
    call_next: CallNext
) -> Response:

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
    
    print(f"trace_id: {request.state.trace_id}")
    print(f"actor: {request.state.actor}")
    
    
    # BackgroundTasks를 ContextVars로 설정
    bg_tasks = BackgroundTasks()
    token = current_bg_tasks.set(bg_tasks)
    
    try:
        # 비즈니스 로직 수행
        response: Response = await call_next(request)
        
        response.headers[REQUEST_ID_HEADER] = trace_id
        
        if response.background is None:
            response.background = bg_tasks
        else:
            response.background.tasks.extend(bg_tasks.tasks)
        
        return response
    finally:
        current_bg_tasks.reset(token)
        clear_request_context()
