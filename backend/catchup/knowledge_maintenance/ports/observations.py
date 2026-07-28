from __future__ import annotations

import uuid
from types import TracebackType
from typing import Protocol
from typing import Self

from catchup.knowledge_maintenance.domain.observation import NormalizedObservation
from catchup.knowledge_maintenance.domain.observation import StoredObservation
from catchup.knowledge_maintenance.ports.knowledge_nodes import KnowledgeNodeRepository


class ObservationRepository(Protocol):
    """정규화 결과의 영속성 기능을 정의한다.

    같은 원문을 같은 정규화 계약으로 두 번 처리하면 새 행을 만들지 않는다.
    정규화에는 LLM이 없어 결과가 같기 때문이며, 이를 판정하는 기준이
    `normalizer_id`와 `normalizer_version`이다.
    """

    def get_by_normalizer(
        self,
        *,
        workspace_id: int,
        source_version_id: uuid.UUID,
        normalizer_id: str,
        normalizer_version: str,
    ) -> StoredObservation | None: ...

    def list_for_source_version(
        self,
        *,
        workspace_id: int,
        source_version_id: uuid.UUID,
    ) -> tuple[StoredObservation, ...]: ...

    def list_without_extraction_run(
        self,
        *,
        workspace_id: int,
        limit: int | None = None,
    ) -> tuple[StoredObservation, ...]:
        """아직 추출을 돌리지 않은 Observation을 찾는다.

        graph node가 있고 그 node를 입력으로 삼은 실행이 없는 것들이다.
        추출을 중간에 멈췄다 다시 돌려도 한 일을 되풀이하지 않게 한다.
        """
        ...

    def add(
        self,
        *,
        workspace_id: int,
        source_version_id: uuid.UUID,
        observation: NormalizedObservation,
    ) -> StoredObservation: ...


class ObservationUnitOfWork(Protocol):
    """정규화 결과 저장에 필요한 transaction 경계를 정의한다.

    SourceVersion 수집 경계와 따로 두는 이유는 정규화가 원문을 읽기만 하기
    때문이다. 구현은 하나의 session으로 둘 다 만족시킨다.
    """

    observations: ObservationRepository
    knowledge_nodes: KnowledgeNodeRepository

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    def commit(self) -> None: ...
