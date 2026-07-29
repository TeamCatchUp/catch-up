from __future__ import annotations

from collections.abc import Callable
from collections.abc import Iterator

import pytest
from sqlalchemy import Engine
from sqlalchemy import create_engine
from sqlalchemy import inspect
from sqlalchemy import select
from sqlalchemy import text
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
from catchup.knowledge_maintenance.domain.knowledge_candidate import (
    EntityResolutionStatus,
)
from catchup.knowledge_maintenance.services.store_knowledge_candidates import (
    store_knowledge_candidates,
)
from catchup.tests.knowledge_maintenance.test_postgres_knowledge_candidate_repository import (  # noqa: E501
    SOURCE_TYPE,
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


def _stored_candidates(workspace_id, session_factory, uow_factory):
    """후보 한 벌을 실제로 저장하고 배치를 돌려준다."""
    observation = _stored_observation(workspace_id, session_factory)
    return store_knowledge_candidates(
        observation,
        _batch(),
        spec=SPEC,
        uow=uow_factory(),
    ).batch


def test_find_pending_returns_source_type_and_payload(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """pending 후보가 source_type과 raw_payload를 갖고 조회된다."""
    stored = _stored_candidates(workspace_id, session_factory, uow_factory)

    with uow_factory() as uow:
        pending = uow.knowledge_candidates.find_pending_entity_candidates(
            workspace_id=workspace_id,
        )

    ids = {candidate.id for candidate in pending}
    assert set(stored.entity_ids.values()) <= ids
    sample = next(c for c in pending if c.id == stored.entity_ids["m1"])
    assert sample.source_type == SOURCE_TYPE
    assert sample.raw_payload["attributes"]["external_key"] == "user-abc"
    assert sample.extraction_method.value == "deterministic"


def test_mark_entity_resolved_excludes_from_pending(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """해소된 후보는 pending 조회에서 빠진다."""
    stored = _stored_candidates(workspace_id, session_factory, uow_factory)
    target = stored.entity_ids["m1"]

    with uow_factory() as uow:
        node = uow.knowledge_nodes.create_entity_node(
            workspace_id=workspace_id,
            entity_type="channel_talk_user",
            canonical_key=f"{SOURCE_TYPE}:channel_talk_user:user-abc",
            display_name="사용자 008",
        )
        uow.knowledge_candidates.mark_entity_resolved(
            candidate_id=target,
            status=EntityResolutionStatus.ACCEPTED,
            resolved_node_id=node.id,
        )
        uow.commit()

    with uow_factory() as uow:
        pending_ids = {
            c.id
            for c in uow.knowledge_candidates.find_pending_entity_candidates(
                workspace_id=workspace_id,
            )
        }
    assert target not in pending_ids


def test_entity_node_roundtrip_by_canonical_key(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """canonical key로 만든 entity 노드를 같은 key로 되찾는다."""
    key = f"{SOURCE_TYPE}:channel_talk_manager:manager-xyz"
    with uow_factory() as uow:
        created = uow.knowledge_nodes.create_entity_node(
            workspace_id=workspace_id,
            entity_type="channel_talk_manager",
            canonical_key=key,
            display_name="캐치업 팀",
        )
        uow.commit()

    with uow_factory() as uow:
        found = uow.knowledge_nodes.get_entity_by_canonical_key(
            workspace_id=workspace_id,
            canonical_key=key,
        )
    assert found is not None
    assert found.id == created.id
    assert found.entity_type == "channel_talk_manager"


def test_add_alias_ignores_duplicates(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """같은 정규화 alias를 다시 넣어도 조용히 넘어간다."""
    with uow_factory() as uow:
        node = uow.knowledge_nodes.create_entity_node(
            workspace_id=workspace_id,
            entity_type="channel_talk_manager",
            canonical_key=f"{SOURCE_TYPE}:channel_talk_manager:m-1",
            display_name="캐치업 팀",
        )
        uow.knowledge_nodes.add_alias(
            workspace_id=workspace_id,
            node_id=node.id,
            alias="캐치업 팀",
            normalized_alias="캐치업 팀",
            source="source",
        )
        uow.knowledge_nodes.add_alias(
            workspace_id=workspace_id,
            node_id=node.id,
            alias="캐치업 팀",
            normalized_alias="캐치업 팀",
            source="source",
        )
        uow.commit()

    with session_factory() as session:
        count = len(
            session.scalars(
                select(AliasRow).where(AliasRow.node_id == node.id)
            ).all()
        )
    assert count == 1


def test_duplicate_proposal_roundtrip_and_abandon(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """병합 proposal이 operation과 함께 저장되고 abandon으로 접힌다."""
    stored = _stored_candidates(workspace_id, session_factory, uow_factory)
    representative = stored.entity_ids["e1"]
    other = stored.entity_ids["e2"]

    with uow_factory() as uow:
        proposal_id = uow.mutation_proposals.add_duplicate_proposal(
            workspace_id=workspace_id,
            idempotency_key="결제 기능",
            trigger_entity_candidate_id=representative,
            detector="catchup.name_group_judge",
            detector_version="1",
            summary="같은 이름 후보 병합",
            resolver_metadata={"member_hash": "abc"},
            representative_candidate_id=representative,
            merge_candidate_ids=(other,),
            proposed_type="feature",
            proposed_name="결제 기능",
        )
        uow.commit()

    with uow_factory() as uow:
        found = uow.mutation_proposals.find_pending_by_idempotency_key(
            workspace_id=workspace_id,
            idempotency_key="결제 기능",
        )
    assert found is not None
    assert found.id == proposal_id
    assert found.resolver_metadata["member_hash"] == "abc"

    with session_factory() as session:
        operations = session.scalars(
            select(OperationRow)
            .where(OperationRow.proposal_id == proposal_id)
            .order_by(OperationRow.sequence)
        ).all()
    assert [op.operation_type for op in operations] == [
        "create_entity",
        "merge_entity",
    ]
    assert operations[0].operation_data["proposed_type"] == "feature"
    assert operations[1].operation_data["merge_into_sequence"] == 1

    with uow_factory() as uow:
        uow.mutation_proposals.abandon(proposal_id=proposal_id)
        uow.commit()

    with uow_factory() as uow:
        assert (
            uow.mutation_proposals.find_pending_by_idempotency_key(
                workspace_id=workspace_id,
                idempotency_key="결제 기능",
            )
            is None
        )
