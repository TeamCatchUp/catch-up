from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from catchup.connectors.github.webhook.metadata import handle_metadata_event
from catchup.sync.incremental.resolve import resolve_github_event
from catchup.sync.incremental.service import get_incremental_service

logger = logging.getLogger(__name__)

ScheduleTask = Callable[..., None]

SUPPORTED_INCREMENTAL_EVENTS = frozenset({
    "issues",
    "issue_comment",
    "pull_request",
    "pull_request_review",
    "pull_request_review_comment",
    "pull_request_review_thread",
})

SUPPORTED_METADATA_EVENTS = frozenset({
    "installation",
    "installation_repositories",
    "repository",
    "organization",
    "membership",
    "member",
})


async def handle_github_webhook(
    *,
    event_name: str | None,
    payload: dict[str, Any],
    schedule_task: ScheduleTask,
) -> dict[str, Any]:
    normalized_event = str(event_name or "").strip().lower()

    if normalized_event == "ping":
        return _ignored_event_response(
            event=normalized_event,
            reason="handshake",
        )

    if normalized_event in SUPPORTED_INCREMENTAL_EVENTS:
        return await _handle_incremental_event(
            event_name=normalized_event,
            payload=payload,
        )

    if normalized_event in SUPPORTED_METADATA_EVENTS:
        return await handle_metadata_event(
            event_name=normalized_event,
            payload=payload,
            schedule_task=schedule_task,
        )

    return _ignored_event_response(
        event=normalized_event,
        reason="unsupported_event",
    )


async def _handle_incremental_event(
    *,
    event_name: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    changes = resolve_github_event(
        event_name=event_name,
        payload=payload,
    )
    if not changes:
        return _ignored_event_response(
            event=event_name,
            reason="unsupported_payload",
        )

    result = await get_incremental_service().ingest_changes_async(
        changes=changes,
        event_name=event_name,
    )
    if result.blocked_count > 0:
        if not result.record_keys:
            logger.info(
                "[GITHUB][WEBHOOK][INGRESS] Incremental blocked before ingest: installation_id=%s, source=webhook, blocked_count=%s, blocked_targets=%s",
                changes[0].scope_id,
                result.blocked_count,
                result.blocked_target_keys,
            )
            return _ignored_event_response(
                event=event_name,
                reason="full_sync_required",
                blocked_count=result.blocked_count,
            )

        logger.info(
            "[GITHUB][WEBHOOK][INGRESS] Incremental partially blocked before ingest: installation_id=%s, source=webhook, allowed_count=%s, blocked_count=%s, blocked_targets=%s",
            changes[0].scope_id,
            len(result.record_keys),
            result.blocked_count,
            result.blocked_target_keys,
        )

    return _accepted_incremental_response(
        event=event_name,
        record_keys=result.record_keys,
        blocked_count=result.blocked_count,
    )


def _ignored_event_response(
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


def _accepted_incremental_response(
    *,
    event: str,
    record_keys: list[str],
    blocked_count: int = 0,
) -> dict[str, Any]:
    response: dict[str, Any] = {
        "status": "accepted",
        "event": event,
        "record_keys": record_keys,
    }
    if blocked_count > 0:
        response["blocked_count"] = blocked_count
    return response
