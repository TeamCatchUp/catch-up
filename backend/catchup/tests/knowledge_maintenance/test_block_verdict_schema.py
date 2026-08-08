"""블록 verdict 저널이 딛고 설 스키마 제약을 실 PostgreSQL로 확인한다.

블록 단위 판정은 사람이 남기는 결정 기록이라 사유 없는 반려나 같은 블록
두 번 판정 같은 훼손을 DB가 막아야 한다. fake 저장소는 제약을 흉내내는
쪽이라 제약 문구가 틀려도 드러나지 않으므로 실 DB에 직접 넣어 본다.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from collections.abc import Iterator
from datetime import datetime
from datetime import timezone

import pytest
from sqlalchemy import Engine
from sqlalchemy import create_engine
from sqlalchemy import inspect
from sqlalchemy import select
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker

from catchup.configs.config import settings
from catchup.db.models import KnowledgeArtifact
from catchup.db.models import KnowledgeArtifactChangeProposal as ProposalRow
from catchup.db.models import KnowledgeBlockVerdict
from catchup.db.models import KnowledgeNode as NodeRow
from catchup.db.models import Workspace
from catchup.tests.knowledge_maintenance.test_artifact_schema import (
    _violated_constraint,
)

ARTIFACT_KIND = "entity_summary"


@pytest.fixture(scope="module")
def engine() -> Iterator[Engine]:
    engine = create_engine(settings.sqlalchemy_database_url)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except OperationalError:
        engine.dispose()
        pytest.skip("PostgreSQL이 없어 통합 테스트를 건너뛴다.")

    if not inspect(engine).has_table(KnowledgeBlockVerdict.__tablename__):
        engine.dispose()
        pytest.skip(
            "블록 verdict 테이블이 없다. alembic upgrade head가 필요하다."
        )

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


def _proposal_id(
    session_factory: Callable[[], Session],
    workspace_id: int,
) -> uuid.UUID:
    """판정을 붙일 변경안 한 건을 새로 마련한다."""
    proposal_id = uuid.uuid4()
    artifact_id = uuid.uuid4()
    with session_factory() as session:
        node = NodeRow(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            node_kind="entity",
            entity_type="feature",
            canonical_key=f"test:feature:{uuid.uuid4().hex}",
            display_name="결제 기능",
        )
        session.add(node)
        session.flush()
        session.add(
            KnowledgeArtifact(
                id=artifact_id,
                workspace_id=workspace_id,
                kind=ARTIFACT_KIND,
                subject_node_id=node.id,
                title="결제 기능",
            )
        )
        session.flush()
        session.add(
            ProposalRow(
                id=proposal_id,
                workspace_id=workspace_id,
                artifact_id=artifact_id,
                blocks=[],
                content_hash=uuid.uuid4().hex,
                idempotency_key=uuid.uuid4().hex,
            )
        )
        session.commit()
    return proposal_id


def _verdict(
    workspace_id: int,
    proposal_id: uuid.UUID,
    **overrides: object,
) -> KnowledgeBlockVerdict:
    """필수 컬럼을 채운 블록 판정 행을 만든다."""
    values: dict[str, object] = {
        "id": uuid.uuid4(),
        "workspace_id": workspace_id,
        "proposal_id": proposal_id,
        "block_index": 0,
        "block_content_hash": uuid.uuid4().hex,
        "verdict": "approved",
        "reviewer": "tester",
        "reviewed_at": datetime.now(timezone.utc),
    }
    values.update(overrides)
    return KnowledgeBlockVerdict(**values)


def test_rejected_without_reason_is_blocked(
    workspace_id: int,
    session_factory: Callable[[], Session],
) -> None:
    """반려인데 사유가 없으면 DB가 막는다."""
    proposal_id = _proposal_id(session_factory, workspace_id)

    with session_factory() as session:
        session.add(_verdict(workspace_id, proposal_id, verdict="rejected"))
        with pytest.raises(IntegrityError) as excinfo:
            session.commit()

    assert (
        _violated_constraint(excinfo) == "ck_block_verdict_rejection_reason"
    )


def test_rejected_with_blank_reason_is_blocked(
    workspace_id: int,
    session_factory: Callable[[], Session],
) -> None:
    """사유가 공백뿐이면 사유 없는 반려와 같이 막힌다."""
    proposal_id = _proposal_id(session_factory, workspace_id)

    with session_factory() as session:
        session.add(
            _verdict(
                workspace_id,
                proposal_id,
                verdict="rejected",
                rejection_reason="   ",
            )
        )
        with pytest.raises(IntegrityError) as excinfo:
            session.commit()

    assert (
        _violated_constraint(excinfo) == "ck_block_verdict_rejection_reason"
    )


def test_rejected_with_reason_is_allowed(
    workspace_id: int,
    session_factory: Callable[[], Session],
) -> None:
    """사유가 있으면 반려 판정이 저장된다."""
    proposal_id = _proposal_id(session_factory, workspace_id)
    row = _verdict(
        workspace_id,
        proposal_id,
        verdict="rejected",
        rejection_reason="근거가 부족하다.",
    )

    with session_factory() as session:
        session.add(row)
        session.commit()
        stored = session.get(KnowledgeBlockVerdict, row.id)
        assert stored is not None
        assert stored.verdict == "rejected"


def test_unknown_verdict_is_blocked(
    workspace_id: int,
    session_factory: Callable[[], Session],
) -> None:
    """약속되지 않은 판정 값은 DB가 막는다."""
    proposal_id = _proposal_id(session_factory, workspace_id)

    with session_factory() as session:
        session.add(_verdict(workspace_id, proposal_id, verdict="banana"))
        with pytest.raises(IntegrityError) as excinfo:
            session.commit()

    assert _violated_constraint(excinfo) == "ck_block_verdict_kind"


def test_blank_reviewer_is_blocked(
    workspace_id: int,
    session_factory: Callable[[], Session],
) -> None:
    """결정자가 공백뿐이면 결정 기록으로 인정하지 않는다."""
    proposal_id = _proposal_id(session_factory, workspace_id)

    with session_factory() as session:
        session.add(_verdict(workspace_id, proposal_id, reviewer="  "))
        with pytest.raises(IntegrityError) as excinfo:
            session.commit()

    assert _violated_constraint(excinfo) == "ck_block_verdict_reviewer"


def test_duplicate_block_index_is_blocked(
    workspace_id: int,
    session_factory: Callable[[], Session],
) -> None:
    """같은 변경안의 같은 블록에 판정이 둘 생기지 않는다."""
    proposal_id = _proposal_id(session_factory, workspace_id)

    with session_factory() as session:
        session.add(_verdict(workspace_id, proposal_id, block_index=3))
        session.commit()

    with session_factory() as session:
        session.add(_verdict(workspace_id, proposal_id, block_index=3))
        with pytest.raises(IntegrityError) as excinfo:
            session.commit()

    assert _violated_constraint(excinfo) == "uq_block_verdict_proposal_block"


def test_upsert_overwrites_same_block(
    workspace_id: int,
    session_factory: Callable[[], Session],
) -> None:
    """같은 블록을 다시 판정하면 ON CONFLICT로 덮어쓴다.

    사람이 마음을 바꿔 다시 누르는 일이 정상 경로라, 유일 제약이 재판정을
    막지 않고 갱신으로 흡수되는지까지 확인한다.
    """
    proposal_id = _proposal_id(session_factory, workspace_id)
    table = KnowledgeBlockVerdict.__table__
    reviewed_at = datetime.now(timezone.utc)

    with session_factory() as session:
        session.add(_verdict(workspace_id, proposal_id, block_index=1))
        session.commit()

    statement = (
        pg_insert(table)
        .values(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            proposal_id=proposal_id,
            block_index=1,
            block_content_hash="b" * 64,
            verdict="rejected",
            rejection_reason="근거가 낡았다.",
            reviewer="tester2",
            reviewed_at=reviewed_at,
        )
    )
    statement = statement.on_conflict_do_update(
        constraint="uq_block_verdict_proposal_block",
        set_={
            "block_content_hash": statement.excluded.block_content_hash,
            "verdict": statement.excluded.verdict,
            "rejection_reason": statement.excluded.rejection_reason,
            "reviewer": statement.excluded.reviewer,
            "reviewed_at": statement.excluded.reviewed_at,
        },
    )

    with session_factory() as session:
        session.execute(statement)
        session.commit()
        rows = (
            session.execute(
                select(KnowledgeBlockVerdict).where(
                    KnowledgeBlockVerdict.proposal_id == proposal_id
                )
            )
            .scalars()
            .all()
        )

    assert len(rows) == 1
    assert rows[0].verdict == "rejected"
    assert rows[0].reviewer == "tester2"


def test_chosen_winner_claim_id_is_free_of_fk(
    workspace_id: int,
    session_factory: Callable[[], Session],
) -> None:
    """존재하지 않는 claim id도 그대로 기록된다.

    저널은 그때 사람이 무엇을 골랐는지 남기는 쪽이라 claim 수명에 묶이지
    않는다. FK를 걸지 않은 선택이 스키마에 실제로 반영됐는지 본다.
    """
    proposal_id = _proposal_id(session_factory, workspace_id)
    winner_id = uuid.uuid4()
    row = _verdict(
        workspace_id,
        proposal_id,
        block_index=2,
        chosen_winner_claim_id=winner_id,
    )

    with session_factory() as session:
        session.add(row)
        session.commit()
        stored = session.get(KnowledgeBlockVerdict, row.id)
        assert stored is not None
        assert stored.chosen_winner_claim_id == winner_id
