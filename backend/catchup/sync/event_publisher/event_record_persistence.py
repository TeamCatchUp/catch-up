from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from catchup.db.models import SyncConnector, SyncEvent, SyncType
from catchup.db.sync import (
    SyncEventCreateInput as DbSyncEventCreateInput,
    SyncJobCreateInput as DbSyncJobCreateInput,
    create_events as create_db_sync_events,
    create_job as create_db_sync_job,
)
from catchup.sync.common.schemas import SyncEventSeed


def _build_resource_metadata(
    *,
    scope_id: str,
    sync_type: SyncType,
    seed: SyncEventSeed,
) -> dict[str, object]:
    resource_metadata = dict(seed.metadata)
    resource_metadata["scope_id"] = scope_id
    resource_metadata["target_id"] = seed.target_id
    resource_metadata["target_name"] = seed.target_name
    resource_metadata["sync_type"] = sync_type.value
    resource_metadata["stage"] = seed.stage
    resource_metadata["range_start"] = seed.range_start.isoformat()
    resource_metadata["range_end"] = seed.range_end.isoformat()
    resource_metadata["chunk_index"] = seed.chunk_index
    resource_metadata["chunk_total"] = seed.chunk_total
    resource_metadata["range_watermark"] = seed.range_watermark.isoformat()
    if seed.sync_from_ts is not None:
        resource_metadata["sync_from_ts"] = seed.sync_from_ts
    return resource_metadata


def persist_sync_job_and_events(
    db: Session,
    *,
    job_id: str,
    connector: SyncConnector,
    sync_type: SyncType,
    scope_id: str,
    requested_at: datetime,
    event_seeds: list[SyncEventSeed],
) -> list[SyncEvent]:
    create_db_sync_job(
        db,
        DbSyncJobCreateInput(
            job_id=job_id,
            connector=connector,
            sync_type=sync_type,
            scope_id=scope_id,
            requested_at=requested_at,
        ),
    )

    payloads: list[DbSyncEventCreateInput] = []

    for seed in event_seeds:
        payloads.append(
            DbSyncEventCreateInput(
                event_id=seed.event_id,
                job_id=job_id,
                connector=connector,
                resource_type=seed.target_type,
                resource_id=seed.target_id,
                stage=seed.stage,
                range_start=seed.range_start,
                range_end=seed.range_end,
                chunk_index=seed.chunk_index,
                chunk_total=seed.chunk_total,
                range_watermark=seed.range_watermark,
                requested_at=requested_at,
                resource_metadata=_build_resource_metadata(
                    scope_id=scope_id,
                    sync_type=sync_type,
                    seed=seed,
                ),
                max_attempts=seed.max_attempts,
            )
        )

    return create_db_sync_events(db, payloads)
