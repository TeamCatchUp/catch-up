from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .incremental import handle_incremental_event
from .metadata import handle_metadata_event
from .responses import ignored_event_response

ScheduleTask = Callable[..., None]

_INCREMENTAL_EVENTS = frozenset({
    "issues",
    "issue_comment",
    "pull_request",
    "pull_request_review",
    "pull_request_review_comment",
    "pull_request_review_thread",
})

_METADATA_EVENTS = frozenset({
    "installation",
    "installation_repositories",
    "repository",
    "organization",
    "membership",
    "member",
})


async def handle_webhook(
    *,
    event_name: str | None,
    payload: dict[str, Any],
    schedule_task: ScheduleTask,
) -> dict[str, Any]:
    normalized_event = str(event_name or "").strip().lower()

    if normalized_event == "ping":
        return ignored_event_response(
            event=normalized_event,
            reason="handshake",
        )

    if normalized_event in _INCREMENTAL_EVENTS:
        return await handle_incremental_event(
            event_name=normalized_event,
            payload=payload,
        )

    if normalized_event in _METADATA_EVENTS:
        return await handle_metadata_event(
            event_name=normalized_event,
            payload=payload,
            schedule_task=schedule_task,
        )

    return ignored_event_response(
        event=normalized_event,
        reason="unsupported_event",
    )
