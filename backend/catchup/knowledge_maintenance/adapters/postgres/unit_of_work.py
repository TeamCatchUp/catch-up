from __future__ import annotations

from collections.abc import Callable
from types import TracebackType
from typing import Self

from sqlalchemy.orm import Session

from catchup.knowledge_maintenance.adapters.postgres.repositories import (
    SqlAlchemyKnowledgeCandidateRepository,
)
from catchup.knowledge_maintenance.adapters.postgres.repositories import (
    SqlAlchemyKnowledgeNodeRepository,
)
from catchup.knowledge_maintenance.adapters.postgres.repositories import (
    SqlAlchemyObservationRepository,
)
from catchup.knowledge_maintenance.adapters.postgres.repositories import (
    SqlAlchemyOntologyRepository,
)
from catchup.knowledge_maintenance.adapters.postgres.repositories import (
    SqlAlchemySourceVersionRepository,
)


class KnowledgeMaintenanceUnitOfWork:
    """Knowledge Maintenance의 transaction 경계를 SQLAlchemy session으로 구현한다.

    SourceVersion과 Observation과 node identity를 같은 session에 둔다. record를
    저장하는 일과 그것을 graph에 올리는 일은 하나의 transaction이어야 하며,
    나뉘면 record는 있는데 graph에서 가리킬 수 없는 상태가 남을 수 있기
    때문이다. 초안의 트랜잭션 경계 T1이 이것을 요구한다.
    """

    source_versions: SqlAlchemySourceVersionRepository
    observations: SqlAlchemyObservationRepository
    knowledge_nodes: SqlAlchemyKnowledgeNodeRepository
    knowledge_candidates: SqlAlchemyKnowledgeCandidateRepository
    ontology: SqlAlchemyOntologyRepository

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory
        self._session: Session | None = None

    def __enter__(self) -> Self:
        session = self._session_factory()
        self._session = session
        self.source_versions = SqlAlchemySourceVersionRepository(session)
        self.observations = SqlAlchemyObservationRepository(session)
        self.knowledge_nodes = SqlAlchemyKnowledgeNodeRepository(session)
        self.knowledge_candidates = SqlAlchemyKnowledgeCandidateRepository(session)
        self.ontology = SqlAlchemyOntologyRepository(session)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        session = self._session
        self._session = None
        if session is None:
            return
        # commit하지 않고 빠져나간 변경은 남기지 않는다.
        session.rollback()
        session.close()

    def commit(self) -> None:
        """현재 transaction을 커밋한다."""
        if self._session is None:
            raise RuntimeError("UnitOfWork를 with 블록 안에서 사용해야 한다.")
        self._session.commit()
