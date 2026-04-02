from __future__ import annotations

from catchup.sync.common.schemas import SyncStreamTask


def task_fields(task: SyncStreamTask) -> dict[str, str]:
    return task.to_stream_fields()


def task_lock_key(task: SyncStreamTask) -> tuple[str, str, str, str]:
    target_type = (
        (task.target_type or "").strip()
        or ("record" if task.record_key else "event")
    )
    target_id = (
        (task.target_id or "").strip()
        or (task.record_key or "").strip()
        or task.event_id
    )
    return(
        task.connector.strip(),
        (task.scope_id or "").strip(),
        target_type,
        target_id,
    )