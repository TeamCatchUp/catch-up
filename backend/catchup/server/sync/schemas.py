from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from catchup.db.models import SyncConnector, SyncJobStatus


class SyncJobSnapshotResponse(BaseModel):
    """
    공통 Job 상태 조회 응답
    """

    job_id: str
    connector: SyncConnector
    sync_type: str = "full"
    scope_id: str

    status: SyncJobStatus

    created_at: str
    started_at: str | None = None
    completed_at: str | None = None

    total_targets: int = 0
    queued_targets: int = 0
    processing_targets: int = 0
    completed_targets: int = 0
    failed_targets: int = 0
    requeued_targets: int = 0

    last_error: str | None = None
    metrics: dict[str, int] = Field(default_factory=dict)


class SyncStreamEventResponse(BaseModel):
    """
    SSE data payload 포맷
    """

    connector: SyncConnector
    job_id: str
    scope_id: str
    event_type: str
    sequence: int
    timestamp: str
    payload: dict[str, Any] = Field(default_factory=dict)


class SyncFullRequest(BaseModel):
    """
    공통 Full Sync 요청
    """

    connector: SyncConnector = Field(..., description="sync connector type")
    scope_id: str = Field(..., description="connector scope id (team_id / installation_id / cloud_id)")
    target_ids: list[str] | None = Field(
        default=None,
        description="sync targets (channel/repository/space/project ids)",
    )
    sync_days: int | None = Field(
        default=None,
        ge=1,
        description="collection period in days; if omitted connector default is used",
    )


class SyncIncrementalRequest(BaseModel):
    """
    공통 Incremental Sync 요청
    """

    connector: SyncConnector = Field(..., description="sync connector type")
    scope_id: str = Field(..., description="connector scope id (team_id / installation_id / cloud_id)")
    target_ids: list[str] | None = Field(
        default=None,
        description="incremental sync targets (optional)",
    )


class SyncAcceptedResponse(BaseModel):
    """
    공통 Sync 접수 응답
    """

    status: str = Field(..., description="accepted | no_events | conflict | failed")
    connector: SyncConnector
    scope_id: str

    job_id: str | None = None
    event_ids: list[str] = Field(default_factory=list)

    total_targets: int = 0
    queued_targets: int = 0
    dropped_targets: int = 0
    dropped_events: int = 0

    message: str | None = None
    snapshot_url: str | None = None
    stream_url: str | None = None


class SyncErrorResponse(BaseModel):
    """
    공통 Sync API 에러 응답
    """

    code: str
    message: str
    connector: SyncConnector | None = None
    scope_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SyncTargetItem(BaseModel):
    """
    공통 Sync target item
    """

    target_id: str
    display_name: str
    target_type: str
    is_accessible: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class SyncTargetsResponse(BaseModel):
    """
    공통 Sync targets 조회 응답
    """

    connector: SyncConnector
    scope_id: str
    total_targets: int
    targets: list[SyncTargetItem] = Field(default_factory=list)
