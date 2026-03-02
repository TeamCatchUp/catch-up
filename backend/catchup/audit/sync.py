from __future__ import annotations

from typing import Any

from catchup.audit.base import (
    AuditLevel,
    build_actor,
    emit_audit_event,
    resolve_audit_level,
)
from catchup.audit.enums import EventType, SyncEventAction


def full_sync(
    *,
    connector: str,
    result: str,
    sync_type: str | None = None,
    trigger: str | None = None,
    resource_type: str | None = None,
    counts: dict[str, int] | None = None,
    duration_ms: int | None = None,
    embedding: dict[str, Any] | None = None,
    error_summary: str | None = None,
    run_id: str | None = None,
    connector_details: dict[str, Any] | None = None,
    sync_details: dict[str, Any] | None = None,
    actor: dict[str, Any] | None = None,
    level: AuditLevel | None = None,
) -> None:
    emit_audit_event(
        event_type=EventType.SYNC,
        event_action=SyncEventAction.FULL_SYNC,
        actor=build_actor(actor=actor),
        metadata={
            "connector": connector,
            "result": result,
            "sync_type": sync_type,
            "trigger": trigger,
            "resource_type": resource_type,
            "counts": counts or {},
            "duration_ms": duration_ms,
            "embedding": embedding or {},
            "error_summary": error_summary,
            "run_id": run_id,
            "connector_details": connector_details or {},
            "sync_details": sync_details or {},
        },
        level=resolve_audit_level(result, level),
    )


def incremental_sync(
    *,
    connector: str,
    result: str,
    trigger: str | None = None,
    resource_type: str | None = None,
    counts: dict[str, int] | None = None,
    duration_ms: int | None = None,
    cursor: str | None = None,
    window_start_utc: str | None = None,
    window_end_utc: str | None = None,
    error_summary: str | None = None,
    run_id: str | None = None,
    connector_details: dict[str, Any] | None = None,
    sync_details: dict[str, Any] | None = None,
    actor: dict[str, Any] | None = None,
    level: AuditLevel | None = None,
) -> None:
    emit_audit_event(
        event_type=EventType.SYNC,
        event_action=SyncEventAction.INCREMENTAL_SYNC,
        actor=build_actor(actor=actor),
        metadata={
            "connector": connector,
            "result": result,
            "trigger": trigger,
            "resource_type": resource_type,
            "counts": counts or {},
            "duration_ms": duration_ms,
            "cursor": cursor,
            "window_start_utc": window_start_utc,
            "window_end_utc": window_end_utc,
            "error_summary": error_summary,
            "run_id": run_id,
            "connector_details": connector_details or {},
            "sync_details": sync_details or {},
        },
        level=resolve_audit_level(result, level),
    )


def sync_failure(
    *,
    connector: str,
    failure_reason: str,
    result: str = "failure",
    error_summary: str | None = None,
    error_code: str | None = None,
    phase: str | None = None,
    retryable: bool | None = None,
    duration_ms: int | None = None,
    run_id: str | None = None,
    connector_details: dict[str, Any] | None = None,
    sync_details: dict[str, Any] | None = None,
    actor: dict[str, Any] | None = None,
    level: AuditLevel | None = None,
) -> None:
    emit_audit_event(
        event_type=EventType.SYNC,
        event_action=SyncEventAction.SYNC_FAILURE,
        actor=build_actor(actor=actor),
        metadata={
            "connector": connector,
            "result": result,
            "failure_reason": failure_reason,
            "error_summary": error_summary,
            "error_code": error_code,
            "phase": phase,
            "retryable": retryable,
            "duration_ms": duration_ms,
            "run_id": run_id,
            "connector_details": connector_details or {},
            "sync_details": sync_details or {},
        },
        level=resolve_audit_level(result, level),
    )


def schema_drift_detected(
    *,
    connector: str,
    resource_type: str,
    diff_summary: dict[str, Any] | str,
    result: str = "partial_failure",
    run_id: str | None = None,
    connector_details: dict[str, Any] | None = None,
    sync_details: dict[str, Any] | None = None,
    actor: dict[str, Any] | None = None,
    level: AuditLevel | None = None,
) -> None:
    emit_audit_event(
        event_type=EventType.SYNC,
        event_action=SyncEventAction.SCHEMA_DRIFT_DETECTED,
        actor=build_actor(actor=actor),
        metadata={
            "connector": connector,
            "resource_type": resource_type,
            "diff_summary": diff_summary,
            "result": result,
            "run_id": run_id,
            "connector_details": connector_details or {},
            "sync_details": sync_details or {},
        },
        level=resolve_audit_level(result, level),
    )


def embedding_batch(
    *,
    model: str,
    result: str,
    vectors_generated: int | None = None,
    batch_size: int | None = None,
    duration_ms: int | None = None,
    connector: str | None = None,
    resource_type: str | None = None,
    failure_reason: str | None = None,
    error_summary: str | None = None,
    run_id: str | None = None,
    embedding_details: dict[str, Any] | None = None,
    sync_details: dict[str, Any] | None = None,
    actor: dict[str, Any] | None = None,
    level: AuditLevel | None = None,
) -> None:
    emit_audit_event(
        event_type=EventType.SYNC,
        event_action=SyncEventAction.EMBEDDING_BATCH,
        actor=build_actor(actor=actor),
        metadata={
            "model": model,
            "result": result,
            "vectors_generated": vectors_generated,
            "batch_size": batch_size,
            "duration_ms": duration_ms,
            "connector": connector,
            "resource_type": resource_type,
            "failure_reason": failure_reason,
            "error_summary": error_summary,
            "run_id": run_id,
            "embedding_details": embedding_details or {},
            "sync_details": sync_details or {},
        },
        level=resolve_audit_level(result, level),
    )
