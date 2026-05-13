from __future__ import annotations

import json
from typing import Any
from typing import Callable
from typing import TypeVar

import httpx

from catchup.connectors.channel_talk.exceptions import ChannelTalkPayloadError

ParsedPayloadT = TypeVar("ParsedPayloadT")


def extract_response_error_metadata(response: httpx.Response) -> dict[str, Any]:
    request_id = response.headers.get("x-request-id") or response.headers.get(
        "x-correlation-id"
    )

    body: Any
    try:
        body = response.json()
    except ValueError:
        body = response.text[:500].strip() or None

    metadata: dict[str, Any] = {"status_code": response.status_code}
    if request_id:
        metadata["request_id"] = request_id
    if body is not None:
        metadata["body"] = body
    return metadata


def build_since_limit_params(
    *,
    since: str | None,
    limit: int,
    max_limit: int = 500,
) -> dict[str, Any]:
    normalized_limit = min(max(int(limit), 1), max_limit)
    params: dict[str, Any] = {"limit": normalized_limit}
    if since is not None and str(since).strip():
        params["since"] = str(since).strip()
    return params


def is_success_response(response: httpx.Response) -> bool:
    return 200 <= response.status_code < 300


def build_upstream_error_message(
    *,
    service_name: str,
    status_code: int,
    metadata: dict[str, Any],
) -> str:
    message = f"{service_name} request failed with upstream status {status_code}"
    body = metadata.get("body")
    if body is None:
        return message

    if isinstance(body, str):
        body_text = body
    else:
        body_text = json.dumps(body, ensure_ascii=False, default=str)
    if not body_text:
        return message
    return f"{message}: body={body_text}"


def decode_response_json(response: httpx.Response, *, error_message: str) -> Any:
    try:
        return response.json()
    except ValueError as exc:
        raise ChannelTalkPayloadError(error_message) from exc


def parse_channel_talk_payload(
    payload: Any,
    *,
    parser: Callable[[Any], ParsedPayloadT],
    log_event: str,
    error_message: str,
    logger: Any,
) -> ParsedPayloadT:
    try:
        return parser(payload)
    except ValueError as exc:
        logger.exception(log_event)
        raise ChannelTalkPayloadError(error_message) from exc
