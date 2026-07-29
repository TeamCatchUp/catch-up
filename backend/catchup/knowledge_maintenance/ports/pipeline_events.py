from __future__ import annotations

import uuid
from datetime import datetime
from typing import Protocol

from catchup.knowledge_maintenance.domain.pipeline_event import FailureKind
from catchup.knowledge_maintenance.domain.pipeline_event import PipelineAggregateType
from catchup.knowledge_maintenance.domain.pipeline_event import PipelineEvent
from catchup.knowledge_maintenance.domain.pipeline_event import PipelineEventType


class PipelineEventRepository(Protocol):
    """다음 단계가 처리할 일의 영속성을 정의한다."""

    def enqueue(
        self,
        *,
        workspace_id: int,
        event_type: PipelineEventType,
        aggregate_type: PipelineAggregateType,
        aggregate_id: uuid.UUID,
        payload: dict | None = None,
    ) -> PipelineEvent | None:
        """할 일을 큐에 적는다.

        같은 대상에 같은 지시가 이미 있으면 새로 적지 않고 `None`을 돌려준다.
        Observation을 저장하는 transaction에서 함께 불러야 지시가 유실되지
        않는다.
        """
        ...

    def claim_pending(
        self,
        *,
        workspace_id: int,
        event_type: PipelineEventType,
        now: datetime,
        limit: int | None = None,
    ) -> tuple[PipelineEvent, ...]:
        """지금 처리할 수 있는 일을 집는다.

        `available_at`이 지난 `pending`만 고른다. 백오프로 미뤄 둔 것은
        시각이 될 때까지 보이지 않는다.
        """
        ...

    def mark_processed(self, *, event_id: int, now: datetime) -> None: ...

    def mark_failed(
        self,
        *,
        event_id: int,
        kind: FailureKind,
        error: str,
        now: datetime,
    ) -> PipelineEvent:
        """실패를 기록하고 다시 시도할지 정한다.

        영구 실패는 접고, 일시적 실패는 물러났다가 다시 나타난다. 판단은
        도메인의 `resolve_failure`가 한다.
        """
        ...
