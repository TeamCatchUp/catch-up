from __future__ import annotations

from typing import Any

import structlog

from catchup.connectors.slack.webhook.metadata import handle_metadata_event
from catchup.sync.incremental.resolve import resolve_slack_event
from catchup.sync.incremental.service import get_incremental_service
from catchup.sync.ingress.types import SlackWebhookRequest

logger = structlog.get_logger(__name__)

SUPPORTED_METADATA_EVENTS = frozenset({
    "channel_created",
    "channel_rename",
    "group_created",
    "group_rename",
    "channel_deleted",
    "group_deleted",
    "channel_archive",
    "channel_unarchive",
    "group_archive",
    "group_unarchive",
    "member_joined_channel",
    "member_left_channel",
    "team_join",
    "user_change",
})


def handle_slack_webhook(
    *,
    request: SlackWebhookRequest,
) -> dict[str, Any]:
    if request.wrapper_type == "url_verification":
        logger.debug("slack_webhook_url_verification")
        return {"challenge": request.challenge}

    if request.wrapper_type != "event_callback":
        logger.warning(
            "slack_webhook_ignored_unknown_wrapper",
            wrapper_type=request.wrapper_type,
        )
        return {
            "status": "ignored",
            "wrapper_type": request.wrapper_type,
        }

    if not request.event:
        logger.warning("slack_webhook_ignored_empty_event")
        return {"status": "ignored", "reason": "empty_event"}

    if not request.team_id:
        logger.warning("slack_webhook_ignored_missing_team_id")
        return {"status": "ignored", "reason": "missing_team_id"}

    if request.event_type in SUPPORTED_METADATA_EVENTS:
        return handle_metadata_event(request)

    if request.event_type == "message":
        return _handle_incremental_event(request)

    logger.warning(
        "slack_webhook_ignored_unsupported_event",
        team_id=request.team_id,
        event_type=request.event_type,
        event_subtype=request.event_subtype,
    )
    return _ignored_event_response(
        event_type=request.event_type,
        reason="unsupported_event",
    )


def _handle_incremental_event(
    request: SlackWebhookRequest,
) -> dict[str, Any]:
    resolved = resolve_slack_event(team_id=request.team_id, event=request.event)
    if not resolved.changes:
        return _ignored_event_response(
            event_type=request.event_type,
            reason=resolved.reason or "unsupported_message_payload",
        )

    result = get_incremental_service().ingest_changes(
        changes=resolved.changes,
        event_name=request.event_type,
    )
    if result.blocked_count > 0:
        if not result.record_keys:
            logger.info(
                "slack_incremental_blocked_before_full_sync",
                team_id=request.team_id,
                event_type=request.event_type,
                blocked_count=result.blocked_count,
            )
            return _ignored_event_response(
                event_type=request.event_type,
                reason="full_sync_required",
                blocked_count=result.blocked_count,
            )

        logger.info(
            "slack_incremental_partially_blocked",
            team_id=request.team_id,
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
