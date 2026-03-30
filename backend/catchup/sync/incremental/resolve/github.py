from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from catchup.db.models import SyncConnector
from catchup.sync.incremental.schemas import RecordChange


def resolve_github_event(
    *,
    event_name: str,
    payload: dict[str, Any],
) -> list[RecordChange]:
    installation_id = _extract_installation_id(payload)
    repository_id = _extract_repository_id(payload)
    if installation_id is None or repository_id is None:
        return []

    record_type, record_id, last_event_at = _resolve_parent_record(event_name, payload)
    if not record_type or not record_id:
        return []

    return [
        RecordChange(
            connector=SyncConnector.GITHUB,
            scope_id=str(installation_id),
            record_type=record_type,
            record_id=record_id,
            parent_type="repository",
            parent_id=str(repository_id),
            event_kind=_resolve_event_kind(event_name, payload),
            last_event_at=last_event_at,
        )
    ]


def _resolve_parent_record(
    event_name: str,
    payload: dict[str, Any],
) -> tuple[str, str, datetime]:
    if event_name == "issues":
        issue = payload.get("issue") or {}
        return (
            "issue",
            str(issue.get("number") or "").strip(),
            _parse_datetime(issue.get("updated_at"))
            or _parse_datetime(issue.get("created_at"))
            or _utc_now(),
        )

    if event_name == "issue_comment":
        issue = payload.get("issue") or {}
        comment = payload.get("comment") or {}
        record_type = "pull_request" if issue.get("pull_request") else "issue"
        return (
            record_type,
            str(issue.get("number") or "").strip(),
            _parse_datetime(comment.get("updated_at"))
            or _parse_datetime(comment.get("created_at"))
            or _parse_datetime(issue.get("updated_at"))
            or _utc_now(),
        )

    if event_name == "pull_request":
        pull_request = payload.get("pull_request") or {}
        return (
            "pull_request",
            str(pull_request.get("number") or "").strip(),
            _parse_datetime(pull_request.get("updated_at"))
            or _parse_datetime(pull_request.get("created_at"))
            or _utc_now(),
        )

    if event_name == "pull_request_review":
        pull_request = payload.get("pull_request") or {}
        review = payload.get("review") or {}
        return (
            "pull_request",
            str(pull_request.get("number") or "").strip(),
            _parse_datetime(review.get("submitted_at"))
            or _parse_datetime(review.get("submittedAt"))
            or _parse_datetime(pull_request.get("updated_at"))
            or _utc_now(),
        )

    if event_name == "pull_request_review_comment":
        pull_request = payload.get("pull_request") or {}
        comment = payload.get("comment") or {}
        return (
            "pull_request",
            str(pull_request.get("number") or "").strip(),
            _parse_datetime(comment.get("updated_at"))
            or _parse_datetime(comment.get("created_at"))
            or _parse_datetime(pull_request.get("updated_at"))
            or _utc_now(),
        )

    if event_name == "pull_request_review_thread":
        pull_request = payload.get("pull_request") or {}
        thread = payload.get("thread") or {}
        return (
            "pull_request",
            str(pull_request.get("number") or "").strip(),
            _parse_datetime(thread.get("updated_at"))
            or _parse_datetime(thread.get("created_at"))
            or _parse_datetime(pull_request.get("updated_at"))
            or _utc_now(),
        )

    return "", "", _utc_now()


def _resolve_event_kind(
    event_name: str,
    payload: dict[str, Any],
) -> str:
    if event_name in {
        "issue_comment",
        "pull_request_review",
        "pull_request_review_comment",
        "pull_request_review_thread",
    }:
        return "updated"

    action = str(payload.get("action") or "").strip().lower()
    if action in {"opened", "reopened"}:
        return "created"
    if action == "deleted":
        return "deleted"
    return "updated"


def _extract_installation_id(payload: dict[str, Any]) -> int | None:
    installation = payload.get("installation") or {}
    raw = installation.get("id")
    if raw in (None, ""):
        return None

    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _extract_repository_id(payload: dict[str, Any]) -> int | None:
    repository = payload.get("repository") or {}
    raw = repository.get("id")
    if raw in (None, ""):
        return None

    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_datetime(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None

    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None
