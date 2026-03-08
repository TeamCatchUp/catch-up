from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from catchup.audit import sync as audit_sync
from catchup.db.models import SyncConnector, SyncType


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _connector_key(connector: SyncConnector | str) -> str:
    if isinstance(connector, SyncConnector):
        return connector.value
    return str(connector)


def _sync_type_value(sync_type: SyncType | str) -> str:
    if isinstance(sync_type, SyncType):
        return sync_type.value
    return str(sync_type)


def _build_connector_details(
    *,
    scope_id: str,
    connector_details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    details: dict[str, Any] = {"scope_id": scope_id}
    if connector_details:
        details.update(connector_details)
    return details


def _build_sync_details(
    *,
    phase: str,
    sync_type: str,
    sync_details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    details: dict[str, Any] = {
        "phase": phase,
        "sync_type": sync_type,
        "event_at_utc": _utc_now_iso(),
    }
    if sync_details:
        details.update(sync_details)
    return details


def _emit_worker_lifecycle(
    *,
    connector: SyncConnector | str,
    sync_type: SyncType | str,
    result: str,
    run_id: str,
    scope_id: str,
    resource_type: str,
    counts: dict[str, int],
    phase: str,
    connector_details: dict[str, Any] | None = None,
    sync_details: dict[str, Any] | None = None,
    actor: dict[str, Any] | None = None,
    duration_ms: int | None = None,
) -> None:
    connector_key = _connector_key(connector)
    sync_type_value = _sync_type_value(sync_type)

    normalized_connector_details = _build_connector_details(
        scope_id=scope_id,
        connector_details=connector_details,
    )
    normalized_sync_details = _build_sync_details(
        phase=phase,
        sync_type=sync_type_value,
        sync_details=sync_details,
    )

    if sync_type_value == SyncType.INCREMENTAL.value:
        audit_sync.incremental_sync(
            connector=connector_key,
            result=result,
            trigger="worker",
            resource_type=resource_type,
            counts=counts,
            duration_ms=duration_ms,
            run_id=run_id,
            connector_details=normalized_connector_details,
            sync_details=normalized_sync_details,
            actor=actor,
        )
        return

    audit_sync.full_sync(
        connector=connector_key,
        result=result,
        sync_type=sync_type_value,
        trigger="worker",
        resource_type=resource_type,
        counts=counts,
        duration_ms=duration_ms,
        run_id=run_id,
        connector_details=normalized_connector_details,
        sync_details=normalized_sync_details,
        actor=actor,
    )


def emit_sync_dispatch_accepted(
    *,
    connector: SyncConnector,
    sync_type: SyncType,
    trigger: str,
    run_id: str,
    scope_id: str,
    counts: dict[str, int],
    scope_metadata: dict[str, Any] | None = None,
    actor: dict[str, Any] | None = None,
) -> None:
    connector_key = connector.value
    sync_type_value = sync_type.value
    connector_details = {"scope_id": scope_id, **dict(scope_metadata or {})}
    sync_details = {
        "phase": "api_accepted",
        "sync_type": sync_type_value,
        "event_at_utc": _utc_now_iso(),
    }

    if sync_type == SyncType.INCREMENTAL:
        audit_sync.incremental_sync(
            connector=connector_key,
            result="accepted",
            trigger=trigger,
            resource_type="resource",
            counts=counts,
            run_id=run_id,
            connector_details=connector_details,
            sync_details=sync_details,
            actor=actor,
        )
        return

    audit_sync.full_sync(
        connector=connector_key,
        result="accepted",
        sync_type=sync_type_value,
        trigger=trigger,
        resource_type="resource",
        counts=counts,
        run_id=run_id,
        connector_details=connector_details,
        sync_details=sync_details,
        actor=actor,
    )


def emit_worker_job_started(
    *,
    connector: SyncConnector | str,
    sync_type: SyncType | str,
    run_id: str,
    scope_id: str,
    total_targets: int,
    connector_details: dict[str, Any] | None = None,
    actor: dict[str, Any] | None = None,
) -> None:
    _emit_worker_lifecycle(
        connector=connector,
        sync_type=sync_type,
        result="in_progress",
        run_id=run_id,
        scope_id=scope_id,
        resource_type="resource",
        counts={"total_targets": total_targets},
        phase="worker_started",
        connector_details=connector_details,
        actor=actor,
    )


def emit_worker_target_started(
    *,
    connector: SyncConnector | str,
    sync_type: SyncType | str,
    run_id: str,
    scope_id: str,
    target_type: str,
    target_id: str,
    target_name: str,
    attempt: int,
    connector_details: dict[str, Any] | None = None,
    actor: dict[str, Any] | None = None,
) -> None:
    details = {
        "target_type": target_type,
        "target_id": target_id,
        "target_name": target_name,
    }
    if connector_details:
        details.update(connector_details)

    _emit_worker_lifecycle(
        connector=connector,
        sync_type=sync_type,
        result="in_progress",
        run_id=run_id,
        scope_id=scope_id,
        resource_type=target_type,
        counts={"started_targets": 1},
        phase="target_started",
        connector_details=details,
        sync_details={"attempt": attempt},
        actor=actor,
    )


def emit_worker_target_completed(
    *,
    connector: SyncConnector | str,
    sync_type: SyncType | str,
    run_id: str,
    scope_id: str,
    target_type: str,
    target_id: str,
    target_name: str,
    synced_count: int,
    error_count: int,
    skipped: bool,
    connector_details: dict[str, Any] | None = None,
    actor: dict[str, Any] | None = None,
) -> None:
    details = {
        "target_type": target_type,
        "target_id": target_id,
        "target_name": target_name,
    }
    if connector_details:
        details.update(connector_details)

    _emit_worker_lifecycle(
        connector=connector,
        sync_type=sync_type,
        result="in_progress",
        run_id=run_id,
        scope_id=scope_id,
        resource_type=target_type,
        counts={
            "completed_targets": 1,
            "synced_records": synced_count,
            "error_records": error_count,
            "skipped_targets": 1 if skipped else 0,
        },
        phase="target_completed",
        connector_details=details,
        actor=actor,
    )


def emit_worker_target_requeued(
    *,
    connector: SyncConnector | str,
    sync_type: SyncType | str,
    run_id: str,
    scope_id: str,
    target_type: str,
    target_id: str,
    target_name: str,
    next_attempt: int,
    error_summary: str | None = None,
    connector_details: dict[str, Any] | None = None,
    actor: dict[str, Any] | None = None,
) -> None:
    details = {
        "target_type": target_type,
        "target_id": target_id,
        "target_name": target_name,
    }
    if connector_details:
        details.update(connector_details)

    _emit_worker_lifecycle(
        connector=connector,
        sync_type=sync_type,
        result="in_progress",
        run_id=run_id,
        scope_id=scope_id,
        resource_type=target_type,
        counts={"requeued_targets": 1},
        phase="target_requeued",
        connector_details=details,
        sync_details={
            "next_attempt": next_attempt,
            "error_summary": error_summary,
        },
        actor=actor,
    )


def emit_worker_target_failed(
    *,
    connector: SyncConnector | str,
    sync_type: SyncType | str,
    run_id: str,
    scope_id: str,
    target_type: str,
    target_id: str,
    target_name: str,
    failure_reason: str,
    error_summary: str | None = None,
    attempt: int | None = None,
    retryable: bool | None = None,
    connector_details: dict[str, Any] | None = None,
    actor: dict[str, Any] | None = None,
) -> None:
    details = {
        "scope_id": scope_id,
        "target_type": target_type,
        "target_id": target_id,
        "target_name": target_name,
    }
    if connector_details:
        details.update(connector_details)

    sync_details = {
        "phase": "target_failed",
        "sync_type": _sync_type_value(sync_type),
        "event_at_utc": _utc_now_iso(),
        "attempt": attempt,
    }

    audit_sync.sync_failure(
        connector=_connector_key(connector),
        failure_reason=failure_reason,
        result="failure",
        error_summary=error_summary,
        phase="target",
        retryable=retryable,
        run_id=run_id,
        connector_details=details,
        sync_details=sync_details,
        actor=actor,
    )


def emit_worker_job_completed(
    *,
    connector: SyncConnector | str,
    sync_type: SyncType | str,
    run_id: str,
    scope_id: str,
    total_targets: int,
    completed_targets: int,
    failed_targets: int,
    requeued_targets: int,
    synced_records: int = 0,
    duration_ms: int | None = None,
    connector_details: dict[str, Any] | None = None,
    actor: dict[str, Any] | None = None,
) -> None:
    result = "success" if failed_targets == 0 else "partial_failure"

    _emit_worker_lifecycle(
        connector=connector,
        sync_type=sync_type,
        result=result,
        run_id=run_id,
        scope_id=scope_id,
        resource_type="resource",
        counts={
            "total_targets": total_targets,
            "completed_targets": completed_targets,
            "failed_targets": failed_targets,
            "requeued_targets": requeued_targets,
            "synced_records": synced_records,
        },
        phase="job_completed",
        connector_details=connector_details,
        actor=actor,
        duration_ms=duration_ms,
    )


def emit_worker_job_failed(
    *,
    connector: SyncConnector | str,
    sync_type: SyncType | str,
    run_id: str,
    scope_id: str,
    failure_reason: str,
    error_summary: str | None = None,
    duration_ms: int | None = None,
    connector_details: dict[str, Any] | None = None,
    actor: dict[str, Any] | None = None,
) -> None:
    details = _build_connector_details(
        scope_id=scope_id,
        connector_details=connector_details,
    )
    sync_details = _build_sync_details(
        phase="job_failed",
        sync_type=_sync_type_value(sync_type),
    )

    audit_sync.sync_failure(
        connector=_connector_key(connector),
        failure_reason=failure_reason,
        result="failure",
        error_summary=error_summary,
        phase="job",
        duration_ms=duration_ms,
        run_id=run_id,
        connector_details=details,
        sync_details=sync_details,
        actor=actor,
    )
