from __future__ import annotations

from collections.abc import Sequence

from catchup.db.models import SyncEvent
from catchup.sync.common.schemas import SyncStreamTask


def _normalize_sync_from_ts(metadata: dict[str, object]) -> str | None:
    raw = metadata.get("sync_from_ts")
    if raw is None:
        return None

    value = str(raw).strip()
    return value or None


def _normalize_iso_datetime(value: object) -> str | None:
    if value is None:
        return None
    return str(value).strip() or None


def _normalize_chunk_int(value: object) -> int | None:
    if value is None:
        return None
    return int(value)

def _resolve_stage(
    *,
    event: SyncEvent,
    metadata: dict[str, object],
) -> str:
    if event.stage is not None:
        value = str(event.stage).strip()
        if value:
            return value
    
    raw = metadata.get("stage")
    if raw is not None:
        value = str(raw).strip()
        if value:
            return value
        
    raise ValueError(f"stage is missing for event: {event.event_id}")


def build_stream_task_from_persisted_event(
    *,
    event: SyncEvent,
    fallback_scope_id: str | None = None,
) -> SyncStreamTask:
    metadata = event.resource_metadata if isinstance(event.resource_metadata, dict) else {}
    scope_id = str(metadata.get("scope_id") or fallback_scope_id or "").strip()
    if not scope_id:
        raise ValueError(f"scope_id is missing for event: {event.event_id}")

    target_type = str(event.resource_type).strip()
    target_id = str(event.resource_id).strip()
    if not target_type or not target_id:
        raise ValueError(f"target identity is invalid for event: {event.event_id}")
    
    stage = _resolve_stage(event=event, metadata=metadata)

    return SyncStreamTask.full(
        event_id=event.event_id,
        job_id=event.job_id,
        connector=event.connector,
        scope_id=scope_id,
        target_type=target_type,
        target_id=target_id,
        stage=stage,
        sync_from_ts=_normalize_sync_from_ts(metadata),
        range_start=_normalize_iso_datetime(event.range_start or metadata.get("range_start")),
        range_end=_normalize_iso_datetime(event.range_end or metadata.get("range_end")),
        chunk_index=_normalize_chunk_int(event.chunk_index or metadata.get("chunk_index")),
        chunk_total=_normalize_chunk_int(event.chunk_total or metadata.get("chunk_total")),
        attempt=max(0, int(event.attempt)),
        max_attempts=max(1, int(event.max_attempts)),
    )


def build_stream_tasks_from_persisted_events(
    *,
    events: Sequence[SyncEvent],
    fallback_scope_id: str | None = None,
) -> list[SyncStreamTask]:
    return [
        build_stream_task_from_persisted_event(
            event=event,
            fallback_scope_id=fallback_scope_id,
        )
        for event in events
    ]
