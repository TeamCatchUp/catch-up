import logging
import time
from typing import Any

from catchup.configs.config import settings
from catchup.observability.logging.constants import LOG_LEVELS

CONSOLE_EXCLUDE_KEYS: set[str] = {
    "actor",
    "environment",
    "event_action",
    "event_type",
    "metadata",
    "service",
    "trace_id",
    "version",
    "remote_addr",
}


# TODO: 협의 후 활성화 또는 삭제
def resolve_console_exclude_keys(log_level: int) -> str:
    if log_level == logging.DEBUG:
        CONSOLE_EXCLUDE_KEYS.discard("metadata")
        return "metadata_exposed_on_debug_level"
    return ""


def resolve_log_level() -> int:
    return LOG_LEVELS[settings.LOG_LEVEL.upper()]


def reorder_console_logger(
    _: Any, __: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    logger_name = event_dict.pop("logger", None)
    if logger_name:
        event = event_dict.get("event", "")
        event_dict["event"] = f"[{logger_name}] {event}"
    return event_dict


def drop_console_noise_fields(
    _: Any, __: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    for key in CONSOLE_EXCLUDE_KEYS:
        event_dict.pop(key, None)
    return event_dict


def reorder_audit_keys(_: Any, __: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    """감사 로그 JSON의 키 순서를 읽기 편하게 재배치하는 커스텀 프로세서"""

    desired_order = [
        "timestamp",
        "level",
        "event",
        "status",
        "actor",
        "metadata",
        "trace_id",
    ]

    ordered_dict = {}
    for key in desired_order:
        if key in event_dict:
            ordered_dict[key] = event_dict.pop(key)

    ordered_dict.update(event_dict)
    return ordered_dict


def unix_timestamp_namer(_: str):
    base_path = settings.LOG_AUDIT_FILE_PATH.replace(".jsonl", "")
    return f"{base_path}.{int(time.time())}.jsonl"
