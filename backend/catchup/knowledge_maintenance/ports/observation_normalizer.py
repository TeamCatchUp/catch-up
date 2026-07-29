from __future__ import annotations

from typing import Protocol

from catchup.knowledge_maintenance.domain.observation import NormalizedObservation
from catchup.knowledge_maintenance.domain.source_version import SourceVersion


class ObservationNormalizer(Protocol):
    """원문 한 버전을 Extractor가 읽을 형태로 정규화하는 경계를 정의한다.

    정규화 포맷은 source마다 다르므로 구현은 adapter가 소유한다. 계약 버전도
    adapter가 정하며, 그래서 `normalizer_id`와 `normalizer_version`이 port의
    속성으로 드러난다. 같은 SourceVersion이라도 이 둘이 달라지면 새로운
    Observation이 되고 기존 것을 덮지 않는다.

    LLM을 쓰지 않는다. 같은 입력이면 언제나 같은 결과를 내야 한다.
    """

    normalizer_id: str
    normalizer_version: str

    def normalize(self, source_version: SourceVersion) -> NormalizedObservation: ...
