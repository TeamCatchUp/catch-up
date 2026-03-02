from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from catchup.auth.dependencies import require_admin_user
from catchup.configs.config import settings
from catchup.connectors.slack.sync_runtime import events as runtime_events
from catchup.connectors.slack.sync_runtime import job_store
from catchup.connectors.slack.sync_runtime.constants import SyncEventType, SyncJobStatus
from catchup.db.models import User
from catchup.server.sync.schemas import SyncJobSnapshotResponse, SyncStreamEventResponse


router = APIRouter(prefix="/api/v1/sync", tags=["sync-runtime"])


@router.get("/jobs/{job_id}", response_model=SyncJobSnapshotResponse)
async def get_job_snapshot(
    job_id: str,
    _admin_user: User = Depends(require_admin_user),
):
    meta = await job_store.get_job(job_id)
    if meta is None:
        raise HTTPException(status_code=404, detail=f"sync job not found: {job_id}")

    return SyncJobSnapshotResponse(
        job_id=meta.job_id,
        connector=meta.connector,
        sync_type=meta.sync_type,
        team_id=meta.team_id,
        status=meta.status,
        created_at=meta.created_at,
        started_at=meta.started_at,
        completed_at=meta.completed_at,
        total_channels=meta.total_channels,
        queued_channels=meta.queued_channels,
        processing_channels=meta.processing_channels,
        completed_channels=meta.completed_channels,
        failed_channels=meta.failed_channels,
        requeued_channels=meta.requeued_channels,
        synced_messages=meta.synced_messages,
        flushed_events=meta.flushed_events,
        dropped_channels=meta.dropped_channels,
        dropped_events=meta.dropped_events,
        last_error=meta.last_error,
    )


@router.get("/jobs/{job_id}/stream")
async def stream_job_events(
    job_id: str,
    from_sequence: int = Query(1, ge=1),
    _admin_user: User = Depends(require_admin_user),
):
    meta = await job_store.get_job(job_id)
    if meta is None:
        raise HTTPException(status_code=404, detail=f"sync job not found: {job_id}")

    async def event_generator():
        next_seq = max(1, from_sequence)

        while True:
            items = await runtime_events.get_events(job_id, start_sequence=next_seq)

            if items:
                for item in items:
                    data = SyncStreamEventResponse(
                        connector=item.connector,
                        job_id=item.job_id,
                        team_id=item.team_id,
                        event_type=item.event_type,
                        sequence=item.sequence,
                        timestamp=item.timestamp,
                        payload=item.payload,
                    )
                    yield f"data: {data.model_dump_json(ensure_ascii=False)}\n\n"
                    next_seq = item.sequence + 1

                if any(
                    item.event_type in {SyncEventType.JOB_COMPLETED, SyncEventType.JOB_FAILED}
                    for item in items
                ):
                    break
            else:
                # 이벤트가 없으면 job 종료 여부 확인
                latest_meta = await job_store.get_job(job_id)
                if latest_meta and latest_meta.status in {SyncJobStatus.SUCCESS, SyncJobStatus.FAILED}:
                    tail_items = await runtime_events.get_events(job_id, start_sequence=next_seq)
                    if tail_items:
                        continue
                    break

                heartbeat = await runtime_events.append_heartbeat(job_id, meta.team_id)
                hb_data = SyncStreamEventResponse(
                    connector=heartbeat.connector,
                    job_id=heartbeat.job_id,
                    team_id=heartbeat.team_id,
                    event_type=heartbeat.event_type,
                    sequence=heartbeat.sequence,
                    timestamp=heartbeat.timestamp,
                    payload=heartbeat.payload,
                )
                yield f"data: {hb_data.model_dump_json(ensure_ascii=False)}\n\n"
                next_seq = heartbeat.sequence + 1

                await asyncio.sleep(settings.SYNC_SSE_HEARTBEAT_SECONDS)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
