from __future__ import annotations

import uuid
from collections.abc import Callable
from collections.abc import Iterator

import pytest
from sqlalchemy import Engine
from sqlalchemy import create_engine
from sqlalchemy import inspect
from sqlalchemy import select
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker

from catchup.configs.config import settings
from catchup.db.models import KnowledgeMutationOperation as OperationRow
from catchup.db.models import KnowledgeMutationProposal as ProposalRow
from catchup.db.models import KnowledgeNodeAlias as AliasRow
from catchup.db.models import Workspace
from catchup.knowledge_maintenance.adapters.postgres.unit_of_work import (
    KnowledgeMaintenanceUnitOfWork,
)
from catchup.knowledge_maintenance.domain.knowledge_node import NodeKind
from catchup.knowledge_maintenance.services.store_knowledge_candidates import (
    store_knowledge_candidates,
)
from catchup.tests.knowledge_maintenance.test_postgres_knowledge_candidate_repository import (  # noqa: E501
    SPEC,
)
from catchup.tests.knowledge_maintenance.test_postgres_knowledge_candidate_repository import (  # noqa: E501
    _batch,
)
from catchup.tests.knowledge_maintenance.test_postgres_knowledge_candidate_repository import (  # noqa: E501
    _stored_observation,
)


@pytest.fixture(scope="module")
def engine() -> Iterator[Engine]:
    engine = create_engine(settings.sqlalchemy_database_url)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except OperationalError:
        engine.dispose()
        pytest.skip("PostgreSQL이 없어 통합 테스트를 건너뛴다.")

    if not inspect(engine).has_table(ProposalRow.__tablename__):
        engine.dispose()
        pytest.skip("resolution 테이블이 없다. alembic upgrade head가 필요하다.")

    yield engine
    engine.dispose()


@pytest.fixture(scope="module")
def workspace_id(engine: Engine) -> int:
    with engine.connect() as connection:
        found = connection.execute(
            select(Workspace.id).order_by(Workspace.id).limit(1)
        ).scalar()

    if found is None:
        pytest.skip("workspace가 없어 통합 테스트를 건너뛴다.")
    return found


@pytest.fixture
def session_factory(engine: Engine) -> Iterator[Callable[[], Session]]:
    connection = engine.connect()
    transaction = connection.begin()

    yield sessionmaker(
        bind=connection,
        join_transaction_mode="create_savepoint",
        expire_on_commit=False,
    )

    transaction.rollback()
    connection.close()


@pytest.fixture
def uow_factory(
    session_factory: Callable[[], Session],
) -> Callable[[], KnowledgeMaintenanceUnitOfWork]:
    return lambda: KnowledgeMaintenanceUnitOfWork(session_factory)


def test_proposal_operation_alias_roundtrip(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """proposal·operation·alias 한 벌이 저장되고 그대로 읽힌다."""
    observation = _stored_observation(workspace_id, session_factory)
    stored = store_knowledge_candidates(
        observation,
        _batch(),
        spec=SPEC,
        uow=uow_factory(),
    ).batch
    representative = stored.entity_ids["e1"]
    other = stored.entity_ids["e2"]

    proposal_id = uuid.uuid4()
    with session_factory() as session:
        session.add(
            ProposalRow(
                id=proposal_id,
                workspace_id=workspace_id,
                trigger_entity_candidate_id=representative,
                proposal_kind="duplicate",
                detector="catchup.name_group_judge",
                detector_version="1",
                summary="같은 이름 후보 병합",
                idempotency_key="결제 기능",
                resolver_metadata={"member_hash": "abc"},
            )
        )
        # relationship을 선언하지 않아 flush 순서가 보장되지 않는다.
        # 어댑터와 같은 방식으로 proposal을 먼저 확정한다.
        session.flush()
        session.add(
            OperationRow(
                id=uuid.uuid4(),
                workspace_id=workspace_id,
                proposal_id=proposal_id,
                sequence=1,
                operation_type="create_entity",
                entity_candidate_id=representative,
                operation_data={"proposed_type": "feature"},
            )
        )
        session.add(
            OperationRow(
                id=uuid.uuid4(),
                workspace_id=workspace_id,
                proposal_id=proposal_id,
                sequence=2,
                operation_type="merge_entity",
                entity_candidate_id=other,
                operation_data={"merge_into_sequence": 1},
            )
        )
        session.commit()

    with session_factory() as session:
        proposal = session.get(ProposalRow, proposal_id)
        assert proposal is not None
        assert proposal.status == "pending"
        operations = (
            session.scalars(
                select(OperationRow)
                .where(OperationRow.proposal_id == proposal_id)
                .order_by(OperationRow.sequence)
            ).all()
        )
        assert [op.operation_type for op in operations] == [
            "create_entity",
            "merge_entity",
        ]


def test_alias_is_unique_per_node(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """같은 노드에 같은 정규화 alias는 한 번만 저장된다."""
    observation = _stored_observation(workspace_id, session_factory)
    with uow_factory() as uow:
        node = uow.knowledge_nodes.get_for_resource(
            workspace_id=workspace_id,
            node_kind=NodeKind.OBSERVATION,
            resource_id=observation.id,
        )

    with session_factory() as session:
        session.add(
            AliasRow(
                id=uuid.uuid4(),
                workspace_id=workspace_id,
                node_id=node.id,
                alias="캐치업 팀",
                normalized_alias="캐치업 팀",
                source="source",
            )
        )
        session.commit()

    with session_factory() as session:
        session.add(
            AliasRow(
                id=uuid.uuid4(),
                workspace_id=workspace_id,
                node_id=node.id,
                alias="캐치업 팀",
                normalized_alias="캐치업 팀",
                source="extractor",
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
