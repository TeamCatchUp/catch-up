from __future__ import annotations

from typing import Any


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


def processed_metadata_response(
    *,
    event_type: str,
    entity: str,
    key: str | None = None,
    entity_id: int | str | None = None,
) -> dict[str, Any]:
    response: dict[str, Any] = {
        "status": "processed",
        "event_type": event_type,
        "entity": entity,
    }
    if key is not None:
        response["key"] = key
    if entity_id is not None:
        response["id"] = entity_id
    return response
