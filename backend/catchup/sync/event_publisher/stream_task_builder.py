from __future__ import annotations

from catchup.db.models import SyncConnector, SyncType
from catchup.sync.common.schemas import SyncEventSeed, SyncStreamTask


def build_stream_tasks_from_event_ids(
    *,
    event_ids: list[str],
    job_id: str,
    connector: SyncConnector,
    sync_type: SyncType,
    scope_id: str,
    event_seeds: list[SyncEventSeed],
) -> list[SyncStreamTask]:
    seed_by_event_id = {seed.event_id: seed for seed in event_seeds}
    tasks: list[SyncStreamTask] = []

    for event_id in event_ids:
        seed = seed_by_event_id.get(event_id)
        if seed is None:
            continue

        tasks.append(
            SyncStreamTask.full(
                event_id=event_id,
                job_id=job_id,
                connector=connector,
                scope_id=scope_id,
                target_type=seed.target_type,
                target_id=seed.target_id,
                sync_from_ts=seed.sync_from_ts,
                attempt=0,
                max_attempts=seed.max_attempts,
            )
        )

    return tasks
