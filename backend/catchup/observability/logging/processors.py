from __future__ import annotations

from typing import Any
from typing import Final

import structlog

from catchup.configs.config import settings

MAX_STRING_LENGTH = 2048
MAX_LIST_LENGTH = 50
SENSITIVE_KEYS = {
    "password",
    "passphrase",
    "authorization",
    "cookie",
    "set-cookie",
    "access_token",
    "refresh_token",
    "id_token",
    "token",
    "client_secret",
    "api_key",
    "secret",
    "private_key",
    "name",
}


def _sanitize_and_truncate(value: Any) -> Any:
    """
    value에 대해서 재귀적으로 민감 정보를 제거하고
    길이 상한을 초과하는 value는 초과분을 생략한다.
    """
    if isinstance(value, dict):
        return {
            k: _sanitize_and_truncate(v)
            for k, v in value.items()
            if str(k).lower() not in SENSITIVE_KEYS
        }

    if isinstance(value, list):
        items = [_sanitize_and_truncate(item) for item in value[:MAX_LIST_LENGTH]]
        if len(value) > MAX_LIST_LENGTH:
            items.append({"_truncated_items": len(value) - MAX_LIST_LENGTH})
        return items

    if isinstance(value, str) and len(value) > MAX_STRING_LENGTH:
        return f"{value[:MAX_STRING_LENGTH]}...[truncated]"

    return value


def process_audit_payload(
    _: Any, __: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """
    로그 메타데이터에서 민감 정보를 삭제하고 길이 제한을 적용하는 프로세서.
    """

    metadata = event_dict.get("metadata")
    if metadata and isinstance(metadata, dict):
        event_dict["metadata"] = _sanitize_and_truncate(metadata)

    return event_dict


def ensure_required_fields(
    _: Any, __: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """
    로그에서 필수 필드를 정규화하는 프로세서.
    """

    event_dict.setdefault("service", settings.SERVICE_NAME)
    event_dict.setdefault("environment", settings.ENV)
    event_dict.setdefault("version", settings.APP_VERSION)

    if event_dict.get("metadata") is None:
        event_dict["metadata"] = {}

    return event_dict


SHARED_PROCESSORS: Final[list[Any]] = [
    structlog.contextvars.merge_contextvars,
    structlog.stdlib.add_log_level,
    structlog.stdlib.add_logger_name,
    process_audit_payload,
    ensure_required_fields,
]
