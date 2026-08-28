"""mutation proposal 결정 컬럼의 제약을 실 PostgreSQL에서 확인한다.

병합 안건의 결정(approved/rejected)은 감사 기록이므로 제약은 DB가
강제해야 한다. 모델 정의만 믿으면 마이그레이션이 빠졌을 때 알아채지
못하므로 실제 스키마에 넣어 본다.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from collections.abc import Iterator
from datetime import UTC
from datetime import datetime

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
from catchup.db.models import KnowledgeMutationProposal as ProposalRow
from catchup.db.models import Workspace
from catchup.knowledge_maintenance.adapters.postgres.unit_of_work import (
    KnowledgeMaintenanceUnitOfWork,
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

DECIDED_AT = datetime(2026, 8, 3, 12, 0, tzinfo=UTC)


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
        pytest.skip("proposal 테이블이 없다. alembic upgrade head가 필요하다.")

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


def _trigger_claim_id(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> uuid.UUID:
    """proposal의 트리거로 쓸 claim 후보를 실제로 저장한다."""
    observation = _stored_observation(workspace_id, session_factory)
    stored = store_knowledge_candidates(
        observation,
        _batch(),
        spec=SPEC,
        uow=uow_factory(),
    ).batch
    return next(iter(stored.claim_ids.values()))


def _proposal(
    workspace_id: int,
    trigger_claim_id: uuid.UUID,
    **overrides: object,
) -> ProposalRow:
    """기본값이 채워진 mutation proposal 행을 만든다."""
    values: dict[str, object] = {
        "id": uuid.uuid4(),
        "workspace_id": workspace_id,
        "trigger_claim_candidate_id": trigger_claim_id,
        "proposal_kind": "contradiction",
        "detector": "test.detector",
        "detector_version": "1",
        "summary": "테스트 안건",
        "idempotency_key": f"test:{uuid.uuid4().hex}",
        "resolver_metadata": {},
    }
    values.update(overrides)
    return ProposalRow(**values)


def _violated_constraint(excinfo: pytest.ExceptionInfo[IntegrityError]) -> str:
    """터진 제약의 이름을 꺼낸다."""
    original = excinfo.value.orig
    diagnostic = getattr(original, "diag", None)
    name = getattr(diagnostic, "constraint_name", None)
    if name:
        return name
    return str(original)


def test_rejected_requires_reason(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """반려에는 사유가 DB 수준에서 강제된다."""
    trigger = _trigger_claim_id(workspace_id, session_factory, uow_factory)
    with session_factory() as session:
        session.add(
            _proposal(
                workspace_id,
                trigger,
                status="rejected",
                reviewer="tester",
                reviewed_at=DECIDED_AT,
                rejection_reason=None,
            )
        )
        with pytest.raises(IntegrityError) as excinfo:
            session.flush()
    assert (
        _violated_constraint(excinfo)
        == "ck_knowledge_mutation_proposals_rejection_reason"
    )


def test_decision_statuses_are_accepted(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """approved와 rejected가 status CHECK를 통과한다."""
    trigger = _trigger_claim_id(workspace_id, session_factory, uow_factory)
    with session_factory() as session:
        session.add(
            _proposal(
                workspace_id,
                trigger,
                status="approved",
                reviewer="tester",
                reviewed_at=DECIDED_AT,
            )
        )
        session.add(
            _proposal(
                workspace_id,
                trigger,
                status="rejected",
                reviewer="tester",
                reviewed_at=DECIDED_AT,
                rejection_reason="근거가 부족하다",
            )
        )
        session.flush()


def test_unknown_status_is_refused(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """정의 밖 status는 CHECK가 막는다."""
    trigger = _trigger_claim_id(workspace_id, session_factory, uow_factory)
    with session_factory() as session:
        session.add(_proposal(workspace_id, trigger, status="bogus"))
        with pytest.raises(IntegrityError) as excinfo:
            session.flush()
    assert (
        _violated_constraint(excinfo)
        == "ck_knowledge_mutation_proposals_status"
    )


def test_decision_without_reviewer_is_refused(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """결정 상태인데 reviewer가 없으면 DB가 거부한다."""
    trigger = _trigger_claim_id(workspace_id, session_factory, uow_factory)
    with session_factory() as session:
        session.add(
            _proposal(
                workspace_id,
                trigger,
                status="approved",
                reviewer=None,
                reviewed_at=DECIDED_AT,
            )
        )
        with pytest.raises(IntegrityError) as excinfo:
            session.flush()
    assert (
        _violated_constraint(excinfo)
        == "ck_knowledge_mutation_proposals_decision_journal"
    )


def test_blank_reviewer_is_refused(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """공백 reviewer는 결정자로 인정되지 않는다."""
    trigger = _trigger_claim_id(workspace_id, session_factory, uow_factory)
    with session_factory() as session:
        session.add(
            _proposal(
                workspace_id,
                trigger,
                status="approved",
                reviewer="   ",
                reviewed_at=DECIDED_AT,
            )
        )
        with pytest.raises(IntegrityError) as excinfo:
            session.flush()
    assert (
        _violated_constraint(excinfo)
        == "ck_knowledge_mutation_proposals_decision_journal"
    )


def test_decision_without_reviewed_at_is_refused(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """결정 상태인데 reviewed_at이 없으면 DB가 거부한다."""
    trigger = _trigger_claim_id(workspace_id, session_factory, uow_factory)
    with session_factory() as session:
        session.add(
            _proposal(
                workspace_id,
                trigger,
                status="rejected",
                reviewer="tester",
                reviewed_at=None,
                rejection_reason="근거가 부족하다",
            )
        )
        with pytest.raises(IntegrityError) as excinfo:
            session.flush()
    assert (
        _violated_constraint(excinfo)
        == "ck_knowledge_mutation_proposals_decision_journal"
    )
