from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4

from sqlalchemy.orm import Session

from catchup.configs.config import settings
from catchup.db.models import SyncConnector, SyncType
from catchup.db.sync import (
    SyncEventCreateInput as DbSyncEventCreateInput,
    SyncJobCreateInput as DbSyncJobCreateInput,
    create_events as create_db_sync_events,
    create_job as create_db_sync_job,
)


@dataclass(slots=True, frozen=True)
class SlackSyncEventSeed:
    event_id: str
    channel_id: str
    channel_name: str
    sync_from: str
    max_attempts: int


def build_full_sync_event_seeds(
    *,
    channels: list[dict[str, str]],
    sync_from: str,
) -> list[SlackSyncEventSeed]:
    seeds: list[SlackSyncEventSeed] = []

    for channel in channels:
        channel_id = (channel.get("id") or "").strip()
        if not channel_id:
            continue

        channel_name = (channel.get("name") or channel_id).strip() or channel_id
        seeds.append(
            SlackSyncEventSeed(
                event_id=uuid4().hex,
                channel_id=channel_id,
                channel_name=channel_name,
                sync_from=sync_from,
                max_attempts=settings.SYNC_JOB_MAX_ATTEMPTS,
            )
        )

    return seeds


def persist_full_sync_job_and_events(
    db: Session,
    *,
    job_id: str,
    team_id: str,
    requested_at: datetime,
    event_seeds: list[SlackSyncEventSeed],
) -> list[str]:
    create_db_sync_job(
        db,
        DbSyncJobCreateInput(
            job_id=job_id,
            connector=SyncConnector.SLACK,
            sync_type=SyncType.FULL,
            scope_id=team_id,
            requested_at=requested_at,
        ),
    )

    created_events = create_db_sync_events(
        db,
        [
            DbSyncEventCreateInput(
                event_id=seed.event_id,
                job_id=job_id,
                connector=SyncConnector.SLACK,
                resource_type="channel",
                resource_id=seed.channel_id,
                requested_at=requested_at,
                resource_metadata={
                    "scope_id": team_id,
                    "team_id": team_id,
                    "channel_name": seed.channel_name,
                    "target_name": seed.channel_name,
                    "sync_type": "full",
                    "sync_from": seed.sync_from,
                },
                max_attempts=seed.max_attempts,
            )
            for seed in event_seeds
        ],
    )

    return [item.event_id for item in created_events]
