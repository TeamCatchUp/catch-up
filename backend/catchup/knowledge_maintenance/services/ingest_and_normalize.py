"""원문 수집과 정규화를 한 transaction으로 묶는다.

초안의 트랜잭션 경계 T1이 요구하는 것이다.

    BEGIN
      SourceVersion insert 또는 idempotent reuse
      Observation insert 또는 idempotent reuse
      두 record의 knowledge_nodes identity insert 또는 reuse
    COMMIT

두 서비스를 따로 부르면 원문만 저장되고 Observation이 없는 상태가 남을 수
있다. 그 원문은 아무 추출의 입력도 되지 못하면서 재수집도 되지 않는다.
전달 키가 이미 쓰였다고 판정되어 다음 폴링이 duplicate로 넘어가기 때문이다.

정규화가 실패하면 원문 저장도 함께 되돌린다. 부분 상태를 만들지 않는 대신,
같은 envelope을 다시 보내면 처음부터 다시 시도한다.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from types import TracebackType
from typing import Protocol
from typing import Self

from catchup.knowledge_maintenance.contracts.source_change import SourceChangeEnvelope
from catchup.knowledge_maintenance.domain.observation import ObservationKind
from catchup.knowledge_maintenance.domain.pipeline_event import PipelineAggregateType
from catchup.knowledge_maintenance.domain.pipeline_event import PipelineEventType
from catchup.knowledge_maintenance.ports.knowledge_nodes import KnowledgeNodeRepository
from catchup.knowledge_maintenance.ports.observation_normalizer import (
    ObservationNormalizer,
)
from catchup.knowledge_maintenance.ports.observations import ObservationRepository
from catchup.knowledge_maintenance.ports.pipeline_events import PipelineEventRepository
from catchup.knowledge_maintenance.ports.source_versions import SourceVersionRepository
from catchup.knowledge_maintenance.services.ingest_source_version import IngestionResult
from catchup.knowledge_maintenance.services.ingest_source_version import (
    ingest_within_transaction,
)
from catchup.knowledge_maintenance.services.normalize_source_version import (
    NormalizationResult,
)
from catchup.knowledge_maintenance.services.normalize_source_version import (
    normalize_within_transaction,
)
from catchup.observability.logging import get_logger

logger = get_logger(__name__)


class SourceIntakeUnitOfWork(Protocol):
    """수집과 정규화가 함께 쓰는 transaction 경계를 정의한다."""

    source_versions: SourceVersionRepository
    observations: ObservationRepository
    knowledge_nodes: KnowledgeNodeRepository
    pipeline_events: PipelineEventRepository

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    def commit(self) -> None: ...


@dataclass(frozen=True, slots=True)
class SourceIntakeResult:
    """수집과 정규화를 함께 마친 결과를 표현한다.

    Attributes:
        source_version_id: 저장됐거나 이미 있던 원문을 식별한다.
        observation_id: 그 원문의 Observation을 식별한다.
        ingestion: 원문이 새로 저장됐는지 나타낸다.
        normalization: Observation이 새로 만들어졌는지 나타낸다.
    """

    source_version_id: uuid.UUID
    observation_id: uuid.UUID
    ingestion: IngestionResult
    normalization: NormalizationResult


def ingest_and_normalize(
    envelope: SourceChangeEnvelope,
    *,
    normalizer: ObservationNormalizer,
    uow: SourceIntakeUnitOfWork,
    id_factory: Callable[[], uuid.UUID] = uuid.uuid4,
    clock: Callable[[], datetime] | None = None,
) -> SourceIntakeResult:
    """Envelope 하나를 받아 원문과 Observation을 함께 확정한다."""
    with uow:
        ingested = ingest_within_transaction(
            envelope,
            uow=uow,
            id_factory=id_factory,
            clock=clock,
        )
        normalized = normalize_within_transaction(
            ingested.source_version,
            normalizer=normalizer,
            uow=uow,
        )
        # 같은 transaction에서 다음 단계 지시를 적는다. 원문이 확정됐는데
        # 처리하라는 지시만 유실되는 경우를 없앤다.
        #
        # 삭제 표식은 추출 대상이 아니다. 본문이 없어 Extractor가 계약 위반을
        # 내고, 재시도 끝에 실패로 남을 뿐 아무 일도 일어나지 않는다. 삭제는
        # 빈 문서에서 지식을 뽑는 일이 아니라 기존 근거가 사라졌다는 사건이며,
        # 그 무효화는 Resolution이 tombstone Observation을 보고 처리한다.
        queued = None
        if normalized.observation.observation.observation_kind is not (
            ObservationKind.TOMBSTONE
        ):
            queued = uow.pipeline_events.enqueue(
                workspace_id=envelope.workspace_id,
                event_type=PipelineEventType.OBSERVATION_READY,
                aggregate_type=PipelineAggregateType.OBSERVATION,
                aggregate_id=normalized.observation.id,
            )
        uow.commit()

    logger.info(
        "source_intake_completed",
        workspace_id=envelope.workspace_id,
        source_type=envelope.source_type,
        source_version_id=str(ingested.source_version.id),
        observation_id=str(normalized.observation.id),
        ingestion=ingested.result.value,
        normalization=normalized.result.value,
        queued=queued is not None,
    )
    return SourceIntakeResult(
        source_version_id=ingested.source_version.id,
        observation_id=normalized.observation.id,
        ingestion=ingested.result,
        normalization=normalized.result,
    )
