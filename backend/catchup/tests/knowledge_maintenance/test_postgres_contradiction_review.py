"""모순 판정과 구간 닫기를 실 PostgreSQL에서 확인한다.

결정 기록이 판정 근거를 덮지 않는지, 적용 명령이 sequence 순으로 붙는지,
그리고 닫힌 구간이 DB CHECK(valid_to > valid_from)를 통과하는지는 실
스키마 위에서만 증명된다.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from collections.abc import Iterator
from datetime import UTC
from datetime import datetime
from datetime import timedelta

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
from catchup.db.models import KnowledgeClaimCandidate as ClaimRow
from catchup.db.models import KnowledgeMutationOperation as OperationRow
from catchup.db.models import KnowledgeMutationProposal as ProposalRow
from catchup.db.models import Workspace
from catchup.knowledge_maintenance.adapters.postgres.unit_of_work import (
    KnowledgeMaintenanceUnitOfWork,
)
from catchup.knowledge_maintenance.services.apply_mutation_proposals import (
    apply_mutation_proposals,
)
from catchup.knowledge_maintenance.services.review_contradiction_proposal import (
    ContradictionReviewError,
)
from catchup.knowledge_maintenance.services.review_contradiction_proposal import (
    review_contradiction_proposal,
)
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

DECIDED_AT = datetime(2026, 7, 31, 9, 0, tzinfo=UTC)
EARLY = datetime(2026, 7, 1, tzinfo=UTC)
LATER = datetime(2026, 7, 20, tzinfo=UTC)


@pytest.fixture(scope="module")
def engine() -> Iterator[Engine]:
    engine = create_engine(settings.sqlalchemy_database_url)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except OperationalError:
        engine.dispose()
        pytest.skip("PostgreSQL이 없어 통합 테스트를 건너뛴다.")

    columns = {
        column["name"]
        for column in inspect(engine).get_columns(ProposalRow.__tablename__)
    }
    if "reviewer" not in columns:
        engine.dispose()
        pytest.skip("결정 컬럼이 없다. alembic upgrade head가 필요하다.")

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
    workspace_id: int,
) -> Callable[[], KnowledgeMaintenanceUnitOfWork]:
    return lambda: KnowledgeMaintenanceUnitOfWork(
        session_factory, workspace_id=workspace_id
    )


def _contradiction(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
    *,
    winner_valid_from: datetime | None = LATER,
    loser_status: str = "accepted",
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """실 claim 두 건 위에 모순 안건 하나를 만든다."""
    observation = _stored_observation(workspace_id, session_factory)
    stored = store_knowledge_candidates(
        observation,
        _batch(),
        spec=SPEC,
        uow=uow_factory(),
    ).batch
    claim_ids = list(stored.claim_ids.values())
    while len(claim_ids) < 2:
        extra = _stored_observation(workspace_id, session_factory)
        more = store_knowledge_candidates(
            extra, _batch(), spec=SPEC, uow=uow_factory()
        ).batch
        claim_ids.extend(more.claim_ids.values())
    winner, loser = claim_ids[0], claim_ids[1]

    with session_factory() as session:
        winner_row = session.get(ClaimRow, winner)
        loser_row = session.get(ClaimRow, loser)
        assert winner_row is not None and loser_row is not None
        winner_row.resolution_status = "accepted"
        winner_row.valid_from = winner_valid_from
        loser_row.resolution_status = loser_status
        loser_row.valid_from = EARLY if loser_status == "accepted" else None
        session.commit()

    with uow_factory() as uow:
        proposal_id = uow.mutation_proposals.add_contradiction_proposal(
            workspace_id=workspace_id,
            idempotency_key=f"contradiction:{uuid.uuid4().hex}",
            trigger_claim_candidate_id=winner,
            detector="catchup.claim_value_conflict",
            detector_version="1",
            summary="'rate_limit_per_minute' 값이 2종으로 갈린다",
            resolver_metadata={
                "predicate": "rate_limit_per_minute",
                "subject_key": "node:test",
                "member_hash": "abc",
                "values": [
                    {
                        "value": 60,
                        "claim_id": str(winner),
                        "statement": "분당 60회입니다",
                        "normalized": "60.0",
                        "observed_at": EARLY.isoformat(),
                    },
                    {
                        "value": 120,
                        "claim_id": str(loser),
                        "statement": "분당 120회입니다",
                        "normalized": "120.0",
                        "observed_at": EARLY.isoformat(),
                    },
                ],
            },
        )
        uow.commit()
    return proposal_id, winner, loser


def test_decision_preserves_evidence_and_creates_operations(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """결정이 판정 근거를 덮지 않고 명령을 순서대로 만든다."""
    proposal_id, winner, loser = _contradiction(
        workspace_id, session_factory, uow_factory
    )

    result = review_contradiction_proposal(
        uow_factory(),
        workspace_id=workspace_id,
        proposal_id=proposal_id,
        winner_claim_id=winner,
        reviewer="ba2slk",
        now=DECIDED_AT,
    )

    assert result.valid_to == LATER
    assert result.valid_to_source == "winner_valid_from"
    with session_factory() as session:
        row = session.get(ProposalRow, proposal_id)
        operations = session.scalars(
            select(OperationRow)
            .where(OperationRow.proposal_id == proposal_id)
            .order_by(OperationRow.sequence)
        ).all()
    assert row is not None
    assert row.status == "approved"
    assert row.reviewer == "ba2slk"
    assert row.reviewed_at is not None
    # 판정 근거는 그대로 남는다.
    assert row.resolver_metadata["predicate"] == "rate_limit_per_minute"
    assert len(row.resolver_metadata["values"]) == 2
    decision = row.resolver_metadata["decision"]
    assert decision["winner_claim_id"] == str(winner)
    assert decision["loser_claim_ids"] == [str(loser)]
    assert len(operations) == 1
    assert operations[0].sequence == 1
    assert operations[0].operation_type == "supersede_claim"
    assert operations[0].claim_candidate_id == loser
    assert operations[0].operation_data["valid_to"] == LATER.isoformat()


def test_second_decision_is_refused(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """먼저 확정된 판정을 나중 판정이 덮지 못한다."""
    proposal_id, winner, loser = _contradiction(
        workspace_id, session_factory, uow_factory
    )
    review_contradiction_proposal(
        uow_factory(),
        workspace_id=workspace_id,
        proposal_id=proposal_id,
        winner_claim_id=winner,
        reviewer="first",
        now=DECIDED_AT,
    )

    with pytest.raises(ContradictionReviewError):
        review_contradiction_proposal(
            uow_factory(),
            workspace_id=workspace_id,
            proposal_id=proposal_id,
            winner_claim_id=loser,
            reviewer="second",
            now=DECIDED_AT + timedelta(hours=1),
        )

    with session_factory() as session:
        row = session.get(ProposalRow, proposal_id)
        operations = session.scalars(
            select(OperationRow).where(
                OperationRow.proposal_id == proposal_id
            )
        ).all()
    assert row is not None
    assert row.reviewer == "first"
    assert row.resolver_metadata["decision"]["winner_claim_id"] == str(
        winner
    )
    # 진 판정이 명령을 덧붙이지 못한다.
    assert len(operations) == 1


def test_stranger_claim_cannot_win(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """안건 밖의 주장은 승자가 될 수 없다."""
    proposal_id, _winner, _loser = _contradiction(
        workspace_id, session_factory, uow_factory
    )

    with pytest.raises(ContradictionReviewError):
        review_contradiction_proposal(
            uow_factory(),
            workspace_id=workspace_id,
            proposal_id=proposal_id,
            winner_claim_id=uuid.uuid4(),
            reviewer="ba2slk",
            now=DECIDED_AT,
        )

    with session_factory() as session:
        row = session.get(ProposalRow, proposal_id)
    assert row is not None
    assert row.status == "pending"
    assert "decision" not in row.resolver_metadata


def test_apply_closes_loser_interval_on_real_rows(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """판정을 적용하면 패자 구간이 실제로 닫히고 상태는 남는다."""
    proposal_id, winner, loser = _contradiction(
        workspace_id, session_factory, uow_factory
    )
    review_contradiction_proposal(
        uow_factory(),
        workspace_id=workspace_id,
        proposal_id=proposal_id,
        winner_claim_id=winner,
        reviewer="ba2slk",
        now=DECIDED_AT,
    )

    result = apply_mutation_proposals(uow_factory, workspace_id=workspace_id)

    assert result.claims_superseded >= 1
    with session_factory() as session:
        proposal = session.get(ProposalRow, proposal_id)
        loser_row = session.get(ClaimRow, loser)
        winner_row = session.get(ClaimRow, winner)
    assert proposal is not None
    assert proposal.status == "applied"
    assert loser_row is not None and winner_row is not None
    # 한때 참이었다는 사실은 남고 구간만 닫힌다.
    assert loser_row.resolution_status == "accepted"
    assert loser_row.valid_to is not None
    assert loser_row.valid_to > loser_row.valid_from
    assert winner_row.valid_to is None

    rerun = apply_mutation_proposals(uow_factory, workspace_id=workspace_id)
    assert rerun.claims_superseded == 0


def test_apply_rejects_pending_loser_on_real_rows(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """지식이 된 적 없는 패자는 구간 없이 탈락한다."""
    proposal_id, winner, loser = _contradiction(
        workspace_id,
        session_factory,
        uow_factory,
        loser_status="pending",
    )
    review_contradiction_proposal(
        uow_factory(),
        workspace_id=workspace_id,
        proposal_id=proposal_id,
        winner_claim_id=winner,
        reviewer="ba2slk",
        now=DECIDED_AT,
    )

    result = apply_mutation_proposals(uow_factory, workspace_id=workspace_id)

    assert result.claims_invalidated == 1
    with session_factory() as session:
        loser_row = session.get(ClaimRow, loser)
    assert loser_row is not None
    assert loser_row.resolution_status == "rejected"
    assert loser_row.valid_to is None
