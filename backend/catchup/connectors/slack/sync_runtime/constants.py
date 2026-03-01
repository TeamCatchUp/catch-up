from __future__ import annotations

from enum import StrEnum
from typing import Final

CONNECTOR_SLACK: Final[str] = "slack"
RESOURCE_TYPE_CHANNEL: Final[str] = "channel"

# Channel 단위 작업 이벤트를 적재하는 메인 큐
SLACK_FULL_SYNC_QUEUE_KEY: Final[str] = "sync:slack:full:queue"
# ACK 전 이벤트를 임시로 보관하는 처리중 큐
SLACK_FULL_SYNC_PROCESSING_KEY: Final[str] = "sync:slack:full:processing"
# 채널 락 충돌/재시도 백오프 이벤트를 보관하는 지연 큐
SLACK_FULL_SYNC_DELAYED_KEY: Final[str] = "sync:slack:full:delayed"
# 최대 재시도 초과 이벤트를 적재하는 데드레터 큐
SLACK_FULL_SYNC_DEADLETTER_KEY: Final[str] = "sync:slack:full:deadletter"


# Redis Job / Lock Key Templates
JOB_META_KEY_TMPL: Final[str] = "sync:job:{job_id}"
JOB_EVENTS_KEY_TMPL: Final[str] = "sync:job:{job_id}:events"
JOB_EVENT_SEQ_KEY_TMPL: Final[str] = "sync:job:{job_id}:seq"

TEAM_LOCK_KEY_TMPL: Final[str] = "sync:lock:slack:{team_id}:team"
TEAM_ACTIVE_CHANNELS_KEY_TMPL: Final[str] = "sync:lock:slack:{team_id}:channels"
CHANNEL_LOCK_KEY_TMPL: Final[str] = "sync:lock:slack:{team_id}:channel:{channel_id}"


def build_job_meta_key(job_id: str) -> str:
    return JOB_META_KEY_TMPL.format(job_id=job_id)


def build_job_events_key(job_id: str) -> str:
    return JOB_EVENTS_KEY_TMPL.format(job_id=job_id)


def build_job_event_seq_key(job_id: str) -> str:
    return JOB_EVENT_SEQ_KEY_TMPL.format(job_id=job_id)


def build_team_lock_key(team_id: str) -> str:
    return TEAM_LOCK_KEY_TMPL.format(team_id=team_id)


def build_team_active_channels_key(team_id: str) -> str:
    return TEAM_ACTIVE_CHANNELS_KEY_TMPL.format(team_id=team_id)


def build_channel_lock_key(team_id: str, channel_id: str) -> str:
    return CHANNEL_LOCK_KEY_TMPL.format(team_id=team_id, channel_id=channel_id)


# Job Status / Runtime Events

class SyncJobStatus(StrEnum):
    ACCEPTED = "accepted"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"


class SyncEventType(StrEnum):
    JOB_CREATED = "job_created"
    JOB_STARTED = "job_started"
    CHANNEL_STARTED = "channel_started"
    CHANNEL_PROGRESS = "channel_progress"
    CHANNEL_COMPLETED = "channel_completed"
    CHANNEL_REQUEUED = "channel_requeued"
    CHANNEL_FAILED = "channel_failed"
    JOB_COMPLETED = "job_completed"
    JOB_FAILED = "job_failed"
    HEARTBEAT = "heartbeat"


class SyncPhase(StrEnum):
    API_ACCEPTED = "api_accepted"
    QUEUED = "queued"
    WORKER_STARTED = "worker_started"
    CHANNEL_SYNC = "channel_sync"
    CHANNEL_REQUEUE = "channel_requeue"
    JOB_FINALIZE = "job_finalize"


class SyncFailureReason(StrEnum):
    TEAM_LOCK_CONFLICT = "team_lock_conflict"
    CHANNEL_LOCK_CONFLICT = "channel_lock_conflict"
    INVALID_PAYLOAD = "invalid_payload"
    MAX_RETRIES_EXCEEDED = "max_retries_exceeded"
    SLACK_SYNC_EXCEPTION = "slack_sync_exception"
    REDIS_OPERATION_ERROR = "redis_operation_error"
    UNEXPECTED_ERROR = "unexpected_error"
