from __future__ import annotations

import logging
from typing import Any

from catchup.connectors.jira.webhook.metadata import (
    SUPPORTED_METADATA_EVENTS,
    handle_metadata_event,
)
from catchup.sync.incremental.resolve import resolve_jira_event
from catchup.sync.incremental.service import get_incremental_service

logger = logging.getLogger(__name__)

SUPPORTED_INCREMENTAL_EVENTS = frozenset({
    "jira:issue_created",
    "jira:issue_updated",
    "jira:issue_deleted",
    "comment_created",
    "comment_updated",
    "comment_deleted",
})


async def handle_jira_webhook(
    *,
    cloud_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    event_type = str(payload.get("webhookEvent") or "").strip().lower()

    if event_type in SUPPORTED_METADATA_EVENTS:
        return await handle_metadata_event(
            cloud_id=cloud_id,
            event_type=event_type,
            payload=payload,
        )

    if event_type in SUPPORTED_INCREMENTAL_EVENTS:
        return await _handle_incremental_event(
            cloud_id=cloud_id,
            event_type=event_type,
            payload=payload,
        )

    logger.info(
        "[JIRA][WEBHOOK][INGRESS] Ignored payload: cloud_id=%s, event_type=%s",
        cloud_id,
        event_type,
    )
    return _ignored_event_response(
        event_type=event_type,
        reason="unsupported_event",
    )


async def _handle_incremental_event(
    *,
    cloud_id: str,
    event_type: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    changes = resolve_jira_event(
        cloud_id=cloud_id,
        payload=payload,
    )
    if not changes:
        logger.info(
            "[JIRA][WEBHOOK][INGRESS] Ignored payload: cloud_id=%s, event_type=%s",
            cloud_id,
            event_type,
        )
        return _ignored_event_response(
            event_type=event_type,
            reason="unsupported_payload",
        )

    result = await get_incremental_service().ingest_changes_async(
        changes=changes,
        event_name=event_type,
    )
    if result.blocked_count > 0:
        if not result.record_keys:
            logger.info(
                "[JIRA][WEBHOOK][INGRESS] Incremental blocked before ingest: cloud_id=%s, source=webhook, blocked_count=%s, blocked_targets=%s",
                cloud_id,
                result.blocked_count,
                result.blocked_target_keys,
            )
            return _ignored_event_response(
                event_type=event_type,
                reason="full_sync_required",
                blocked_count=result.blocked_count,
            )

        logger.info(
            "[JIRA][WEBHOOK][INGRESS] Incremental partially blocked before ingest: cloud_id=%s, source=webhook, allowed_count=%s, blocked_count=%s, blocked_targets=%s",
            cloud_id,
            len(result.record_keys),
            result.blocked_count,
            result.blocked_target_keys,
        )

    return _accepted_incremental_response(
        event_type=event_type,
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
