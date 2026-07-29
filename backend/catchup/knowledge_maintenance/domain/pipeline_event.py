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
    """실패가 무엇 때문이었는지 나타낸다.

    처음에는 `permanent`와 `transient`로 나눠 "다시 시도할 것인가"를 이름에
    담았다. 실측이 그 전제를 부정했다. 계약 위반을 영구 실패로 두었는데 같은
    입력에 같은 프롬프트로 다시 돌리자 성공했다. `temperature`가 0이어도 LLM은
    완전히 결정론적이지 않고, 계약 위반은 대부분 출력이 스키마에서 살짝
    어긋나는 것이라 정확히 그 흔들림 구간에 있다.

    그래서 재시도 여부가 아니라 몇 번까지 봐줄지를 종류마다 다르게 둔다.
    """

    # 스키마에서 어긋난 출력이다. 흔들림이면 곧 성공하고, 프롬프트가 잘못됐다면
    # 곧 포기하는 편이 낫다.
    CONTRACT_VIOLATION = "contract_violation"
    # throttling이나 timeout이다. 오래 갈 수 있으므로 더 봐준다.
    API_ERROR = "api_error"


# 실패를 다시 시도하기까지 기다리는 시간이다. 시도가 거듭될수록 배로 늘려
# 같은 대상에 몰리지 않게 한다.
BACKOFF_BASE = timedelta(minutes=1)

# 종류마다 봐주는 횟수가 다르다. 넘으면 접는다. 무한히 재시도하면 고쳐지지
# 않는 대상에 비용이 나가고, 진짜 문제가 실패 목록에 드러나지 않는다.
RETRY_LIMITS = {
    FailureKind.CONTRACT_VIOLATION: 2,
    FailureKind.API_ERROR: 5,
}


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
    """실패한 일을 다시 큐에 둘지 접을지 정한다."""
    if attempts >= RETRY_LIMITS[kind]:
        return PipelineEventStatus.FAILED
    return PipelineEventStatus.PENDING
