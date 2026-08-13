from __future__ import annotations

from collections.abc import Callable
from types import TracebackType
from typing import Self

from sqlalchemy.orm import Session

from catchup.knowledge_maintenance.adapters.postgres.repositories import (
    SqlAlchemyArtifactDefinitionRepository,
)
from catchup.knowledge_maintenance.adapters.postgres.repositories import (
    SqlAlchemyArtifactRepository,
)
from catchup.knowledge_maintenance.adapters.postgres.repositories import (
    SqlAlchemyBlockVerdictRepository,
)
from catchup.knowledge_maintenance.adapters.postgres.repositories import (
    SqlAlchemyKnowledgeCandidateRepository,
)
from catchup.knowledge_maintenance.adapters.postgres.repositories import (
    SqlAlchemyKnowledgeNodeRepository,
)
from catchup.knowledge_maintenance.adapters.postgres.repositories import (
    SqlAlchemyMutationProposalRepository,
)
from catchup.knowledge_maintenance.adapters.postgres.repositories import (
    SqlAlchemyObservationRepository,
)
from catchup.knowledge_maintenance.adapters.postgres.repositories import (
    SqlAlchemyOntologyRepository,
)
from catchup.knowledge_maintenance.adapters.postgres.repositories import (
    SqlAlchemyPipelineEventRepository,
)
from catchup.knowledge_maintenance.adapters.postgres.repositories import (
    SqlAlchemyRelationRepository,
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
    pipeline_events: SqlAlchemyPipelineEventRepository
    mutation_proposals: SqlAlchemyMutationProposalRepository
    artifacts: SqlAlchemyArtifactRepository
    artifact_definitions: SqlAlchemyArtifactDefinitionRepository
    block_verdicts: SqlAlchemyBlockVerdictRepository
    relations: SqlAlchemyRelationRepository

    def __init__(
        self,
        session_factory: Callable[[], Session],
        *,
        workspace_id: int | None = None,
    ) -> None:
        """transaction 경계를 만든다.

        `workspace_id`는 artifact 저장소와 정의 저장소와 블록 결정
        저장소와 관계 저장소만 쓴다. 다른 저장소는 메서드마다 workspace를 받으므로
        기본값을 두어 기존 호출자를 그대로 둔다. 문서 작업을 하려면
        반드시 넘겨야 하며, 없이 쓰면 저장소가 막는다.

        키워드로만 받는다. 위치 인자로 열어 두면 session factory 자리에
        잘못 넣거나 그 반대로 넣어도 조용히 통과할 자리가 생긴다.
        """
        self._session_factory = session_factory
        self._workspace_id = workspace_id
        self._session: Session | None = None

    @property
    def workspace_id(self) -> int | None:
        """Artifact repository에 고정된 workspace 범위를 돌려준다."""
        return self._workspace_id

    def __enter__(self) -> Self:
        session = self._session_factory()
        self._session = session
        self.source_versions = SqlAlchemySourceVersionRepository(session)
        self.observations = SqlAlchemyObservationRepository(session)
        self.knowledge_nodes = SqlAlchemyKnowledgeNodeRepository(session)
        self.knowledge_candidates = SqlAlchemyKnowledgeCandidateRepository(session)
        self.ontology = SqlAlchemyOntologyRepository(session)
        self.pipeline_events = SqlAlchemyPipelineEventRepository(session)
        self.mutation_proposals = SqlAlchemyMutationProposalRepository(session)
        self.artifacts = SqlAlchemyArtifactRepository(
            session, self._workspace_id
        )
        self.artifact_definitions = SqlAlchemyArtifactDefinitionRepository(
            session, self._workspace_id
        )
        self.block_verdicts = SqlAlchemyBlockVerdictRepository(
            session, self._workspace_id
        )
        self.relations = SqlAlchemyRelationRepository(
            session, self._workspace_id
        )
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
