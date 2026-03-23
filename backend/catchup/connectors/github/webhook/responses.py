from __future__ import annotations

from typing import Any


def ignored_event_response(
    *,
    event: str,
    reason: str,
    **extra: Any,
) -> dict[str, Any]:
    response = {
        "status": "ignored",
        "event": event,
        "reason": reason,
    }
    response.update(extra)
    return response


def accepted_incremental_response(
    *,
    event: str,
    record_keys: list[str],
    blocked_count: int = 0,
) -> dict[str, Any]:
    response = {
        "status": "accepted",
        "event": event,
        "record_keys": record_keys,
    }
    if blocked_count > 0:
        response["blocked_count"] = blocked_count
    return response


def processed_metadata_response(
    *,
    event: str,
    installation_id: int,
    refresh_target: str,
) -> dict[str, Any]:
    return {
        "status": "processed",
        "event": event,
        "refresh_target": refresh_target,
        "installation_id": installation_id,
    }


def installation_status_response(
    *,
    status: str,
    installation_id: int,
) -> dict[str, Any]:
    return {
        "status": status,
        "installation_id": installation_id,
    }


def installation_repositories_response(
    *,
    installation_id: int,
    added: int,
    removed: int,
) -> dict[str, Any]:
    return {
        "status": "processed",
        "event": "installation_repositories",
        "installation_id": installation_id,
        "added": added,
        "removed": removed,
    }
