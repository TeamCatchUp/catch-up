from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable

from fastapi import Request, Response

from catchup.observability.logging.context import (
    bind_base_context,
    clear_request_context,
)

REQUEST_ID_HEADER = "X-Request-Id"
AMZN_TRACE_HEADER = "X-Amzn-Trace-Id"

CallNext = Callable[[Request], Awaitable[Response]]

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

async def request_context_middleware(request: Request, call_next: CallNext) -> Response:
    trace_id = _resolve_trace_id(request)

    clear_request_context()
    bind_base_context(trace_id)
    request.state.trace_id = trace_id

    try:
        response = await call_next(request)
    finally:
        clear_request_context()

    response.headers[REQUEST_ID_HEADER] = trace_id
    return response