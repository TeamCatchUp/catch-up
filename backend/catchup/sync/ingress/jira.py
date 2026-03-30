from __future__ import annotations

from typing import Any

import structlog

from catchup.connectors.jira.webhook.metadata import handle_metadata_event
from catchup.sync.incremental.resolve import resolve_jira_event
from catchup.sync.incremental.service import get_incremental_service
from catchup.sync.ingress.types import JiraWebhookRequest

logger = structlog.get_logger(__name__)

SUPPORTED_INCREMENTAL_EVENTS = frozenset({
    "jira:issue_created",
    "jira:issue_updated",
    "jira:issue_deleted",
    "comment_created",
    "comment_updated",
    "comment_deleted",
})

SUPPORTED_METADATA_EVENTS = frozenset({
    "jira:project_created",
    "jira:project_updated",
    "jira:project_deleted",
    "sprint_created",
    "sprint_updated",
    "sprint_deleted",
    "user_created",
    "user_updated",
    "user_deleted",
})


async def handle_jira_webhook(
    *,
    request: JiraWebhookRequest,
) -> dict[str, Any]:
    if request.event_type in SUPPORTED_METADATA_EVENTS:
        return await handle_metadata_event(request)

    if request.event_type in SUPPORTED_INCREMENTAL_EVENTS:
        return await _handle_incremental_event(request)

    logger.debug(
        "jira_webhook_ignored_unsupported_event",
        cloud_id=request.cloud_id,
        event_type=request.event_type,
    )
    return _ignored_event_response(
        event_type=request.event_type,
        reason="unsupported_event",
    )


async def _handle_incremental_event(
    request: JiraWebhookRequest,
) -> dict[str, Any]:
    changes = resolve_jira_event(
        cloud_id=request.cloud_id,
        payload=request.payload,
    )
    if not changes:
        logger.debug(
            "jira_webhook_ignored_unsupported_payload",
            cloud_id=request.cloud_id,
            event_type=request.event_type,
        )
        return _ignored_event_response(
            event_type=request.event_type,
            reason="unsupported_payload",
        )

    result = await get_incremental_service().ingest_changes_async(
        changes=changes,
        event_name=request.event_type,
    )
    if result.blocked_count > 0:
        if not result.record_keys:
            logger.info(
                "jira_incremental_blocked_before_full_sync",
                cloud_id=request.cloud_id,
                event_type=request.event_type,
                blocked_count=result.blocked_count,
            )
            return _ignored_event_response(
                event_type=request.event_type,
                reason="full_sync_required",
                blocked_count=result.blocked_count,
            )

        logger.info(
            "jira_incremental_partially_blocked",
            cloud_id=request.cloud_id,
            event_type=request.event_type,
            record_key_count=len(result.record_keys),
            blocked_count=result.blocked_count,
        )

    return _accepted_incremental_response(
        event_type=request.event_type,
        record_keys=result.record_keys,
        blocked_count=result.blocked_count,
    )


def _ignored_event_response(
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


def _accepted_incremental_response(
    *,
    event_type: str,
    record_keys: list[str],
    blocked_count: int = 0,
) -> dict[str, Any]:
    response: dict[str, Any] = {
        "status": "accepted",
        "event_type": event_type,
        "record_keys": record_keys,
    }
    if blocked_count > 0:
        response["blocked_count"] = blocked_count
    return response
