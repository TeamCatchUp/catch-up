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
from sqlalchemy import update
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker

from catchup.configs.config import settings
from catchup.db.models import KnowledgeClaimCandidate as ClaimRow
from catchup.db.models import KnowledgeMutationOperation as OperationRow
from catchup.db.models import KnowledgeMutationProposal as ProposalRow
from catchup.db.models import Workspace
from catchup.knowledge_maintenance.adapters.postgres.unit_of_work import (
    KnowledgeMaintenanceUnitOfWork,
)
from catchup.knowledge_maintenance.contracts.extraction import ExtractionVocabulary
from catchup.knowledge_maintenance.contracts.extraction import PredicateEntry
from catchup.knowledge_maintenance.domain.knowledge_candidate import (
    EntityResolutionStatus,
)
from catchup.knowledge_maintenance.services.resolve_claim_conflicts import (
    conflict_idempotency_key,
)
from catchup.knowledge_maintenance.services.resolve_claim_conflicts import (
    resolve_claim_conflicts,
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


def test_contradiction_proposal_roundtrip_and_replacement(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """contradiction proposal이 저장되고 같은 key로 교체된다."""
    stored = _stored_candidates(workspace_id, session_factory, uow_factory)
    trigger = stored.claim_ids["c1"]
    key = f"contradiction:{uuid.uuid4().hex}"

    with uow_factory() as uow:
        first_id = uow.mutation_proposals.add_contradiction_proposal(
            workspace_id=workspace_id,
            idempotency_key=key,
            trigger_claim_candidate_id=trigger,
            detector="catchup.claim_conflict",
            detector_version="1",
            summary="같은 속성에 값이 둘이다",
            resolver_metadata={"predicate": "release_month"},
        )
        uow.commit()

    with uow_factory() as uow:
        found = uow.mutation_proposals.find_pending_by_idempotency_key(
            workspace_id=workspace_id,
            idempotency_key=key,
        )
    assert found is not None
    assert found.id == first_id
    assert found.resolver_metadata["predicate"] == "release_month"

    with session_factory() as session:
        row = session.get(ProposalRow, first_id)
        assert row is not None
        assert row.proposal_kind == "contradiction"
        assert row.trigger_claim_candidate_id == trigger
        assert row.trigger_entity_candidate_id is None
        # 모순 계획서는 적용 명령을 만들지 않는다.
        assert (
            session.scalars(
                select(OperationRow).where(
                    OperationRow.proposal_id == first_id
                )
            ).all()
            == []
        )

    # abandoned 행이 key를 계속 차지하므로 되살려 교체해야 한다.
    with uow_factory() as uow:
        uow.mutation_proposals.abandon(proposal_id=first_id)
        uow.commit()

    with uow_factory() as uow:
        second_id = uow.mutation_proposals.add_contradiction_proposal(
            workspace_id=workspace_id,
            idempotency_key=key,
            trigger_claim_candidate_id=trigger,
            detector="catchup.claim_conflict",
            detector_version="1",
            summary="값이 달라진 새 모순",
            resolver_metadata={"predicate": "release_month", "round": "2"},
        )
        uow.commit()

    assert second_id == first_id

    with uow_factory() as uow:
        replaced = uow.mutation_proposals.find_pending_by_idempotency_key(
            workspace_id=workspace_id,
            idempotency_key=key,
        )
    assert replaced is not None
    assert replaced.id == second_id
    assert replaced.resolver_metadata["round"] == "2"

    with session_factory() as session:
        assert (
            session.scalars(
                select(OperationRow).where(
                    OperationRow.proposal_id == second_id
                )
            ).all()
            == []
        )


def test_contradiction_proposal_replaces_duplicate_row_triggers(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """entity trigger로 쓰던 key를 claim trigger로 갈아끼워도 CHECK를 지킨다.

    trigger 셋 중 정확히 하나만 채워야 하므로, 교체 시 이전 entity trigger를
    비우지 않으면 저장이 통째로 실패한다.
    """
    stored = _stored_candidates(workspace_id, session_factory, uow_factory)
    representative = stored.entity_ids["e1"]
    other = stored.entity_ids["e2"]
    trigger = stored.claim_ids["c1"]
    key = f"shared-key:{uuid.uuid4().hex}"

    with uow_factory() as uow:
        uow.mutation_proposals.add_duplicate_proposal(
            workspace_id=workspace_id,
            idempotency_key=key,
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
        proposal_id = uow.mutation_proposals.add_contradiction_proposal(
            workspace_id=workspace_id,
            idempotency_key=key,
            trigger_claim_candidate_id=trigger,
            detector="catchup.claim_conflict",
            detector_version="1",
            summary="모순으로 다시 씀",
            resolver_metadata={},
        )
        uow.commit()

    with session_factory() as session:
        row = session.get(ProposalRow, proposal_id)
        assert row is not None
        assert row.proposal_kind == "contradiction"
        assert row.trigger_entity_candidate_id is None
        assert row.trigger_claim_candidate_id == trigger
        # 이전 계획서의 operation은 남으면 안 된다.
        assert (
            session.scalars(
                select(OperationRow).where(
                    OperationRow.proposal_id == proposal_id
                )
            ).all()
            == []
        )


def test_find_claim_candidates_carries_observed_at_and_resolution(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """claim이 관찰 시각과 subject 해소 결과를 갖고 조회된다."""
    stored = _stored_candidates(workspace_id, session_factory, uow_factory)
    claim_id = stored.claim_ids["c1"]
    subject = stored.entity_ids["e1"]

    with uow_factory() as uow:
        claims = uow.knowledge_candidates.find_claim_candidates(
            workspace_id=workspace_id,
        )
    found = next(claim for claim in claims if claim.id == claim_id)
    assert found.subject_entity_candidate_id == subject
    assert found.subject_node_id is None
    assert found.subject_resolved_node_id is None
    assert found.predicate == "release_month"
    assert found.value == "2026-09"
    assert found.statement == "9월 예정입니다."
    assert found.observed_at is not None
    assert found.observed_at.tzinfo is not None

    with uow_factory() as uow:
        node = uow.knowledge_nodes.create_entity_node(
            workspace_id=workspace_id,
            entity_type="feature",
            canonical_key=f"{SOURCE_TYPE}:feature:{uuid.uuid4().hex}",
            display_name="결제 기능",
        )
        uow.knowledge_candidates.mark_entity_resolved(
            candidate_id=subject,
            status=EntityResolutionStatus.ACCEPTED,
            resolved_node_id=node.id,
            expected_node_id=None,
        )
        uow.commit()

    with uow_factory() as uow:
        claims = uow.knowledge_candidates.find_claim_candidates(
            workspace_id=workspace_id,
        )
    found = next(claim for claim in claims if claim.id == claim_id)
    assert found.subject_resolved_node_id == node.id


def test_find_pending_duplicate_groups_maps_members_to_proposal(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """pending 병합 계획서의 멤버가 계획서 id로 되짚힌다."""
    stored = _stored_candidates(workspace_id, session_factory, uow_factory)
    representative = stored.entity_ids["e1"]
    other = stored.entity_ids["e2"]
    key = f"group:{uuid.uuid4().hex}"

    with uow_factory() as uow:
        proposal_id = uow.mutation_proposals.add_duplicate_proposal(
            workspace_id=workspace_id,
            idempotency_key=key,
            trigger_entity_candidate_id=representative,
            detector="catchup.name_group_judge",
            detector_version="1",
            summary="같은 이름 후보 병합",
            resolver_metadata={
                "member_ids": [str(representative), str(other)],
                "member_hash": "abc",
            },
            representative_candidate_id=representative,
            merge_candidate_ids=(other,),
            proposed_type="feature",
            proposed_name="결제 기능",
        )
        uow.commit()

    with uow_factory() as uow:
        groups = uow.mutation_proposals.find_pending_duplicate_groups(
            workspace_id=workspace_id,
        )
    assert groups[representative] == proposal_id
    assert groups[other] == proposal_id

    with uow_factory() as uow:
        uow.mutation_proposals.abandon(proposal_id=proposal_id)
        uow.commit()

    with uow_factory() as uow:
        groups = uow.mutation_proposals.find_pending_duplicate_groups(
            workspace_id=workspace_id,
        )
    assert representative not in groups
    assert other not in groups


def test_find_pending_contradiction_proposals_lists_open_rows(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """열려 있는 모순 계획서만 key와 함께 되짚힌다."""
    stored = _stored_candidates(workspace_id, session_factory, uow_factory)
    trigger = stored.claim_ids["c1"]
    representative = stored.entity_ids["e1"]
    other = stored.entity_ids["e2"]
    conflict_key = f"contradiction:{uuid.uuid4().hex}"
    duplicate_key = f"group:{uuid.uuid4().hex}"

    with uow_factory() as uow:
        conflict_id = uow.mutation_proposals.add_contradiction_proposal(
            workspace_id=workspace_id,
            idempotency_key=conflict_key,
            trigger_claim_candidate_id=trigger,
            detector="catchup.claim_value_conflict",
            detector_version="1",
            summary="값이 둘이다",
            resolver_metadata={"predicate": "release_month"},
        )
        uow.mutation_proposals.add_duplicate_proposal(
            workspace_id=workspace_id,
            idempotency_key=duplicate_key,
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
        found = uow.mutation_proposals.find_pending_contradiction_proposals(
            workspace_id=workspace_id,
        )
    # predicate를 함께 돌려줘야 사전이 아직 그 속성을 비교하는지 보고
    # 회수 여부를 정할 수 있다.
    assert (conflict_id, conflict_key, "release_month") in found
    # 병합 계획서는 다른 종류라 회수 대상이 아니다.
    assert duplicate_key not in {key for _, key, _ in found}

    with uow_factory() as uow:
        uow.mutation_proposals.abandon(proposal_id=conflict_id)
        uow.commit()

    with uow_factory() as uow:
        found = uow.mutation_proposals.find_pending_contradiction_proposals(
            workspace_id=workspace_id,
        )
    assert conflict_key not in {key for _, key, _ in found}


def _rewrite_claim(
    session_factory: Callable[[], Session],
    claim_id: uuid.UUID,
    predicate: str,
    value: object,
) -> None:
    """저장된 claim의 predicate와 값을 시나리오에 맞게 바꾼다."""
    with session_factory() as session:
        session.execute(
            update(ClaimRow)
            .where(ClaimRow.id == claim_id)
            .values(predicate=predicate, value_type="number", value=value)
        )
        session.commit()


def test_converged_values_abandon_stale_contradiction_proposal(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """실 DB에서도 값이 수렴하면 재실행이 낡은 계획서를 접는다."""
    predicate = f"conflict_test_{uuid.uuid4().hex[:8]}"
    vocabulary = ExtractionVocabulary(
        snapshot_id="test",
        predicate_entries=(
            PredicateEntry(
                name=predicate,
                definition="테스트용 수치를 나타낸다.",
                value_type="number",
            ),
        ),
    )
    first = _stored_candidates(workspace_id, session_factory, uow_factory)
    second = _stored_candidates(workspace_id, session_factory, uow_factory)

    with uow_factory() as uow:
        node = uow.knowledge_nodes.create_entity_node(
            workspace_id=workspace_id,
            entity_type="feature",
            canonical_key=f"{SOURCE_TYPE}:feature:{uuid.uuid4().hex}",
            display_name="결제 기능",
        )
        for stored in (first, second):
            uow.knowledge_candidates.mark_entity_resolved(
                candidate_id=stored.entity_ids["e1"],
                status=EntityResolutionStatus.ACCEPTED,
                resolved_node_id=node.id,
                expected_node_id=None,
            )
        uow.commit()

    _rewrite_claim(session_factory, first.claim_ids["c1"], predicate, 60)
    _rewrite_claim(session_factory, second.claim_ids["c1"], predicate, 120)

    created = resolve_claim_conflicts(
        workspace_id=workspace_id,
        vocabulary=vocabulary,
        uow=uow_factory(),
    )
    assert created.conflicts_found == 1
    assert created.proposals_created == 1

    key = conflict_idempotency_key(f"node:{node.id}", predicate)
    with uow_factory() as uow:
        opened = uow.mutation_proposals.find_pending_by_idempotency_key(
            workspace_id=workspace_id,
            idempotency_key=key,
        )
    assert opened is not None

    _rewrite_claim(session_factory, second.claim_ids["c1"], predicate, 60)
    recalled = resolve_claim_conflicts(
        workspace_id=workspace_id,
        vocabulary=vocabulary,
        uow=uow_factory(),
    )

    assert recalled.conflicts_found == 0
    assert recalled.proposals_abandoned >= 1
    with uow_factory() as uow:
        still_open = uow.mutation_proposals.find_pending_by_idempotency_key(
            workspace_id=workspace_id,
            idempotency_key=key,
        )
    assert still_open is None
    with session_factory() as session:
        row = session.get(ProposalRow, opened.id)
        assert row is not None
        assert row.status == "abandoned"
