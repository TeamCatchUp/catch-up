from __future__ import annotations

from typing import Any

import structlog

from catchup.connectors.github.webhook.metadata import handle_metadata_event
from catchup.sync.incremental.resolve import resolve_github_event
from catchup.sync.incremental.service import get_incremental_service
from catchup.sync.ingress.types import GithubWebhookRequest

logger = structlog.get_logger(__name__)

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
    request: GithubWebhookRequest,
) -> dict[str, Any]:
    if request.event_name == "ping":
        return _ignored_event_response(
            event=request.event_name,
            reason="handshake",
        )

    if request.event_name in SUPPORTED_INCREMENTAL_EVENTS:
        return await _handle_incremental_event(request)

    if request.event_name in SUPPORTED_METADATA_EVENTS:
        return await handle_metadata_event(request)

    return _ignored_event_response(
        event=request.event_name,
        reason="unsupported_event",
    )


async def _handle_incremental_event(
    request: GithubWebhookRequest,
) -> dict[str, Any]:
    changes = resolve_github_event(
        event_name=request.event_name,
        payload=request.payload,
    )
    if not changes:
        return _ignored_event_response(
            event=request.event_name,
            reason="unsupported_payload",
        )

    result = await get_incremental_service().ingest_changes_async(
        changes=changes,
        event_name=request.event_name,
    )
    if result.blocked_count > 0:
        if not result.record_keys:
            logger.info(
                "github_incremental_blocked_before_full_sync",
                event_name=request.event_name,
                scope_id=changes[0].scope_id,
                blocked_count=result.blocked_count,
            )
            return _ignored_event_response(
                event=request.event_name,
                reason="full_sync_required",
                blocked_count=result.blocked_count,
            )

        logger.info(
            "github_incremental_partially_blocked",
            event_name=request.event_name,
            scope_id=changes[0].scope_id,
            record_key_count=len(result.record_keys),
            blocked_count=result.blocked_count,
        )

    return _accepted_incremental_response(
        event=request.event_name,
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
