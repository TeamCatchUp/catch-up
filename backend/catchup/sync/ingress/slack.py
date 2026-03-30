from __future__ import annotations

import logging
from typing import Any

from catchup.connectors.slack.schemas import SlackEventWrapper
from catchup.connectors.slack.webhook.metadata import (
    SUPPORTED_METADATA_EVENTS,
    handle_metadata_event,
)
from catchup.sync.incremental.resolve import resolve_slack_event
from catchup.sync.incremental.service import get_incremental_service

logger = logging.getLogger(__name__)

IGNORED_MESSAGE_SUBTYPES = frozenset(
    {
        "channel_join",
        "channel_leave",
        "group_join",
        "group_leave",
        "channel_topic",
        "channel_purpose",
        "channel_name",
        "group_topic",
        "group_purpose",
        "group_name",
    }
)
INCREMENTAL_MESSAGE_SUBTYPES = frozenset(
    {
        "",
        "bot_message",
        "file_share",
        "message_changed",
        "message_deleted",
        "thread_broadcast",
    }
)


def handle_slack_webhook(
    *,
    payload: dict[str, Any],
) -> dict[str, Any]:
    event_wrapper = SlackEventWrapper(**payload)

    if event_wrapper.type == "url_verification":
        logger.info("[SLACK][WEBHOOK][INGRESS] URL verification received")
        return {"challenge": event_wrapper.challenge}

    if event_wrapper.type != "event_callback":
        logger.warning(
            "[SLACK][WEBHOOK][INGRESS] Unknown wrapper type: type=%s",
            event_wrapper.type,
        )
        return {
            "status": "ignored",
            "wrapper_type": event_wrapper.type,
        }

    if not event_wrapper.event:
        logger.warning("[SLACK][WEBHOOK][INGRESS] Empty event callback")
        return {"status": "ignored", "reason": "empty_event"}

    if not event_wrapper.team_id:
        logger.warning("[SLACK][WEBHOOK][INGRESS] Missing team_id in callback")
        return {"status": "ignored", "reason": "missing_team_id"}

    event = event_wrapper.event
    event_type = str(event.get("type") or "").strip()
    event_subtype = str(event.get("subtype") or "").strip()
    team_id = event_wrapper.team_id

    logger.info(
        "[SLACK][WEBHOOK][INGRESS] Received event: team_id=%s, type=%s, subtype=%s",
        team_id,
        event_type,
        event_subtype,
    )

    if event_type in SUPPORTED_METADATA_EVENTS:
        return handle_metadata_event(
            team_id=team_id,
            event_type=event_type,
            event=event,
        )

    if event_type == "message":
        return _handle_incremental_event(
            team_id=team_id,
            event_type=event_type,
            event=event,
        )

    logger.debug(
        "[SLACK][WEBHOOK][INGRESS] Ignored unsupported event: team_id=%s, type=%s, subtype=%s",
        team_id,
        event_type,
        event_subtype,
    )
    return _ignored_event_response(
        event_type=event_type,
        reason="unsupported_event",
    )


def _handle_incremental_event(
    *,
    team_id: str,
    event_type: str,
    event: dict[str, Any],
) -> dict[str, Any]:
    if not _is_supported_channel_message(event):
        return _ignored_event_response(
            event_type=event_type,
            reason="unsupported_channel",
        )

    subtype_policy = _classify_message_subtype(event)
    if subtype_policy == "ignore":
        return _ignored_event_response(
            event_type=event_type,
            reason="ignored_subtype",
        )
    if subtype_policy == "unsupported":
        return _ignored_event_response(
            event_type=event_type,
            reason="unsupported_subtype",
        )

    changes = resolve_slack_event(team_id=team_id, event=event)
    if not changes:
        return _ignored_event_response(
            event_type=event_type,
            reason="unsupported_message_payload",
        )

    result = get_incremental_service().ingest_changes(
        changes=changes,
        event_name=event_type,
    )
    if result.blocked_count > 0:
        if not result.record_keys:
            logger.info(
                "[SLACK][WEBHOOK][INGRESS] Incremental blocked before ingest: team_id=%s, source=webhook, blocked_count=%s, blocked_targets=%s",
                team_id,
                result.blocked_count,
                result.blocked_target_keys,
            )
            return _ignored_event_response(
                event_type=event_type,
                reason="full_sync_required",
                blocked_count=result.blocked_count,
            )

        logger.info(
            "[SLACK][WEBHOOK][INGRESS] Incremental partially blocked before ingest: team_id=%s, source=webhook, allowed_count=%s, blocked_count=%s, blocked_targets=%s",
            team_id,
            len(result.record_keys),
            result.blocked_count,
            result.blocked_target_keys,
        )

    return _accepted_incremental_response(
        event_type=event_type,
        record_keys=result.record_keys,
        blocked_count=result.blocked_count,
    )


def _classify_message_subtype(event: dict[str, Any]) -> str:
    subtype = str(event.get("subtype") or "").strip().lower()
    if subtype in IGNORED_MESSAGE_SUBTYPES:
        return "ignore"
    if subtype in INCREMENTAL_MESSAGE_SUBTYPES:
        return "incremental"
    return "unsupported"


def _is_supported_channel_message(event: dict[str, Any]) -> bool:
    channel_id = str(event.get("channel") or "").strip()
    return channel_id.startswith(("C", "G"))


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
