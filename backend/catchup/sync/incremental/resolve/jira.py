from __future__ import annotations

from datetime import datetime
from datetime import timezone
from typing import Any

from catchup.connectors.atlassian.utils import parse_atlassian_datetime
from catchup.db.models import SyncConnector
from catchup.sync.incremental.schemas import RecordChange


def resolve_jira_event(
    *,
    cloud_id: str,
    payload: dict[str, Any],
) -> list[RecordChange]:
    event_name = str(payload.get("webhookEvent") or "").strip().lower()
    issue = payload.get("issue") or {}
    issue_fields = issue.get("fields") or {}
    project = issue_fields.get("project") or payload.get("project") or {}

    record_id = str(issue.get("key") or "").strip()
    parent_id = str(project.get("key") or "").strip()
    if not record_id or not parent_id:
        return []

    if event_name == "jira:issue_deleted":
        event_kind = "deleted"
    elif event_name == "jira:issue_created":
        event_kind = "created"
    else:
        event_kind = "updated"
    last_event_at = (
        _parse_datetime((payload.get("comment") or {}).get("updated"))
        or _parse_datetime((payload.get("comment") or {}).get("created"))
        or _parse_datetime(issue_fields.get("updated"))
        or datetime.now(timezone.utc)
    )

    return [
        RecordChange(
            connector=SyncConnector.JIRA,
            scope_id=cloud_id.strip(),
            record_type="issue",
            record_id=record_id,
            parent_type="project",
            parent_id=parent_id,
            event_kind=event_kind,
            last_event_at=last_event_at,
        )
    ]
def _parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    raw = str(value).strip()
    if not raw:
        return None

    parsed = parse_atlassian_datetime(raw)
    if parsed is not None:
        return parsed.astimezone(timezone.utc)

    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None
