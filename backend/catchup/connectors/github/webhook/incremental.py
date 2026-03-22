from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi.concurrency import run_in_threadpool

from catchup.audit.enums import AuditEventStatus, AuditLevel
from catchup.db.engine import SessionLocal
from catchup.db.models import SyncConnector
from catchup.events.enums import SyncTriggerEventAction
from catchup.sync.audit import SyncAuditContext, emit_sync_trigger_audit
from catchup.sync.incremental import ingest_record_changes
from catchup.sync.incremental.full_sync_guard import filter_record_changes_by_full_sync
from catchup.sync.incremental.schemas import RecordChange

from .responses import accepted_incremental_response, ignored_event_response

logger = logging.getLogger(__name__)


async def handle_incremental_event(
    *,
    event_name: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    def _sync_task() -> dict[str, Any]:
        changes = _build_incremental_changes(
            event_name=event_name,
            payload=payload,
        )
        if not changes:
            return ignored_event_response(
                event=event_name,
                reason="unsupported_payload",
            )

        with SessionLocal() as db:
            guard_result = filter_record_changes_by_full_sync(db, changes)
            blocked_count = len(guard_result.blocked_changes)
            if blocked_count > 0:
                blocked_targets = guard_result.blocked_targets
                if not guard_result.allowed_changes:
                    logger.info(
                        "[GITHUB][WEBHOOK][INGRESS] Incremental blocked before ingest: installation_id=%s, source=webhook, blocked_count=%s, blocked_targets=%s",
                        changes[0].scope_id,
                        blocked_count,
                        [
                            f"{target.target_type}:{target.target_id}"
                            for target in blocked_targets
                        ],
                    )
                    return ignored_event_response(
                        event=event_name,
                        reason="full_sync_required",
                        blocked_count=blocked_count,
                    )

                logger.info(
                    "[GITHUB][WEBHOOK][INGRESS] Incremental partially blocked before ingest: installation_id=%s, source=webhook, allowed_count=%s, blocked_count=%s, blocked_targets=%s",
                    changes[0].scope_id,
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
                        f"stage=record_change_ingest,event_name={event_name},"
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
                            f"stage=record_change_ingest_failed,event_name={event_name},"
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
                        f"stage=record_change_ingested,event_name={event_name},"
                        f"record_key_count={len(record_keys)},blocked_count={blocked_count}"
                    ),
                )

        return accepted_incremental_response(
            event=event_name,
            record_keys=record_keys,
            blocked_count=blocked_count,
        )

    return await run_in_threadpool(_sync_task)


def _build_incremental_changes(
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
