from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Final

from catchup.audit import sync as sync_audit

CONNECTOR_SLACK: Final[str] = "slack"
RESOURCE_TYPE_CHANNEL: Final[str] = "channel"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _build_sync_details(
    phase: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    details: dict[str, Any] = {
        "phase": phase,
        "event_at_utc": _utc_now_iso(),
    }
    if extra:
        details.update(extra)
    return details


def _emit_sync_lifecycle(
    *,
    sync_type: str,
    result: str,
    trigger: str | None,
    resource_type: str,
    counts: dict[str, int],
    run_id: str,
    connector_details: dict[str, Any],
    sync_details: dict[str, Any],
    duration_ms: int | None = None,
    actor: dict[str, Any] | None = None,
) -> None:
    if sync_type == "incremental":
        sync_audit.incremental_sync(
            connector=CONNECTOR_SLACK,
            result=result,
            trigger=trigger,
            resource_type=resource_type,
            counts=counts,
            duration_ms=duration_ms,
            run_id=run_id,
            connector_details=connector_details,
            sync_details=sync_details,
            actor=actor,
        )
        return

    sync_audit.full_sync(
        connector=CONNECTOR_SLACK,
        result=result,
        sync_type=sync_type,
        trigger=trigger,
        resource_type=resource_type,
        counts=counts,
        duration_ms=duration_ms,
        run_id=run_id,
        connector_details=connector_details,
        sync_details=sync_details,
        actor=actor,
    )


def emit_job_accepted(
    *,
    job_id: str,
    team_id: str,
    total_channels: int,
    queued_channels: int,
    sync_type: str = "full",
    dropped_channels: int = 0,
    dropped_events: int = 0,
    trigger: str = "api",
    actor: dict[str, Any] | None = None,
) -> None:
    _emit_sync_lifecycle(
        sync_type=sync_type,
        result="accepted",
        trigger=trigger,
        resource_type=RESOURCE_TYPE_CHANNEL,
        counts={
            "total_channels": total_channels,
            "queued_channels": queued_channels,
            "dropped_channels": dropped_channels,
            "dropped_events": dropped_events,
        },
        run_id=job_id,
        connector_details={"team_id": team_id},
        sync_details=_build_sync_details("api_accepted", {"sync_type": sync_type}),
        actor=actor,
    )


def emit_job_started(
    *,
    job_id: str,
    team_id: str,
    total_channels: int,
    sync_type: str = "full",
    actor: dict[str, Any] | None = None,
) -> None:
    _emit_sync_lifecycle(
        sync_type=sync_type,
        result="in_progress",
        trigger="worker",
        resource_type=RESOURCE_TYPE_CHANNEL,
        counts={"total_channels": total_channels},
        run_id=job_id,
        connector_details={"team_id": team_id},
        sync_details=_build_sync_details("worker_started", {"sync_type": sync_type}),
        actor=actor,
    )


def emit_channel_started(
    *,
    job_id: str,
    team_id: str,
    channel_id: str,
    channel_name: str,
    attempt: int,
    sync_type: str = "full",
    actor: dict[str, Any] | None = None,
) -> None:
    _emit_sync_lifecycle(
        sync_type=sync_type,
        result="in_progress",
        trigger="worker",
        resource_type=RESOURCE_TYPE_CHANNEL,
        counts={"started_channels": 1},
        run_id=job_id,
        connector_details={
            "team_id": team_id,
            "channel_id": channel_id,
            "channel_name": channel_name,
        },
        sync_details=_build_sync_details(
            "channel_started",
            {"attempt": attempt, "sync_type": sync_type},
        ),
        actor=actor,
    )


def emit_channel_requeued(
    *,
    job_id: str,
    team_id: str,
    channel_id: str,
    channel_name: str,
    attempt: int,
    delay_seconds: float,
    sync_type: str = "full",
    actor: dict[str, Any] | None = None,
) -> None:
    _emit_sync_lifecycle(
        sync_type=sync_type,
        result="in_progress",
        trigger="worker",
        resource_type=RESOURCE_TYPE_CHANNEL,
        counts={"requeued_channels": 1},
        run_id=job_id,
        connector_details={
            "team_id": team_id,
            "channel_id": channel_id,
            "channel_name": channel_name,
        },
        sync_details=_build_sync_details(
            "channel_requeued",
            {
                "attempt": attempt,
                "delay_seconds": delay_seconds,
                "sync_type": sync_type,
            },
        ),
        actor=actor,
    )


def emit_channel_completed(
    *,
    job_id: str,
    team_id: str,
    channel_id: str,
    channel_name: str,
    synced_count: int,
    error_count: int,
    skipped: bool,
    sync_type: str = "full",
    flushed_events: int | None = None,
    actor: dict[str, Any] | None = None,
) -> None:
    counts = {
        "completed_channels": 1,
        "synced_messages": synced_count,
        "channel_errors": error_count,
        "skipped_channels": 1 if skipped else 0,
    }
    if flushed_events is not None:
        counts["flushed_events"] = flushed_events

    _emit_sync_lifecycle(
        sync_type=sync_type,
        result="in_progress",
        trigger="worker",
        resource_type=RESOURCE_TYPE_CHANNEL,
        counts=counts,
        run_id=job_id,
        connector_details={
            "team_id": team_id,
            "channel_id": channel_id,
            "channel_name": channel_name,
        },
        sync_details=_build_sync_details("channel_completed", {"sync_type": sync_type}),
        actor=actor,
    )


def emit_channel_failed(
    *,
    job_id: str,
    team_id: str,
    channel_id: str,
    channel_name: str,
    failure_reason: str,
    error_summary: str | None = None,
    attempt: int | None = None,
    retryable: bool | None = None,
    sync_type: str = "full",
    actor: dict[str, Any] | None = None,
) -> None:
    sync_audit.sync_failure(
        connector=CONNECTOR_SLACK,
        failure_reason=failure_reason,
        result="failure",
        error_summary=error_summary,
        phase="channel",
        retryable=retryable,
        run_id=job_id,
        connector_details={
            "team_id": team_id,
            "channel_id": channel_id,
            "channel_name": channel_name,
        },
        sync_details=_build_sync_details(
            "channel_failed",
            {"attempt": attempt, "sync_type": sync_type},
        ),
        actor=actor,
    )


def emit_job_completed(
    *,
    job_id: str,
    team_id: str,
    total_channels: int,
    completed_channels: int,
    failed_channels: int,
    requeued_channels: int,
    total_synced_messages: int,
    sync_type: str = "full",
    flushed_events: int = 0,
    dropped_events: int = 0,
    duration_ms: int | None = None,
    actor: dict[str, Any] | None = None,
) -> None:
    _emit_sync_lifecycle(
        sync_type=sync_type,
        result="success" if failed_channels == 0 else "partial_failure",
        trigger="worker",
        resource_type=RESOURCE_TYPE_CHANNEL,
        counts={
            "total_channels": total_channels,
            "completed_channels": completed_channels,
            "failed_channels": failed_channels,
            "requeued_channels": requeued_channels,
            "synced_messages": total_synced_messages,
            "flushed_events": flushed_events,
            "dropped_events": dropped_events,
        },
        duration_ms=duration_ms,
        run_id=job_id,
        connector_details={"team_id": team_id},
        sync_details=_build_sync_details("job_completed", {"sync_type": sync_type}),
        actor=actor,
    )


def emit_job_failed(
    *,
    job_id: str,
    team_id: str,
    failure_reason: str,
    error_summary: str | None = None,
    sync_type: str = "full",
    duration_ms: int | None = None,
    actor: dict[str, Any] | None = None,
) -> None:
    sync_audit.sync_failure(
        connector=CONNECTOR_SLACK,
        failure_reason=failure_reason,
        result="failure",
        error_summary=error_summary,
        phase="job",
        duration_ms=duration_ms,
        run_id=job_id,
        connector_details={"team_id": team_id},
        sync_details=_build_sync_details("job_failed", {"sync_type": sync_type}),
        actor=actor,
    )
