from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from catchup.connectors.jira import webhook_service
from catchup.audit.enums import AuditEventStatus, AuditLevel
from catchup.events.enums import SyncTriggerEventAction
from catchup.sync.audit import SyncAuditContext, emit_sync_trigger_audit
from catchup.sync.incremental import ingest_record_changes, normalize_jira_event
from catchup.sync.incremental.full_sync_guard import filter_record_changes_by_full_sync

logger = logging.getLogger(__name__)

_INCREMENTAL_EVENTS = frozenset(
    {
        "jira:issue_created",
        "jira:issue_updated",
        "jira:issue_deleted",
        "comment_created",
        "comment_updated",
        "comment_deleted",
    }
)


def handle_webhook(
    *,
    db: Session,
    cloud_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    event_type = str(payload.get("webhookEvent") or "").strip().lower()

    if event_type in webhook_service.SUPPORTED_METADATA_EVENTS:
        return webhook_service.handle_metadata_event(
            db=db,
            cloud_id=cloud_id,
            event_type=event_type,
            payload=payload,
        )

    if event_type not in _INCREMENTAL_EVENTS:
        logger.info(
            "[JIRA][WEBHOOK][INGRESS] Ignored payload: cloud_id=%s, event_type=%s",
            cloud_id,
            event_type,
        )
        return {"status": "ignored", "event_type": event_type, "reason": "unsupported_event"}

    # comment_* 이벤트도 별도 comment record를 만들지 않고 부모 Jira Issue를 다시 sync한다.
    changes = normalize_jira_event(
        cloud_id=cloud_id,
        payload=payload,
    )
    if not changes:
        logger.info(
            "[JIRA][WEBHOOK][INGRESS] Ignored payload: cloud_id=%s, event_type=%s",
            cloud_id,
            event_type,
        )
        return {"status": "ignored", "event_type": event_type, "reason": "unsupported_payload"}

    guard_result = filter_record_changes_by_full_sync(db, changes)
    blocked_count = len(guard_result.blocked_changes)
    if blocked_count > 0:
        blocked_targets = guard_result.blocked_targets
        if not guard_result.allowed_changes:
            logger.info(
                "[JIRA][WEBHOOK][INGRESS] Incremental blocked before ingest: cloud_id=%s, source=webhook, blocked_count=%s, blocked_targets=%s",
                cloud_id,
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
            "[JIRA][WEBHOOK][INGRESS] Incremental partially blocked before ingest: cloud_id=%s, source=webhook, allowed_count=%s, blocked_count=%s, blocked_targets=%s",
            cloud_id,
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
    response = {
        "status": "accepted",
        "event_type": event_type,
        "record_keys": record_keys,
    }
    if blocked_count > 0:
        response["blocked_count"] = blocked_count
    return response
