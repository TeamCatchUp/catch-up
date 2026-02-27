from __future__ import annotations

import json
from typing import Any

from catchup.configs.config import settings

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
}

DEFAULT_ACTOR = {
    "user_id": None,
    "email": None,
    "role": None,
    "department": None,
}

MAX_METADATA_BYTES = 16 * 1024
MAX_STRING_LENGTH = 2048
MAX_USER_AGENT_LENGTH = 512
MAX_ERROR_SUMMARY_LENGTH = 1024
MAX_LIST_LENGTH = 50

# token / password 제거
def _sanitize_nested(value: Any) -> Any:
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            if str(key).lower() in SENSITIVE_KEYS:
                continue
            sanitized[key] = _sanitize_nested(item)
        return sanitized

    if isinstance(value, list):
        return [_sanitize_nested(item) for item in value]

    return value

# 긴 문자열 자르기
def _truncate_text(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return f"{value[:limit]}...[truncated]"

# 메타데이터 필드에 따라서 길이 제한
def _truncate_nested(value: Any, parent_key:str = "") -> Any:
    if isinstance(value, dict):
        truncated: dict[str, Any] = {}
        for key, item in value.items():
            truncated[key] = _truncate_nested(item, str(key).lower())
        return truncated
    
    if isinstance(value, list):
        items = [_truncate_nested(item, parent_key) for item in value[:MAX_LIST_LENGTH]]
        if len(value) > MAX_LIST_LENGTH:
            items.append({"_truncated_items": len(value) - MAX_LIST_LENGTH})
        return items

    if isinstance(value, str):
        if parent_key == "user_agent":
            return _truncate_text(value, MAX_USER_AGENT_LENGTH)
        if parent_key == "error_summary":
            return _truncate_text(value, MAX_ERROR_SUMMARY_LENGTH)
        return _truncate_text(value, MAX_STRING_LENGTH)

    return value

# 메타데이터 용량 측정
def _metadata_size_in_bytes(metadata: dict[str, Any]) -> int:
    return len(json.dumps(metadata, ensure_ascii=False, default=str).encode("utf-8"))

# 메타데이터 dict 형태 보장
def _normalize_metadata(metadata: Any) -> dict[str, Any]:
    if metadata is None:
        return {}
    if isinstance(metadata, dict):
        return metadata
    return {"value": metadata}

# 메타데이터 용량 보장
def _enforce_metadata_size(metadata: dict[str, Any]) -> dict[str, Any]:
    if _metadata_size_in_bytes(metadata) <= MAX_METADATA_BYTES:
        return metadata
    
    truncated = _truncate_nested(metadata, "metadata")
    if isinstance(truncated, dict) and _metadata_size_in_bytes(truncated) <= MAX_METADATA_BYTES:
        truncated["_truncated"] = True
        return truncated
    
    return {
        "_truncated": True,
        "_summary": "metadata exceeded size limit and was compacted",
    }

# actor 필드 정규화 (user_id, email, role, department)
def _normalize_actor(actor: Any) -> dict[str, Any]:
    normalized = dict(DEFAULT_ACTOR)

    if not isinstance(actor, dict):
        return normalized
    
    for key in DEFAULT_ACTOR:
        normalized[key] = actor.get(key)
    
    return normalized

# 민감 정보 제거
def sanitize_secrets_processor(_: Any, __: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    sanitized = _sanitize_nested(dict(event_dict))
    if isinstance(sanitized, dict):
        return sanitized
    return {"event": str(sanitized)}

# 크기 제한
def truncate_large_fields_processor(_: Any, __: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    truncated = _truncate_nested(dict(event_dict))
    if not isinstance(truncated, dict):
        return {"event": str(truncated)}

    metadata = _normalize_metadata(truncated.get("metadata"))
    truncated["metadata"] = _enforce_metadata_size(metadata)
    return truncated

# 로그 스키마 표준화
def ensure_required_fields_processor(_: Any, __: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    event_dict.setdefault("service", settings.SERVICE_NAME)
    event_dict.setdefault("environment", str(settings.ENV))
    event_dict.setdefault("version", settings.APP_VERSIONS)
    event_dict.setdefault("trace_id", "unknown")

    event_dict["actor"] = _normalize_actor(event_dict.get("actor"))
    event_dict["metadata"] = _normalize_metadata(event_dict.get("metadata"))

    event_dict.setdefault("event_type", "SYSTEM")
    if "event_action" not in event_dict:
        event_dict["event_action"] = str(event_dict.get("event", "log"))

    return event_dict
