from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from catchup.connectors.jira import webhook_service
from catchup.sync.incremental import ingest_record_changes, normalize_jira_event

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

    record_keys = ingest_record_changes(db, changes)
    return {
        "status": "accepted",
        "event_type": event_type,
        "record_keys": record_keys,
    }
