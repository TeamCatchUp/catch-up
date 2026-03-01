from __future__ import annotations

from typing import Any
from typing import Literal

from pydantic import BaseModel, Field

from catchup.connectors.slack.sync_runtime.constants import (
    CONNECTOR_SLACK,
    SyncEventType,
    SyncJobStatus,
)

def _decode_redis_value(value: Any) -> str:

    if isinstance(value, bytes):
        return value.decode("utf-8")
    return str(value)

def _to_int(value: Any, default: int=0) -> int:
    try:
        return int(_decode_redis_value(value))
    except (TypeError, ValueError):
        return default
    
class SlackChannelSyncTask(BaseModel):
    """
    Redis Queue에 발행되는 채널 단위 동기화 작업 이벤트
    """

    connector: str = Field(default=CONNECTOR_SLACK, description="connector key")
    sync_type: Literal["full", "incremental"] = Field(
        default="full",
        description="sync task type",
    )
    event_id: str = Field(..., description="queue event id")
    job_id: str = Field(..., description="full sync job id")
    team_id: str = Field(..., description="slack workspace id")
    channel_id: str = Field(..., description="slack channel id")
    channel_name: str = Field(..., description="slack channel name")
    sync_from: str | None = Field(default=None, description="oldest slack ts")
    attempt: int = Field(default=0, description="current retry attempt")
    max_attempts: int = Field(default=3, description="max retry attempts")
    enqueued_at: str = Field(..., description="utc iso timestamp when queued")

    def to_queue_payload(self) -> str:
        """Redis List에 넣기 위한 JSON 문자열"""
        return self.model_dump_json(ensure_ascii=False)

    @classmethod
    def from_queue_payload(cls, payload: str) -> "SlackChannelSyncTask":
        """Redis List에서 꺼낸 JSON 문자열 파싱"""
        return cls.model_validate_json(payload)

class DelayedQueueItem(BaseModel):
    """
    채널 락 충돌/재시도를 위한 이벤트
    """

    due_at_epoch_ms: int = Field(..., description="requeue due time(epoch ms)")
    task: SlackChannelSyncTask = Field(..., description="delayed task payload")

    def to_queue_payload(self) -> str:
        return self.model_dump_json(ensure_ascii=False)

    @classmethod
    def from_queue_payload(cls, payload: str) -> "DelayedQueueItem":
        return cls.model_validate_json(payload)
    
class SyncJobMeta(BaseModel):
    """
    Redis Hash로 관리하는 Job 메타 정보
    """

    job_id: str
    connector: str = CONNECTOR_SLACK
    sync_type: Literal["full", "incremental"] = "full"
    team_id: str

    status: SyncJobStatus = SyncJobStatus.ACCEPTED
    created_at: str
    started_at: str | None = None
    completed_at: str | None = None

    total_channels: int = 0
    queued_channels: int = 0
    processing_channels: int = 0
    completed_channels: int = 0
    failed_channels: int = 0
    requeued_channels: int = 0
    synced_messages: int = 0
    flushed_events: int = 0
    dropped_channels: int = 0
    dropped_events: int = 0

    last_error: str | None = None

    def to_redis_hash(self) -> dict[str, str]:
        """
        Redis HSET에 넣기 위해 모든 값을 문자열로 직렬화
        """
        data = self.model_dump(mode="json")
        return {key: "" if value is None else str(value) for key, value in data.items()}

    @classmethod
    def from_redis_hash(cls, data: dict[str, Any]) -> "SyncJobMeta":
        """
        Redis HGETALL 결과를 모델로 복원
        """
        normalized: dict[str, Any] = {_decode_redis_value(k): v for k, v in data.items()}

        return cls(
            job_id=_decode_redis_value(normalized.get("job_id", "")),
            connector=_decode_redis_value(normalized.get("connector", CONNECTOR_SLACK)),
            sync_type=_decode_redis_value(normalized.get("sync_type", "full")),
            team_id=_decode_redis_value(normalized.get("team_id", "")),
            status=SyncJobStatus(_decode_redis_value(normalized.get("status", SyncJobStatus.ACCEPTED.value))),
            created_at=_decode_redis_value(normalized.get("created_at", "")),
            started_at=(
                None
                if _decode_redis_value(normalized.get("started_at", "")) == ""
                else _decode_redis_value(normalized.get("started_at", ""))
            ),
            completed_at=(
                None
                if _decode_redis_value(normalized.get("completed_at", "")) == ""
                else _decode_redis_value(normalized.get("completed_at", ""))
            ),
            total_channels=_to_int(normalized.get("total_channels", 0)),
            queued_channels=_to_int(normalized.get("queued_channels", 0)),
            processing_channels=_to_int(normalized.get("processing_channels", 0)),
            completed_channels=_to_int(normalized.get("completed_channels", 0)),
            failed_channels=_to_int(normalized.get("failed_channels", 0)),
            requeued_channels=_to_int(normalized.get("requeued_channels", 0)),
            synced_messages=_to_int(normalized.get("synced_messages", 0)),
            flushed_events=_to_int(normalized.get("flushed_events", 0)),
            dropped_channels=_to_int(normalized.get("dropped_channels", 0)),
            dropped_events=_to_int(normalized.get("dropped_events", 0)),
            last_error=(
                None
                if _decode_redis_value(normalized.get("last_error", "")) == ""
                else _decode_redis_value(normalized.get("last_error", ""))
            ),
        )
    
class SyncRuntimeEvent(BaseModel):
    """
    Redis 이벤트 로그 + SSE 공통 이벤트 포맷
    """

    connector: str = CONNECTOR_SLACK
    job_id: str
    team_id: str
    event_type: SyncEventType
    sequence: int
    timestamp: str
    payload: dict[str, Any] = Field(default_factory=dict)

    def to_event_log_payload(self) -> str:
        return self.model_dump_json(ensure_ascii=False)

    @classmethod
    def from_event_log_payload(cls, payload: str) -> "SyncRuntimeEvent":
        return cls.model_validate_json(payload)

    def to_sse_data(self) -> str:
        """
        SSE으로 전송할 JSON 문자열
        """
        return self.model_dump_json(ensure_ascii=False)
