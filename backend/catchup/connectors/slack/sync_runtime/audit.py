from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from catchup.audit import sync as sync_audit
from catchup.connectors.slack.sync_runtime.constants import (
    CONNECTOR_SLACK,
    RESOURCE_TYPE_CHANNEL,
    SyncFailureReason,
)

def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _build_sync_details(phase: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    details: dict[str, Any] = {
        "phase": phase,
        "event_at_utc": _utc_now_iso(),
    }
    if extra:
        details.update(extra)
    return details

# 1) Full Sync 요청 -> Queue 적재 완료 시 로그
def emit_job_accepted(
    *,
    job_id: str,
    team_id: str,
    total_channels: int,
    queued_channels: int,
    actor: dict[str, Any] | None = None,
) -> None:
    sync_audit.full_sync(
        connector=CONNECTOR_SLACK,
        result="accepted",
        sync_type="full",
        trigger="api",
        resource_type=RESOURCE_TYPE_CHANNEL,
        counts={
            "total_channels": total_channels,
            "queued_channels": queued_channels,
        },
        run_id=job_id,
        connector_details={"team_id": team_id},
        sync_details=_build_sync_details("api_accepted"),
        actor=actor,
    )


def emit_team_lock_conflict(
    *,
    team_id: str,
    requested_job_id: str,
    owner_job_id: str | None = None,
    actor: dict[str, Any] | None = None,
) -> None:
    sync_audit.sync_failure(
        connector=CONNECTOR_SLACK,
        failure_reason=SyncFailureReason.TEAM_LOCK_CONFLICT.value,
        result="failure",
        error_summary="full_sync_already_in_progress_for_team",
        phase="api",
        retryable=True,
        run_id=requested_job_id,
        connector_details={
            "team_id": team_id,
            "owner_job_id": owner_job_id,
        },
        sync_details=_build_sync_details("api_lock_conflict"),
        actor=actor,
    )


# 2) Worker가 이벤트 처리를 시작한 시점
def emit_job_started(
    *,
    job_id: str,
    team_id: str,
    total_channels: int,
    actor: dict[str, Any] | None = None,
) -> None:
    sync_audit.full_sync(
        connector=CONNECTOR_SLACK,
        result="in_progress",
        sync_type="full",
        trigger="worker",
        resource_type=RESOURCE_TYPE_CHANNEL,
        counts={"total_channels": total_channels},
        run_id=job_id,
        connector_details={"team_id": team_id},
        sync_details=_build_sync_details("worker_started"),
        actor=actor,
    )

# 3) 채널 단위 동기화 시작
def emit_channel_started(
    *,
    job_id: str,
    team_id: str,
    channel_id: str,
    channel_name: str,
    attempt: int,
    actor: dict[str, Any] | None = None,
) -> None:
    sync_audit.full_sync(
        connector=CONNECTOR_SLACK,
        result="in_progress",
        sync_type="full",
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
            {"attempt": attempt},
        ),
        actor=actor,
    )

# 4) 채널 락 충돌/백오프로 재큐잉된 경우
def emit_channel_requeued(
    *,
    job_id: str,
    team_id: str,
    channel_id: str,
    channel_name: str,
    attempt: int,
    delay_seconds: float,
    actor: dict[str, Any] | None = None,
) -> None:
    sync_audit.full_sync(
        connector=CONNECTOR_SLACK,
        result="in_progress",
        sync_type="full",
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
            },
        ),
        actor=actor,
    )

# 5) 채널 동기화 완료(성공/skip 포함)
def emit_channel_completed(
    *,
    job_id: str,
    team_id: str,
    channel_id: str,
    channel_name: str,
    synced_count: int,
    error_count: int,
    skipped: bool,
    actor: dict[str, Any] | None = None,
) -> None:
    sync_audit.full_sync(
        connector=CONNECTOR_SLACK,
        result="in_progress",
        sync_type="full",
        trigger="worker",
        resource_type=RESOURCE_TYPE_CHANNEL,
        counts={
            "completed_channels": 1,
            "synced_messages": synced_count,
            "channel_errors": error_count,
            "skipped_channels": 1 if skipped else 0,
        },
        run_id=job_id,
        connector_details={
            "team_id": team_id,
            "channel_id": channel_id,
            "channel_name": channel_name,
        },
        sync_details=_build_sync_details("channel_completed"),
        actor=actor,
    )

# 6) 채널 단위 최종 실패
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
            {"attempt": attempt},
        ),
        actor=actor,
    )

# 7) 전체 job 완료
def emit_job_completed(
    *,
    job_id: str,
    team_id: str,
    total_channels: int,
    completed_channels: int,
    failed_channels: int,
    requeued_channels: int,
    total_synced_messages: int,
    duration_ms: int | None = None,
    actor: dict[str, Any] | None = None,
) -> None:
    sync_audit.full_sync(
        connector=CONNECTOR_SLACK,
        result="success" if failed_channels == 0 else "partial_failure",
        sync_type="full",
        trigger="worker",
        resource_type=RESOURCE_TYPE_CHANNEL,
        counts={
            "total_channels": total_channels,
            "completed_channels": completed_channels,
            "failed_channels": failed_channels,
            "requeued_channels": requeued_channels,
            "synced_messages": total_synced_messages,
        },
        duration_ms=duration_ms,
        run_id=job_id,
        connector_details={"team_id": team_id},
        sync_details=_build_sync_details("job_completed"),
        actor=actor,
    )

# 8) 전체 job 실패
def emit_job_failed(
    *,
    job_id: str,
    team_id: str,
    failure_reason: str,
    error_summary: str | None = None,
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
        sync_details=_build_sync_details("job_failed"),
        actor=actor,
    )

# 9) 임베딩 배치 단계 감사 로그
def emit_embedding_batch(
    *,
    job_id: str,
    team_id: str,
    model: str,
    result: str,
    vectors_generated: int | None = None,
    batch_size: int | None = None,
    duration_ms: int | None = None,
    failure_reason: str | None = None,
    error_summary: str | None = None,
    actor: dict[str, Any] | None = None,
) -> None:
    sync_audit.embedding_batch(
        model=model,
        result=result,
        vectors_generated=vectors_generated,
        batch_size=batch_size,
        duration_ms=duration_ms,
        connector=CONNECTOR_SLACK,
        resource_type="message",
        failure_reason=failure_reason,
        error_summary=error_summary,
        run_id=job_id,
        embedding_details={"team_id": team_id},
        sync_details=_build_sync_details("embedding_batch"),
        actor=actor,
    )
