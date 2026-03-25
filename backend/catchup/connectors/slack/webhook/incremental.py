from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from catchup.audit.enums import AuditEventStatus, AuditLevel
from catchup.events.enums import SyncTriggerEventAction
from catchup.sync.audit import SyncAuditContext, emit_sync_trigger_audit
from catchup.sync.incremental import ingest_record_changes, normalize_slack_event
from catchup.sync.incremental.policy.full_sync_guard import (
    filter_record_changes_by_full_sync,
)

from .responses import accepted_incremental_response, ignored_event_response

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


def handle_incremental_event(
    *,
    db: Session,
    team_id: str,
    event_type: str,
    event: dict[str, Any],
) -> dict[str, Any]:
    if not is_supported_channel_message(event):
        return ignored_event_response(
            event_type=event_type,
            reason="unsupported_channel",
        )

    subtype_policy = classify_message_subtype(event)
    if subtype_policy == "ignore":
        return ignored_event_response(
            event_type=event_type,
            reason="ignored_subtype",
        )
    if subtype_policy == "unsupported":
        return ignored_event_response(
            event_type=event_type,
            reason="unsupported_subtype",
        )

    changes = normalize_slack_event(team_id=team_id, event=event)
    if not changes:
        return ignored_event_response(
            event_type=event_type,
            reason="unsupported_message_payload",
        )

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
            return ignored_event_response(
                event_type=event_type,
                reason="full_sync_required",
                blocked_count=blocked_count,
            )

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

    return accepted_incremental_response(
        event_type=event_type,
        record_keys=record_keys,
        blocked_count=blocked_count,
    )


def classify_message_subtype(event: dict[str, Any]) -> str:
    subtype = str(event.get("subtype") or "").strip().lower()
    if subtype in IGNORED_MESSAGE_SUBTYPES:
        return "ignore"
    if subtype in INCREMENTAL_MESSAGE_SUBTYPES:
        return "incremental"
    return "unsupported"


def is_supported_channel_message(event: dict[str, Any]) -> bool:
    channel_id = str(event.get("channel") or "").strip()
    return channel_id.startswith(("C", "G"))
