from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from catchup.knowledge_maintenance.domain.observation import StoredObservation
from catchup.knowledge_maintenance.domain.source_version import SourceVersion
from catchup.knowledge_maintenance.ports.observation_normalizer import (
    ObservationNormalizer,
)
from catchup.knowledge_maintenance.ports.observations import ObservationUnitOfWork


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
        uow.commit()
        return SourceVersionNormalizationResult(
            observation=stored,
            result=NormalizationResult.CREATED,
        )
