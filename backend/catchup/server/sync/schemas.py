from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from typing import Any

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import field_validator

from catchup.db.models import SyncConnector
from catchup.db.models import SyncEventStatus
from catchup.db.models import SyncJobStatus
from catchup.db.models import SyncType
from catchup.sync.common.exceptions import SyncRequestException
from catchup.sync.common.schemas import FullSyncDispatchRequest
from catchup.sync.common.schemas import FullSyncRequestedTarget
from catchup.sync.common.schemas import SyncDispatchResult
from catchup.sync.common.schemas import SyncDispatchStatus
from catchup.sync.common.schemas import SyncTargetType
from catchup.sync.common.schemas import SyncTrigger
from catchup.sync.query_service import SyncJobSnapshotResult
from catchup.sync.query_service import SyncJobTargetSnapshotResult
from catchup.sync.query_service import SyncScopeStatusResult
from catchup.sync.query_service import SyncTargetsResult


class SyncJobTargetSnapshotItem(BaseModel):
    target_id: str
    target_name: str
    status: SyncEventStatus

    @classmethod
    def from_snapshot_result(
        cls,
        result: SyncJobTargetSnapshotResult,
    ) -> "SyncJobTargetSnapshotItem":
        return cls.model_validate(asdict(result))


class SyncJobSnapshotResponse(BaseModel):
    """
    공통 Job 상태 조회 응답
    """

    job_id: str
    connector: SyncConnector
    sync_type: SyncType = SyncType.FULL
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
    targets: list[SyncJobTargetSnapshotItem] = Field(default_factory=list)

    last_error: str | None = None
    metrics: dict[str, int] = Field(default_factory=dict)

    @classmethod
    def from_snapshot_result(
        cls,
        result: SyncJobSnapshotResult,
    ) -> "SyncJobSnapshotResponse":
        return cls.model_validate(asdict(result))


