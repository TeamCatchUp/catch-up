from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from catchup.connectors.slack.sync_runtime.constants import SyncEventType, SyncJobStatus


class SyncJobSnapshotResponse(BaseModel):
    """
    공통 Job 상태 조회 응답
    """

    job_id: str
    connector: str
    team_id: str

    status: SyncJobStatus

    created_at: str
    started_at: str | None = None
    completed_at: str | None = None

    total_channels: int = 0
    queued_channels: int = 0
    processing_channels: int = 0
    completed_channels: int = 0
    failed_channels: int = 0
    requeued_channels: int = 0

    last_error: str | None = None


class SyncStreamEventResponse(BaseModel):
    """
    SSE data payload 포맷
    """

    connector: str
    job_id: str
    team_id: str
    event_type: SyncEventType
    sequence: int
    timestamp: str
    payload: dict[str, Any] = Field(default_factory=dict)
