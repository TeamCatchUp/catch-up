from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from catchup.knowledge_maintenance.domain.knowledge_node import NodeKind
from catchup.knowledge_maintenance.domain.observation import StoredObservation
from catchup.knowledge_maintenance.domain.source_version import SourceVersion
from catchup.knowledge_maintenance.ports.observation_normalizer import (
    ObservationNormalizer,
)
from catchup.knowledge_maintenance.ports.observations import ObservationUnitOfWork
from catchup.observability.logging import get_logger

logger = get_logger(__name__)


class NormalizationResult(StrEnum):
    CREATED = "created"
    REUSED = "reused"


@dataclass(frozen=True, slots=True)
class SourceVersionNormalizationResult:
    """정규화 결과를 표현한다.

    Attributes:
        observation: 새로 만들었거나 이미 있던 Observation을 담는다.
        result: 새로 만들었는지 기존 것을 그대로 썼는지 나타낸다.
    """

    observation: StoredObservation
    result: NormalizationResult


def normalize_source_version(
    source_version: SourceVersion,
    *,
    normalizer: ObservationNormalizer,
    uow: ObservationUnitOfWork,
) -> SourceVersionNormalizationResult:
    """원문 한 버전을 정규화해 Observation을 최대 하나 남긴다.

    같은 원문을 같은 정규화 계약으로 다시 처리하면 새로 만들지 않는다.
    정규화에는 LLM이 없어 결과가 같기 때문이며, 그래서 재실행이 안전하다.
    계약 버전이 올라가면 판정 키가 달라져 새 Observation이 생기고, 기존
    것은 그대로 남는다.
    """
    with uow:
        existing = uow.observations.get_by_normalizer(
            workspace_id=source_version.workspace_id,
            source_version_id=source_version.id,
            normalizer_id=normalizer.normalizer_id,
            normalizer_version=normalizer.normalizer_version,
        )
        if existing is not None:
            # 이미 있으면 아무것도 쓰지 않는다. node는 Observation과 같은
            # transaction에서 만들어지므로 함께 있거나 함께 없다.
            return SourceVersionNormalizationResult(
                observation=existing,
                result=NormalizationResult.REUSED,
            )

        # 정규화를 transaction 안에서 하는 것은 LLM 호출이 없기 때문이다.
        # Extractor는 이 경계 밖에서 돈다.
        observation = normalizer.normalize(source_version)
        stored = uow.observations.add(
            workspace_id=source_version.workspace_id,
            source_version_id=source_version.id,
            observation=observation,
        )
        _ensure_node(stored, uow)
        uow.commit()
        logger.info(
            "observation_normalized",
            workspace_id=source_version.workspace_id,
            source_version_id=str(source_version.id),
            observation_id=str(stored.id),
            normalizer_id=normalizer.normalizer_id,
            normalizer_version=normalizer.normalizer_version,
            observation_kind=observation.observation_kind.value,
            content_length=len(observation.content or ""),
            metadata_entity_count=len(observation.metadata_entities),
        )
        return SourceVersionNormalizationResult(
            observation=stored,
            result=NormalizationResult.CREATED,
        )


def _ensure_node(
    stored: StoredObservation,
    uow: ObservationUnitOfWork,
) -> None:
    """Observation을 graph에서 가리킬 수 있게 node identity를 붙인다.

    ExtractionRun의 `input_node_id`와 근거 링크의 `evidence_node_id`가 이
    node를 가리킨다. 없으면 추출 결과를 저장할 수 없다.
    """
    uow.knowledge_nodes.ensure_for_resource(
        workspace_id=stored.workspace_id,
        node_kind=NodeKind.OBSERVATION,
        resource_id=stored.id,
    )
