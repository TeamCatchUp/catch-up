from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator

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


class FullSyncRequest(BaseModel):
    """
    공통 Full Sync 요청
    """

    connector: SyncConnector = Field(..., description="sync connector type")
    scope_id: str = Field(
        ...,
        description="connector scope id (team_id / installation_id / cloud_id)",
    )
    target_ids: list[str] = Field(
        ...,
        min_length=1,
        description="required target ids returned by GET /api/v1/sync/targets",
    )
    sync_days: int | None = Field(
        default=None,
        ge=1,
        description="collection period in days; if omitted connector default is used",
    )
    
    @field_validator("target_ids")
    @classmethod
    def _validate_target_ids(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()

        for item in value:
            candidate = (item or "").strip()
            if not candidate:
                raise ValueError("target_ids must not contain empty values")
            if candidate in seen:
                continue
            seen.add(candidate)
            normalized.append(candidate)

        if not normalized:
            raise ValueError("target_ids must not be empty")

        return normalized


class IncrementalSyncRequest(BaseModel):
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

    message: str | None = None
    snapshot_url: str | None = None
    stream_url: str | None = None


class SyncStatusResponse(BaseModel):
    """
    scope 기준 최신 Full Sync 상태 응답
    """

    connector: SyncConnector
    scope_id: str
    sync_type: str = "full"
    job_id: str
    status: SyncJobStatus

    requested_at: str
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


class SyncFlushRequest(BaseModel):
    """
    공통 Flush 요청
    """

    connector: SyncConnector = Field(..., description="flush target connector")
    scope_ids: list[str] | None = Field(
        default=None,
        description="connector scope ids to flush (optional)",
    )


class SyncFlushResponse(BaseModel):
    """
    공통 Flush 응답
    """

    status: str = Field(..., description="no_events | not_implemented")
    connector: SyncConnector
    scope_ids: list[str] = Field(default_factory=list)
    message: str | None = None


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
