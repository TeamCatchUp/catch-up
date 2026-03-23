from __future__ import annotations

from typing import Any


def url_verification_response(*, challenge: str | None) -> dict[str, Any]:
    return {"challenge": challenge}


def ignored_event_response(
    *,
    event_type: str,
    reason: str,
    **extra: Any,
) -> dict[str, Any]:
    response = {
        "status": "ignored",
        "event_type": event_type,
        "reason": reason,
    }
    response.update(extra)
    return response


def ignored_wrapper_response(*, wrapper_type: str) -> dict[str, Any]:
    return {"status": "ignored", "wrapper_type": wrapper_type}


def accepted_incremental_response(
    *,
    event_type: str,
    record_keys: list[str],
    blocked_count: int = 0,
) -> dict[str, Any]:
    response = {
        "status": "accepted",
        "event_type": event_type,
        "record_keys": record_keys,
    }
    if blocked_count > 0:
        response["blocked_count"] = blocked_count
    return response


def processed_metadata_response(*, event_type: str) -> dict[str, Any]:
    return {"status": "processed", "event_type": event_type}


def metadata_error_response() -> dict[str, Any]:
    return {"status": "error", "reason": "processing_failed"}