class FullSyncRequest(BaseModel):
    """
    공통 Full Sync 요청
    """
    model_config = ConfigDict(extra="forbid")

    connector: SyncConnector = Field(..., description="sync connector type")
    scope_id: str = Field(
        ...,
        description=(
            "connector scope id "
            "(team_id / installation_id / cloud_id / channel_id)"
        ),
    )
    targets: list[FullSyncRequestedTarget] = Field(
        ...,
        min_length=1,
        description=(
            "required targets returned by GET /api/v1/sync/targets "
            "(target_type + target_id)"
        ),
    )
    sync_days: int | None = Field(
        default=None,
        ge=1,
        description="collection period in days; if omitted connector default is used",
    )

    @field_validator("scope_id")
    @classmethod
    def _validate_scope_id(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("scope_id must not be empty")
        return stripped

    @field_validator("targets")
    @classmethod
    def _validate_targets(
        cls,
        value: list[FullSyncRequestedTarget],
    ) -> list[FullSyncRequestedTarget]:
        normalized: list[FullSyncRequestedTarget] = []
        seen: set[tuple[SyncTargetType, str]] = set()

        for item in value:
            # 같은 ID라도 target_type이 다르면 서로 다른 리소스다.
            # 예: Channel Talk channel-123과 space-123은 tuple 기준으로만 비교한다.
            key = (item.target_type, item.target_id)
            if key in seen:
                continue
            seen.add(key)
            normalized.append(item)

        if not normalized:
            raise ValueError("targets must not be empty")

        return normalized

    def to_dispatch_request(
        self,
        *,
        default_sync_days: int,
        trigger: SyncTrigger = SyncTrigger.API,
        now: datetime | None = None,
    ) -> FullSyncDispatchRequest:
        # API 모델은 사용자 입력을 검증하고, 내부 dispatch 모델은 실행에 필요한
        # sync_from_ts까지 계산한 불변 요청 객체로 넘긴다.
        sync_days = self.sync_days if self.sync_days is not None else default_sync_days
        if sync_days < 1:
            raise SyncRequestException(
                "sync_days must be greater or equal to 1",
                code="invalid_sync_days",
            )

        current_time = now or datetime.now(timezone.utc)
        sync_from_ts = f"{(current_time - timedelta(days=sync_days)).timestamp():.6f}"

        return FullSyncDispatchRequest(
            scope_id=self.scope_id,
            targets=self.targets,
            sync_from_ts=sync_from_ts,
            trigger=trigger,
        )


class SyncAcceptedResponse(BaseModel):
    """
    공통 Sync 접수 응답
    """

    status: SyncDispatchStatus = Field(
        ...,
        description=(
            "accepted : means a new dispatch was created, "
            "no_events : no sync events were generated, "
            "conflict : an active full sync already exists. "
            "failed : dispatch did not match accepted, no_events, or conflict"
        ),
    )
    connector: SyncConnector
    scope_id: str

    job_id: str | None = Field(
        default=None,
        description="created job id, or the active job id when status is conflict",
    )
    event_ids: list[str] = Field(
        default_factory=list,
        description="persisted sync event ids created for the accepted dispatch",
    )

    total_targets: int = 0
    queued_targets: int = Field(
        default=0,
        description="number of targets successfully published to the queue",
    )

    message: str | None = None

    @classmethod
    def from_dispatch_result(cls, result: SyncDispatchResult) -> "SyncAcceptedResponse":
        return cls.model_validate(asdict(result))


class SyncStatusResponse(BaseModel):
    """
    scope 기준 최신 Full Sync 상태 응답
    """

    connector: SyncConnector
    scope_id: str
    sync_type: SyncType = SyncType.FULL
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

    @classmethod
    def from_scope_status_result(
        cls,
        result: SyncScopeStatusResult,
    ) -> "SyncStatusResponse":
        return cls.model_validate(asdict(result))


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
    target_type: SyncTargetType
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

    @classmethod
    def from_targets_result(cls, result: SyncTargetsResult) -> "SyncTargetsResponse":
        return cls.model_validate(asdict(result))

# ==============================================================================

class SyncRecordGapItem(BaseModel):
    record_type: str
    expected_count: int = 0
    stored_count: int = 0
    missing_count: int = 0
    missing_ids: list[str] = Field(default_factory=list)


class SyncRecordGapResponse(BaseModel):
    connector: SyncConnector
    scope_id: str
    target_id: str
    target_name: str
    event_id: str | None = None
    attempt: int | None = None
    event_status: SyncEventStatus | None = None
    records: list[SyncRecordGapItem] = Field(default_factory=list)


class SyncRecordRetryItemRequest(BaseModel):
    record_type: str
    record_ids: list[str] = Field(default_factory=list)

    @field_validator("record_type")
    @classmethod
    def _validate_record_type(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("record_type must not be empty")
        return stripped

    @field_validator("record_ids")
    @classmethod
    def _validate_record_ids(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()

        for item in value:
            candidate = (item or "").strip()
            if not candidate:
                raise ValueError("record_ids must not contain empty values")
            if candidate in seen:
                continue
            seen.add(candidate)
            normalized.append(candidate)

        if not normalized:
            raise ValueError("record_ids must not be empty")

        return normalized


class SyncRecordRetryItemResponse(BaseModel):
    record_type: str
    requested_ids: list[str] = Field(default_factory=list)
    retried_count: int = 0
    succeeded_count: int = 0
    failed_ids: list[str] = Field(default_factory=list)
    remaining_missing_ids: list[str] = Field(default_factory=list)


class SyncRecordRetryRequest(BaseModel):
    event_id: str = Field(..., description="sync event id for event-based retry")
    records: list[SyncRecordRetryItemRequest] = Field(default_factory=list)

    @field_validator("event_id")
    @classmethod
    def _validate_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("field must not be empty")
        return stripped

    @field_validator("records")
    @classmethod
    def _validate_records(cls, value: list[SyncRecordRetryItemRequest]) -> list[SyncRecordRetryItemRequest]:
        if not value:
            raise ValueError("records must not be empty")

        seen: set[str] = set()
        normalized: list[SyncRecordRetryItemRequest] = []

        for item in value:
            if item.record_type in seen:
                raise ValueError(f"duplicate record_type: {item.record_type}")
            seen.add(item.record_type)
            normalized.append(item)

        return normalized


class SyncRecordRetryResponse(BaseModel):
    connector: SyncConnector
    scope_id: str
    target_id: str
    target_name: str
    event_id: str | None = None
    event_status: SyncEventStatus | None = None
    records: list[SyncRecordRetryItemResponse] = Field(default_factory=list)


class SlackIncrementalRecoveryResponse(BaseModel):
    connector: SyncConnector = SyncConnector.SLACK
    total_incremental_records_before_recovery: int = 0
    succeeded_records: int = 0
    failed_records: int = 0
