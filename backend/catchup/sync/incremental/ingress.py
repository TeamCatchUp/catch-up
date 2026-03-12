from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from catchup.connectors.atlassian.utils import parse_atlassian_datetime
from catchup.db.incremental import upsert_record_change
from catchup.db.models import SyncConnector
from catchup.sync.incremental.schemas import RecordChange


def ingest_record_changes(
    db: Session,
    changes: list[RecordChange],
) -> list[str]:
    record_keys: list[str] = []
    for change in changes:
        state = upsert_record_change(db, change.to_input())
        record_keys.append(state.record_key)
    return record_keys


def normalize_github_event(
    *,
    event_name: str,
    payload: dict[str, Any],
) -> list[RecordChange]:
    installation = payload.get("installation") or {}
    repository = payload.get("repository") or {}
    resource = payload.get("issue") or payload.get("pull_request") or {}

    scope_id = str(installation.get("id") or "").strip()
    parent_id = str(repository.get("id") or "").strip()
    record_id = str(resource.get("number") or "").strip()
    if not scope_id or not parent_id or not record_id:
        return []

    record_type = "issue" if event_name == "issues" else "pull_request"
    action = str(payload.get("action") or "").strip().lower()
    if action in {"opened", "reopened"}:
        event_kind = "created"
    elif action == "deleted":
        event_kind = "deleted"
    else:
        event_kind = "updated"

    updated_at = _parse_datetime(resource.get("updated_at")) or _utc_now()
    return [
        RecordChange(
            connector=SyncConnector.GITHUB,
            scope_id=scope_id,
            record_type=record_type,
            record_id=record_id,
            parent_type="repository",
            parent_id=parent_id,
            event_kind=event_kind,
            last_event_at=updated_at,
        )
    ]


def normalize_jira_event(
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
        or _utc_now()
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


def normalize_slack_event(
    *,
    team_id: str,
    event: dict[str, Any],
) -> list[RecordChange]:
    if str(event.get("type") or "").strip() != "message":
        return []

    subtype = str(event.get("subtype") or "").strip().lower()
    channel_id = str(event.get("channel") or "").strip()

    # Public/Private channel만 허용하고 DM 계열은 제외한다.
    if not channel_id.startswith(("C", "G")):
        return []

    message_payload = _resolve_slack_message_payload(event, subtype)
    if not isinstance(message_payload, dict):
        return []

    record_id = _resolve_slack_record_id(event, message_payload)
    if not channel_id or not record_id:
        return []

    event_kind = _resolve_slack_event_kind(subtype, event, message_payload)
    last_event_at = _parse_slack_ts(
        str(event.get("event_ts") or message_payload.get("ts") or record_id)
    ) or _utc_now()

    return [
        RecordChange(
            connector=SyncConnector.SLACK,
            scope_id=team_id.strip(),
            record_type="message",
            record_id=record_id,
            parent_type="channel",
            parent_id=channel_id,
            event_kind=event_kind,
            last_event_at=last_event_at,
        )
    ]

def _resolve_slack_message_payload(
    event: dict[str, Any],
    subtype: str,
) -> dict[str, Any]:
    if subtype == "message_deleted":
        previous_message = event.get("previous_message")
        if isinstance(previous_message, dict):
            return previous_message

        message = event.get("message")
        if isinstance(message, dict):
            return message

    if subtype == "message_changed":
        message = event.get("message")
        if isinstance(message, dict):
            return message

    return event


def _resolve_slack_record_id(
    event: dict[str, Any],
    message_payload: dict[str, Any],
) -> str:
    message_ts = str(
        message_payload.get("ts")
        or event.get("deleted_ts")
        or event.get("ts")
        or ""
    ).strip()
    thread_ts = str(message_payload.get("thread_ts") or "").strip()

    return thread_ts or message_ts


def _resolve_slack_event_kind(
    subtype: str,
    event: dict[str, Any],
    message_payload: dict[str, Any],
) -> str:
    message_ts = str(
        message_payload.get("ts")
        or event.get("deleted_ts")
        or event.get("ts")
        or ""
    ).strip()
    thread_ts = str(message_payload.get("thread_ts") or "").strip()
    is_thread_reply = bool(thread_ts) and thread_ts != message_ts

    if subtype == "message_deleted":
        return "updated" if is_thread_reply else "deleted"

    if subtype == "message_changed":
        return "updated"

    if is_thread_reply:
        return "updated"

    return "created"


def build_confluence_record_change(
    *,
    cloud_id: str,
    space_key: str,
    record_type: str,
    record_id: str,
    last_event_at: datetime,
) -> RecordChange:
    return RecordChange(
        connector=SyncConnector.CONFLUENCE,
        scope_id=cloud_id.strip(),
        record_type=record_type.strip(),
        record_id=record_id.strip(),
        parent_type="space",
        parent_id=space_key.strip(),
        event_kind="updated",
        last_event_at=last_event_at,
    )


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


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


def _parse_slack_ts(value: str) -> datetime | None:
    normalized = value.strip()
    if not normalized:
        return None
    try:
        return datetime.fromtimestamp(float(normalized), tz=timezone.utc)
    except (TypeError, ValueError):
        return None
