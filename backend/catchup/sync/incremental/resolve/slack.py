from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from datetime import timezone

from catchup.db.models import SyncConnector
from catchup.sync.incremental.schemas import RecordChange

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


@dataclass(slots=True, frozen=True)
class SlackResolveResult:
    changes: list[RecordChange]
    reason: str | None = None


@dataclass(slots=True, frozen=True)
class SlackMessageRef:
    record_id: str
    message_ts: str
    is_thread_reply: bool


def resolve_slack_event(
    *,
    team_id: str,
    event: dict[str, object],
) -> SlackResolveResult:
    if str(event.get("type") or "").strip() != "message":
        return SlackResolveResult(changes=[], reason="unsupported_event")

    subtype = str(event.get("subtype") or "").strip().lower()
    channel_id = str(event.get("channel") or "").strip()
    if not channel_id.startswith(("C", "G")):
        return SlackResolveResult(changes=[], reason="unsupported_channel")

    subtype_policy = _classify_message_subtype(subtype)
    if subtype_policy == "ignore":
        return SlackResolveResult(changes=[], reason="ignored_subtype")
    if subtype_policy == "unsupported":
        return SlackResolveResult(changes=[], reason="unsupported_subtype")

    message_payload = _resolve_slack_message_payload(event, subtype)
    if not isinstance(message_payload, dict):
        return SlackResolveResult(changes=[], reason="unsupported_message_payload")

    message_ref = _resolve_slack_message_ref(event, message_payload)
    if not channel_id or not message_ref.record_id:
        return SlackResolveResult(changes=[], reason="unsupported_message_payload")

    event_kind = _resolve_slack_event_kind(subtype, message_ref)
    last_event_at = _parse_slack_ts(
        str(event.get("event_ts") or message_ref.message_ts or message_ref.record_id)
    ) or datetime.now(timezone.utc)

    return SlackResolveResult(
        changes=[
            RecordChange(
                connector=SyncConnector.SLACK,
                scope_id=team_id.strip(),
                record_type="message",
                record_id=message_ref.record_id,
                parent_type="channel",
                parent_id=channel_id,
                event_kind=event_kind,
                last_event_at=last_event_at,
            )
        ]
    )


def _classify_message_subtype(subtype: str) -> str:
    if subtype in IGNORED_MESSAGE_SUBTYPES:
        return "ignore"
    if subtype in INCREMENTAL_MESSAGE_SUBTYPES:
        return "incremental"
    return "unsupported"

def _resolve_slack_message_payload(
    event: dict[str, object],
    subtype: str,
) -> dict[str, object]:
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


def _resolve_slack_message_ref(
    event: dict[str, object],
    message_payload: dict[str, object],
) -> SlackMessageRef:
    message_ts = str(
        message_payload.get("ts")
        or event.get("deleted_ts")
        or event.get("ts")
        or ""
    ).strip()
    thread_ts = str(message_payload.get("thread_ts") or "").strip()
    is_thread_reply = bool(thread_ts) and thread_ts != message_ts

    return SlackMessageRef(
        record_id=thread_ts or message_ts,
        message_ts=message_ts,
        is_thread_reply=is_thread_reply,
    )


def _resolve_slack_event_kind(
    subtype: str,
    message_ref: SlackMessageRef,
) -> str:
    if subtype == "message_deleted":
        return "updated" if message_ref.is_thread_reply else "deleted"
    if subtype == "message_changed":
        return "updated"
    if message_ref.is_thread_reply:
        return "updated"
    return "created"


def _parse_slack_ts(value: str) -> datetime | None:
    normalized = value.strip()
    if not normalized:
        return None
    try:
        return datetime.fromtimestamp(float(normalized), tz=timezone.utc)
    except (TypeError, ValueError):
        return None
