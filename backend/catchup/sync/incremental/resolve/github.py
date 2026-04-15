from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from datetime import timezone
from typing import Any

from catchup.db.models import SyncConnector
from catchup.sync.incremental.schemas import RecordChange


@dataclass(slots=True, frozen=True)
class GithubScope:
    installation_id: str
    repository_id: str


@dataclass(slots=True, frozen=True)
class GithubRecord:
    record_type: str
    record_id: str
    last_event_at: datetime


type GithubEventResolver = Callable[[dict[str, Any]], GithubRecord | None]

UPDATED_ONLY_EVENTS = frozenset({
    "issue_comment",
    "pull_request_review",
    "pull_request_review_comment",
    "pull_request_review_thread",
})


def resolve_github_event(
    *,
    event_name: str,
    payload: dict[str, Any],
) -> list[RecordChange]:
    scope = _resolve_scope(payload)
    if scope is None:
        return []

    resolver = GITHUB_EVENT_RESOLVERS.get(event_name)
    if resolver is None:
        return []

    record = resolver(payload)
    if record is None:
        return []

    return [
        RecordChange(
            connector=SyncConnector.GITHUB,
            scope_id=scope.installation_id,
            record_type=record.record_type,
            record_id=record.record_id,
            parent_type="repository",
            parent_id=scope.repository_id,
            event_kind=_resolve_event_kind(event_name, payload),
            last_event_at=record.last_event_at,
        )
    ]


def _resolve_scope(payload: dict[str, Any]) -> GithubScope | None:
    installation_id = _extract_int(payload.get("installation"), "id")
    repository_id = _extract_int(payload.get("repository"), "id")
    if installation_id is None or repository_id is None:
        return None

    return GithubScope(
        installation_id=str(installation_id),
        repository_id=str(repository_id),
    )
def _resolve_issue(payload: dict[str, Any]) -> GithubRecord | None:
    issue = payload.get("issue") or {}
    record_id = _extract_number(issue, "number")
    if not record_id:
        return None

    return GithubRecord(
        record_type="issue",
        record_id=record_id,
        last_event_at=_first_datetime(
            issue.get("updated_at"),
            issue.get("created_at"),
        ),
    )


def _resolve_issue_comment(payload: dict[str, Any]) -> GithubRecord | None:
    issue = payload.get("issue") or {}
    comment = payload.get("comment") or {}
    record_id = _extract_number(issue, "number")
    if not record_id:
        return None

    return GithubRecord(
        record_type="pull_request" if issue.get("pull_request") else "issue",
        record_id=record_id,
        last_event_at=_first_datetime(
            comment.get("updated_at"),
            comment.get("created_at"),
            issue.get("updated_at"),
        ),
    )


def _resolve_pull_request(payload: dict[str, Any]) -> GithubRecord | None:
    return _resolve_pull_request_record(
        payload,
        "pull_request",
        "updated_at",
        "created_at",
    )


def _resolve_pull_request_review(payload: dict[str, Any]) -> GithubRecord | None:
    return _resolve_pull_request_record(
        payload,
        "review",
        "submitted_at",
        "submittedAt",
        "updated_at",
    )


def _resolve_pull_request_review_comment(payload: dict[str, Any]) -> GithubRecord | None:
    return _resolve_pull_request_record(
        payload,
        "comment",
        "updated_at",
        "created_at",
        "updated_at",
    )


def _resolve_pull_request_review_thread(payload: dict[str, Any]) -> GithubRecord | None:
    return _resolve_pull_request_record(
        payload,
        "thread",
        "updated_at",
        "created_at",
        "updated_at",
    )


def _resolve_pull_request_record(
    payload: dict[str, Any],
    event_node_key: str,
    *timestamp_keys: str,
) -> GithubRecord | None:
    pull_request = payload.get("pull_request") or {}
    record_id = _extract_number(pull_request, "number")
    if not record_id:
        return None

    event_node = payload.get(event_node_key) or {}

    return GithubRecord(
        record_type="pull_request",
        record_id=record_id,
        last_event_at=_first_datetime(
            *[event_node.get(key) for key in timestamp_keys],
            pull_request.get("updated_at"),
        ),
    )


GITHUB_EVENT_RESOLVERS: dict[str, GithubEventResolver] = {
    "issues": _resolve_issue,
    "issue_comment": _resolve_issue_comment,
    "pull_request": _resolve_pull_request,
    "pull_request_review": _resolve_pull_request_review,
    "pull_request_review_comment": _resolve_pull_request_review_comment,
    "pull_request_review_thread": _resolve_pull_request_review_thread,
}


def _resolve_event_kind(
    event_name: str,
    payload: dict[str, Any],
) -> str:
    if event_name in UPDATED_ONLY_EVENTS:
        return "updated"

    action = str(payload.get("action") or "").strip().lower()
    if action in {"opened", "reopened"}:
        return "created"
    if action == "deleted":
        return "deleted"
    return "updated"


def _extract_int(node: Any, key: str) -> int | None:
    if not isinstance(node, dict):
        return None

    raw = node.get(key)
    if raw in (None, ""):
        return None

    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _extract_number(node: Any, key: str) -> str:
    if not isinstance(node, dict):
        return ""
    return str(node.get(key) or "").strip()


def _first_datetime(*values: Any) -> datetime:
    for value in values:
        parsed = _parse_datetime(value)
        if parsed is not None:
            return parsed
    return datetime.now(timezone.utc)


def _parse_datetime(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None

    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None
