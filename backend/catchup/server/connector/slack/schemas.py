from typing import Literal

from pydantic import BaseModel, Field


# ================================================================
# Sync Request/Response
# ================================================================
class SyncResultDetail(BaseModel):
    """엔티티별 동기화 결과"""
    synced: int = 0
    errors: int = 0
    skipped: int = 0


class SlackSyncResponse(BaseModel):
    """동기화 응답"""
    status: str
    message: str
    team_id: str | None = None
    results: dict[str, SyncResultDetail] | None = None


class SlackFullSyncRequest(BaseModel):
    """Slack Full Sync 요청"""

    team_id: str = Field(..., description="Slack Team/Workspace ID")
    channel_ids: list[str] | None = Field(
        None,
        description="동기화할 Slack Channel ID 목록, 미지정 시 전체 채널",
    )
    sync_days: int | None = Field(
        None,
        ge=1,
        le=3650,
        description="수집 범위 (일), 미지정 시 기본값 사용",
    )


class SlackFullSyncAcceptedResponse(BaseModel):
    """Slack Full Sync 접수 응답"""

    status: Literal["accepted"] = "accepted"
    job_id: str
    team_id: str
    total_channels: int
    queued_channels: int
    snapshot_url: str
    stream_url: str


class SlackIncrementalFlushRequest(BaseModel):
    """Slack 증분 Flush(단건) 요청"""

    team_id: str = Field(..., description="Slack Team/Workspace ID")


class SlackIncrementalAcceptedResponse(BaseModel):
    """Slack 증분 Flush 접수 응답"""

    status: Literal["accepted"] = "accepted"
    job_id: str
    team_id: str
    total_channels: int
    queued_channels: int
    dropped_channels: int = 0
    dropped_events: int = 0
    snapshot_url: str
    stream_url: str


class SlackIncrementalNoEventsResponse(BaseModel):
    """Slack 증분 Flush no_events 응답"""

    status: Literal["no_events"] = "no_events"
    team_id: str
    dropped_channels: int = 0
    dropped_events: int = 0
    message: str


# ================================================================
# Sync Status
# ================================================================

class SlackSyncStatusResponse(BaseModel):
    """동기화 상태 응답"""
    team_id: str
    entity_type: str
    last_sync_status: str | None
    last_successful_sync_at: str | None
    synced_entities: int
    last_sync_error: str | None
    oldest_ts: str | None = None
    latest_ts: str | None = None


# ================================================================
# Channel Access (Debug)
# ================================================================

class ChannelAccessInfo(BaseModel):
    """채널 접근 정보"""
    id: str
    name: str
    channel_type: str
    is_member: bool
    is_private: bool
    member_count: int | None = None


class ChannelAccessResponse(BaseModel):
    """채널 접근 권한 디버그 응답"""
    team_id: str
    total_channels: int
    accessible_channels: int
    channels: list[ChannelAccessInfo]
