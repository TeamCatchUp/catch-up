from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from catchup.connectors.slack import webhook_service
from catchup.connectors.slack.schemas import SlackEventWrapper
from catchup.audit.enums import AuditEventStatus, AuditLevel
from catchup.events.enums import SyncTriggerEventAction
from catchup.sync.audit import SyncAuditContext, emit_sync_trigger_audit
from catchup.sync.incremental import ingest_record_changes, normalize_slack_event
from catchup.sync.incremental.full_sync_guard import filter_record_changes_by_full_sync

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

        guard_result = filter_record_changes_by_full_sync(db, changes)
        blocked_count = len(guard_result.blocked_changes)
        if blocked_count > 0:
            blocked_targets = guard_result.blocked_targets
            if not guard_result.allowed_changes:
                logger.info(
                    "[SLACK][WEBHOOK][INGRESS] Incremental blocked before ingest: team_id=%s, source=webhook, blocked_count=%s, blocked_targets=%s",
                    team_id,
                    blocked_count,
                    [
                        f"{target.target_type}:{target.target_id}"
                        for target in blocked_targets
                    ],
                )
                return {
                    "status": "ignored",
                    "event_type": event_type,
                    "reason": "full_sync_required",
                    "blocked_count": blocked_count,
                }

            logger.info(
                "[SLACK][WEBHOOK][INGRESS] Incremental partially blocked before ingest: team_id=%s, source=webhook, allowed_count=%s, blocked_count=%s, blocked_targets=%s",
                team_id,
                len(guard_result.allowed_changes),
                blocked_count,
                [
                    f"{target.target_type}:{target.target_id}"
                    for target in blocked_targets
                ],
            )

        record_keys: list[str] = []
        if guard_result.allowed_changes:
            first_change = guard_result.allowed_changes[0]
            audit_context = SyncAuditContext(
                connector=first_change.connector,
                scope_id=first_change.scope_id,
                target_id=first_change.parent_id,
            )
            emit_sync_trigger_audit(
                action=SyncTriggerEventAction.WEBHOOK_EVENT_RECEIVED,
                status=AuditEventStatus.ATTEMPT,
                audit_context=audit_context,
                context=(
                    f"stage=record_change_ingest,event_name={event_type},"
                    f"event_kind={first_change.event_kind},change_count={len(guard_result.allowed_changes)}"
                ),
            )
            try:
                record_keys = ingest_record_changes(db, guard_result.allowed_changes)
            except Exception as exc:
                emit_sync_trigger_audit(
                    action=SyncTriggerEventAction.WEBHOOK_EVENT_RECEIVED,
                    status=AuditEventStatus.FAIL,
                    audit_context=audit_context,
                    context=(
                        f"stage=record_change_ingest_failed,event_name={event_type},"
                        f"event_kind={first_change.event_kind},error={str(exc).strip()[:200]}"
                    ),
                    level=AuditLevel.ERROR,
                )
                raise
            emit_sync_trigger_audit(
                action=SyncTriggerEventAction.WEBHOOK_EVENT_RECEIVED,
                status=AuditEventStatus.SUCCESS,
                audit_context=audit_context,
                context=(
                    f"stage=record_change_ingested,event_name={event_type},"
                    f"record_key_count={len(record_keys)},blocked_count={blocked_count}"
                ),
            )
        response = {"status": "accepted", "event_type": event_type, "record_keys": record_keys}
        if blocked_count > 0:
            response["blocked_count"] = blocked_count
        return response

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
