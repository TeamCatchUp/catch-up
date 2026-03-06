from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from uuid import uuid4

from sqlalchemy.orm import Session

from catchup.db.models import SyncConnector, SyncType
from catchup.db.sync import (
    SyncEventCreateInput as DbSyncEventCreateInput,
    SyncJobCreateInput as DbSyncJobCreateInput,
    create_events as create_db_sync_events,
    create_job as create_db_sync_job,
)
from catchup.sync.common.schemas import SyncEventSeed, SyncStreamTask

def build_seeds_from_targets(
    *,
    target_type: str,
    targets: list[dict[str, str]],
    id_key: str = "id",
    name_key: str = "name",
    per_target_metadata_builder: Callable[[dict[str, str]], dict[str, object] | None] | None = None,
    max_attempts: int = 3,
) -> list[SyncEventSeed]:
    normalized_target_type = target_type.strip()
    if not normalized_target_type:
        raise ValueError("target_type is empty")

    normalized_max_attempts = max(1, int(max_attempts))
    seeds: list[SyncEventSeed] = []

    for target in targets:
        target_id = (target.get(id_key) or "").strip()
        if not target_id:
            continue

        target_name = (target.get(name_key) or target_id).strip() or target_id
        target_metadata = (
            per_target_metadata_builder(target) if per_target_metadata_builder else None
        )

        seeds.append(
            SyncEventSeed(
                event_id=uuid4().hex,
                target_type=normalized_target_type,
                target_id=target_id,
                target_name=target_name,
                metadata=dict(target_metadata or {}),
                max_attempts=normalized_max_attempts,
            )
        )

    return seeds


def persist_sync_job_and_events(
    db: Session,
    *,
    job_id: str,
    connector: SyncConnector,
    sync_type: SyncType,
    scope_id: str,
    requested_at: datetime,
    event_seeds: list[SyncEventSeed],
    scope_metadata: dict[str, object] | None = None,
) -> list[str]:
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

    normalized_scope_metadata = dict(scope_metadata or {})
    payloads: list[DbSyncEventCreateInput] = []

    for seed in event_seeds:
        resource_metadata: dict[str, object] = {
            "scope_id": scope_id,
            "target_name": seed.target_name,
            "sync_type": sync_type.value,
        }
        resource_metadata.update(normalized_scope_metadata)
        resource_metadata.update(seed.metadata)

        payloads.append(
            DbSyncEventCreateInput(
                event_id=seed.event_id,
                job_id=job_id,
                connector=connector,
                resource_type=seed.target_type,
                resource_id=seed.target_id,
                requested_at=requested_at,
                resource_metadata=resource_metadata,
                max_attempts=seed.max_attempts,
            )
        )

    created_events = create_db_sync_events(db, payloads)
    return [item.event_id for item in created_events]


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
            SyncStreamTask(
                event_id=event_id,
                job_id=job_id,
                connector=connector.value,
                sync_type=sync_type.value,
                scope_id=scope_id,
                target_type=seed.target_type,
                target_id=seed.target_id,
                attempt=0,
                max_attempts=seed.max_attempts,
            )
        )

    return tasks
