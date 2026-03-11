from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from catchup.connectors.slack import webhook_service
from catchup.connectors.slack.schemas import SlackEventWrapper
from catchup.sync.incremental import ingest_record_changes, normalize_slack_event

logger = logging.getLogger(__name__)

_CHANNEL_UPSERT_EVENTS = {"channel_created", "channel_rename", "group_created", "group_rename"}
_CHANNEL_DELETE_EVENTS = {"channel_deleted", "group_deleted"}
_CHANNEL_ARCHIVE_EVENTS = {"channel_archive", "channel_unarchive", "group_archive", "group_unarchive"}
_MEMBER_EVENTS = {"member_joined_channel", "member_left_channel"}
_USER_EVENTS = {"team_join", "user_change"}
_IGNORED_MESSAGE_SUBTYPES = frozenset(
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
_INCREMENTAL_MESSAGE_SUBTYPES = frozenset(
    {
        "",
        "bot_message",
        "file_share",
        "message_changed",
        "message_deleted",
        "thread_broadcast",
    }
)


def handle_webhook(
    *,
    db: Session,
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
        return {"status": "ignored", "wrapper_type": event_wrapper.type}

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

    if event_type in _CHANNEL_UPSERT_EVENTS:
        return _run_metadata_handler(
            team_id=team_id,
            event=event,
            event_type=event_type,
            db=db,
            handler=webhook_service.handle_channel_upsert,
            label="Channel upsert",
        )

    if event_type in _CHANNEL_DELETE_EVENTS:
        return _run_metadata_handler(
            team_id=team_id,
            event=event,
            event_type=event_type,
            db=db,
            handler=webhook_service.handle_channel_delete,
            label="Channel delete",
        )

    if event_type in _CHANNEL_ARCHIVE_EVENTS:
        return _run_metadata_handler(
            team_id=team_id,
            event=event,
            event_type=event_type,
            db=db,
            handler=webhook_service.handle_channel_archive,
            label="Channel archive",
        )

    if event_type in _MEMBER_EVENTS:
        if not _is_supported_channel_membership_event(event):
            return {"status": "ignored", "event_type": event_type, "reason": "unsupported_channel"}
        return _run_metadata_handler(
            team_id=team_id,
            event=event,
            event_type=event_type,
            db=db,
            handler=webhook_service.handle_member_event,
            label="Member event",
        )

    if event_type in _USER_EVENTS:
        return _run_metadata_handler(
            team_id=team_id,
            event=event,
            event_type=event_type,
            db=db,
            handler=webhook_service.handle_user_event,
            label="User event",
        )

    if event_type == "message":
        if not _is_supported_channel_message(event):
            return {"status": "ignored", "event_type": event_type, "reason": "unsupported_channel"}
        subtype_policy = _classify_message_subtype(event)
        if subtype_policy == "ignore":
            return {"status": "ignored", "event_type": event_type, "reason": "ignored_subtype"}
        if subtype_policy == "unsupported":
            return {"status": "ignored", "event_type": event_type, "reason": "unsupported_subtype"}
        changes = normalize_slack_event(team_id=team_id, event=event)
        if not changes:
            return {
                "status": "ignored",
                "event_type": event_type,
                "reason": "unsupported_message_payload",
            }

        record_keys = ingest_record_changes(db, changes)
        return {"status": "accepted", "event_type": event_type, "record_keys": record_keys}

    logger.debug(
        "[SLACK][WEBHOOK][INGRESS] Ignored unsupported event: team_id=%s, type=%s, subtype=%s",
        team_id,
        event_type,
        event_subtype,
    )
    return {"status": "ignored", "event_type": event_type}


def _classify_message_subtype(event: dict[str, Any]) -> str:
    subtype = str(event.get("subtype") or "").strip().lower()
    if subtype in _IGNORED_MESSAGE_SUBTYPES:
        return "ignore"
    if subtype in _INCREMENTAL_MESSAGE_SUBTYPES:
        return "incremental"
    return "unsupported"


def _is_supported_channel_message(event: dict[str, Any]) -> bool:
    channel_id = str(event.get("channel") or "").strip()
    return channel_id.startswith(("C", "G"))


def _is_supported_channel_membership_event(event: dict[str, Any]) -> bool:
    channel_type = str(event.get("channel_type") or "").strip().upper()
    if channel_type:
        return channel_type in {"C", "G"}

    channel_id = str(event.get("channel") or "").strip()
    return channel_id.startswith(("C", "G"))


def _run_metadata_handler(
    *,
    team_id: str,
    event: dict[str, Any],
    event_type: str,
    db: Session,
    handler,
    label: str,
) -> dict[str, Any]:
    try:
        handler(db, team_id, event)
        return {"status": "processed", "event_type": event_type}
    except Exception as exc:
        logger.error(
            "[SLACK][WEBHOOK][INGRESS] %s failed: team_id=%s, error=%s",
            label,
            team_id,
            exc,
        )
        return {"status": "error", "reason": "processing_failed"}
