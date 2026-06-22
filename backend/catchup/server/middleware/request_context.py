from __future__ import annotations

import time
import uuid
from typing import Any

import structlog
from fastapi import HTTPException
from fastapi.concurrency import run_in_threadpool
from starlette.datastructures import MutableHeaders
from starlette.requests import Request
from starlette.types import ASGIApp
from starlette.types import Receive
from starlette.types import Scope
from starlette.types import Send

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


def _extract_amzn_root_trace(raw_header: str) -> str:
    parts = {}
    for segment in raw_header.split(";"):
        if "=" not in segment:
            continue
        key, value = segment.split("=", 1)
        parts[key.strip()] = value.strip()

    return parts.get("Root", raw_header)


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
        return AuditActor()
    except Exception as e:
        logger.error("unexpected_error_resolving_actor", error=str(e))
        return AuditActor()


class RequestContextMiddleware:
    """순수 ASGI 미들웨어. BaseHTTPMiddleware 대신 send_wrapper 패턴을 사용해
    SSE 스트리밍 응답과 호환된다."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(
        self, scope: Scope, receive: Receive, send: Send
    ) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope)
        trace_id = _resolve_trace_id(request)
        remote_addr = request.client.host if request.client else "unknown"

        clear_request_context()
        bind_base_context(trace_id, remote_addr)

        access_token = _extract_access_token(request)
        actor = await run_in_threadpool(
            _resolve_actor_from_access_token, access_token
        )
        bind_actor_context(actor)

        logger.debug(
            "request_trace_info",
            trace_id_=trace_id,
            actor_=actor.model_dump(mode="json"),
        )

        AuditContext.init()

        logger.debug(
            "http_request_started",
            method=request.method,
            path=request.url.path,
        )

        status_code = 500
        start_time = time.perf_counter()

        async def send_wrapper(message: Any) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                headers = MutableHeaders(scope=message)
                headers[REQUEST_ID_HEADER] = trace_id
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            process_time = time.perf_counter() - start_time
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
                event_action=f"{request.method} {request.url.path}",
            )
            clear_request_context()
