from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from enum import StrEnum

from catchup.knowledge_maintenance.domain.source_version import JsonValue


class PipelineEventType(StrEnum):
    OBSERVATION_READY = "observation.ready"


class PipelineAggregateType(StrEnum):
    OBSERVATION = "observation"


class PipelineEventStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"


class FailureKind(StrEnum):
    """실패가 다시 시도할 만한 것인지 가른다.

    이 구분이 재시도 정책의 전부다. 둘을 섞으면 결정론적으로 실패하는 문서에
    매 주기마다 LLM 비용이 나가거나, 반대로 일시적인 오류 한 번으로 문서를
    영영 포기하게 된다.
    """

    # 같은 입력에 같은 계약이면 다시 해도 같은 결과다. 프롬프트나 계약을
    # 고쳐야 풀리므로 자동 재시도가 의미 없다.
    PERMANENT = "permanent"
    # throttling이나 timeout처럼 시간이 지나면 풀린다.
    TRANSIENT = "transient"


# 일시적 실패를 다시 시도하기까지 기다리는 시간이다. 시도가 거듭될수록
# 배로 늘려 같은 대상에 몰리지 않게 한다.
BACKOFF_BASE = timedelta(minutes=1)
MAX_ATTEMPTS = 5


@dataclass(frozen=True, slots=True)
class PipelineEvent:
    """다음 단계가 처리할 일 하나를 표현한다.

    Attributes:
        id: 큐 안에서 이 일을 식별한다.
        workspace_id: 일이 속한 CatchUp workspace를 식별한다.
        event_type: 무엇을 하라는 지시인지 나타낸다.
        aggregate_type: 대상 record의 종류를 나타낸다.
        aggregate_id: 대상 record를 가리킨다.
        status: 처리 상태를 나타낸다.
        attempts: 지금까지 시도한 횟수를 나타낸다.
        available_at: 이 시각이 지나야 집을 수 있다.
        payload: 처리에 필요한 부가 정보를 담는다.
        last_error: 마지막 실패 사유를 보존한다.
    """

    id: int
    workspace_id: int
    event_type: PipelineEventType
    aggregate_type: PipelineAggregateType
    aggregate_id: uuid.UUID
    status: PipelineEventStatus
    attempts: int
    available_at: datetime
    payload: Mapping[str, JsonValue] = field(default_factory=dict)
    last_error: str | None = None

    def __post_init__(self) -> None:
        if self.workspace_id <= 0:
            raise ValueError("workspace_id must be greater than 0")
        if self.attempts < 0:
            raise ValueError("attempts must not be negative")
        if self.available_at.tzinfo is None:
            raise ValueError("available_at must include timezone information")


def next_attempt_at(attempts: int, *, now: datetime) -> datetime:
    """다음 시도 시각을 정한다.

    시도 횟수만큼 대기를 배로 늘린다. 1분, 2분, 4분 순이다.
    """
    if attempts < 0:
        raise ValueError("attempts must not be negative")
    return now.astimezone(timezone.utc) + BACKOFF_BASE * (2**attempts)


def resolve_failure(
    kind: FailureKind,
    attempts: int,
) -> PipelineEventStatus:
    """실패한 일을 다시 큐에 둘지 접을지 정한다.

    영구 실패는 한 번으로 접는다. 일시적 실패도 정해진 횟수를 넘으면 접는다.
    무한히 재시도하면 고쳐지지 않는 대상에 비용이 계속 나가고, 진짜 문제가
    실패 목록에 드러나지 않는다.
    """
    if kind is FailureKind.PERMANENT:
        return PipelineEventStatus.FAILED
    if attempts >= MAX_ATTEMPTS:
        return PipelineEventStatus.FAILED
    return PipelineEventStatus.PENDING
