"""블록 verdict 저장 포트를 실 PostgreSQL과 fake 양쪽으로 확인한다.

같은 시나리오를 두 구현에 그대로 태운다. fake가 실 DB와 다르게 굴면
서비스 계층 테스트가 초록인 채로 실제 저장에서 깨지기 때문이다. 실 DB
쪽에는 fake가 흉내 낼 수 없는 것 — workspace 교차 참조 차단 — 을 따로
둔다.
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
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker

from catchup.configs.config import settings
from catchup.db.models import KnowledgeArtifact
from catchup.db.models import KnowledgeArtifactChangeProposal as ProposalRow
from catchup.db.models import KnowledgeBlockVerdict
from catchup.db.models import KnowledgeNode as NodeRow
from catchup.db.models import Workspace
from catchup.knowledge_maintenance.adapters.postgres.repositories import (
    SqlAlchemyBlockVerdictRepository,
)
from catchup.knowledge_maintenance.ports.block_verdicts import BlockVerdictRepository
from catchup.tests.knowledge_maintenance.test_review_artifact_proposal import (
    FakeArtifactRepository,
)
from catchup.tests.knowledge_maintenance.test_review_artifact_proposal import (
    FakeBlockVerdictRepository,
)

ARTIFACT_KIND = "entity_summary"
REVIEWER = "tester"
FIRST_AT = datetime(2026, 8, 1, 9, 0, tzinfo=UTC)
SECOND_AT = datetime(2026, 8, 2, 9, 0, tzinfo=UTC)
HASH_A = "a" * 64
HASH_B = "b" * 64
HASH_C = "c" * 64


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


def _proposal(
    session: Session,
    workspace_id: int,
) -> tuple[uuid.UUID, uuid.UUID]:
    """판정을 붙일 문서와 변경안을 하나씩 마련한다."""
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
    artifact_id = uuid.uuid4()
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
    proposal_id = uuid.uuid4()
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
    session.flush()
    return artifact_id, proposal_id


def _other_workspace(session: Session, workspace_id: int) -> int:
    """같은 회사 안에 workspace를 하나 더 만든다."""
    company_id = session.scalar(
        select(Workspace.company_id).where(Workspace.id == workspace_id)
    )
    other = Workspace(name="블록판정 격리용", company_id=company_id)
    session.add(other)
    session.flush()
    return other.id


def _scenario_upsert_and_list(
    repository: BlockVerdictRepository,
    *,
    proposal_id: uuid.UUID,
) -> None:
    """새 판정 저장·재판정 갱신·block_index 정렬을 한 번에 확인한다."""
    repository.upsert_verdict(
        proposal_id=proposal_id,
        block_index=2,
        block_content_hash=HASH_C,
        verdict="approved",
        rejection_reason=None,
        chosen_winner_claim_id=None,
        reviewer=REVIEWER,
        reviewed_at=FIRST_AT,
    )
    repository.upsert_verdict(
        proposal_id=proposal_id,
        block_index=0,
        block_content_hash=HASH_A,
        verdict="rejected",
        rejection_reason="근거가 부족하다.",
        chosen_winner_claim_id=None,
        reviewer=REVIEWER,
        reviewed_at=FIRST_AT,
    )

    stored = repository.list_for_proposal(proposal_id=proposal_id)
    assert [row.block_index for row in stored] == [0, 2]
    assert stored[0].verdict == "rejected"
    assert stored[0].rejection_reason == "근거가 부족하다."
    assert stored[0].block_content_hash == HASH_A
    assert stored[0].reviewer == REVIEWER
    assert stored[0].reviewed_at == FIRST_AT
    assert stored[1].verdict == "approved"
    assert stored[1].rejection_reason is None

    winner_id = uuid.uuid4()
    repository.upsert_verdict(
        proposal_id=proposal_id,
        block_index=0,
        block_content_hash=HASH_B,
        verdict="approved",
        rejection_reason=None,
        chosen_winner_claim_id=winner_id,
        reviewer="tester2",
        reviewed_at=SECOND_AT,
    )

    stored = repository.list_for_proposal(proposal_id=proposal_id)
    assert [row.block_index for row in stored] == [0, 2]
    assert stored[0].verdict == "approved"
    assert stored[0].rejection_reason is None
    assert stored[0].block_content_hash == HASH_B
    assert stored[0].chosen_winner_claim_id == winner_id
    assert stored[0].reviewer == "tester2"
    assert stored[0].reviewed_at == SECOND_AT


def _scenario_rejected_hashes(
    repository: BlockVerdictRepository,
    *,
    artifact_id: uuid.UUID,
    proposal_id: uuid.UUID,
    other_artifact_id: uuid.UUID,
    other_proposal_id: uuid.UUID,
) -> None:
    """반려 지문 조회가 문서 경계를 넘지 않는지 확인한다."""
    repository.upsert_verdict(
        proposal_id=proposal_id,
        block_index=0,
        block_content_hash=HASH_A,
        verdict="rejected",
        rejection_reason="근거가 부족하다.",
        chosen_winner_claim_id=None,
        reviewer=REVIEWER,
        reviewed_at=FIRST_AT,
    )
    repository.upsert_verdict(
        proposal_id=proposal_id,
        block_index=1,
        block_content_hash=HASH_B,
        verdict="approved",
        rejection_reason=None,
        chosen_winner_claim_id=None,
        reviewer=REVIEWER,
        reviewed_at=FIRST_AT,
    )
    repository.upsert_verdict(
        proposal_id=other_proposal_id,
        block_index=0,
        block_content_hash=HASH_C,
        verdict="rejected",
        rejection_reason="남의 문서 반려.",
        chosen_winner_claim_id=None,
        reviewer=REVIEWER,
        reviewed_at=FIRST_AT,
    )

    assert repository.find_rejected_hashes(artifact_id=artifact_id) == {
        HASH_A: "근거가 부족하다."
    }
    assert repository.find_rejected_hashes(artifact_id=other_artifact_id) == {
        HASH_C: "남의 문서 반려."
    }


def _scenario_latest_rejection_wins(
    repository: BlockVerdictRepository,
    *,
    artifact_id: uuid.UUID,
    proposal_id: uuid.UUID,
) -> None:
    """같은 지문에 반려가 여럿이면 나중 사유가 남는지 확인한다.

    나중 결정을 먼저 넣고 block_index도 더 작게 준다. 결정 시각으로
    정렬하지 않으면 저장 순서든 block_index 순서든 먼저 넣은 쪽이 아니라
    나중에 넣은 옛 사유가 dict에 남아 이 검사가 깨진다.
    """
    repository.upsert_verdict(
        proposal_id=proposal_id,
        block_index=0,
        block_content_hash=HASH_A,
        verdict="rejected",
        rejection_reason="다시 봐도 근거가 낡았다.",
        chosen_winner_claim_id=None,
        reviewer=REVIEWER,
        reviewed_at=SECOND_AT,
    )
    repository.upsert_verdict(
        proposal_id=proposal_id,
        block_index=1,
        block_content_hash=HASH_A,
        verdict="rejected",
        rejection_reason="근거가 부족하다.",
        chosen_winner_claim_id=None,
        reviewer=REVIEWER,
        reviewed_at=FIRST_AT,
    )

    assert repository.find_rejected_hashes(artifact_id=artifact_id) == {
        HASH_A: "다시 봐도 근거가 낡았다."
    }


def test_postgres_upsert_and_list(
    workspace_id: int,
    session_factory: Callable[[], Session],
) -> None:
    """실 DB에서 새 판정·재판정·정렬이 약속대로 움직인다."""
    with session_factory() as session:
        _, proposal_id = _proposal(session, workspace_id)
        repository = SqlAlchemyBlockVerdictRepository(session, workspace_id)
        _scenario_upsert_and_list(repository, proposal_id=proposal_id)


def test_postgres_find_rejected_hashes(
    workspace_id: int,
    session_factory: Callable[[], Session],
) -> None:
    """실 DB에서 반려 지문이 문서별로 갈린다."""
    with session_factory() as session:
        artifact_id, proposal_id = _proposal(session, workspace_id)
        other_artifact_id, other_proposal_id = _proposal(
            session, workspace_id
        )
        repository = SqlAlchemyBlockVerdictRepository(session, workspace_id)
        _scenario_rejected_hashes(
            repository,
            artifact_id=artifact_id,
            proposal_id=proposal_id,
            other_artifact_id=other_artifact_id,
            other_proposal_id=other_proposal_id,
        )


def test_postgres_latest_rejection_reason_wins(
    workspace_id: int,
    session_factory: Callable[[], Session],
) -> None:
    """실 DB에서 같은 지문의 반려는 나중 사유로 접힌다."""
    with session_factory() as session:
        artifact_id, proposal_id = _proposal(session, workspace_id)
        repository = SqlAlchemyBlockVerdictRepository(session, workspace_id)
        _scenario_latest_rejection_wins(
            repository,
            artifact_id=artifact_id,
            proposal_id=proposal_id,
        )


def test_postgres_upsert_refreshes_updated_at(
    workspace_id: int,
    session_factory: Callable[[], Session],
) -> None:
    """재판정은 행을 늘리지 않고 갱신 시각을 새로 찍는다.

    `on_conflict_do_update`는 ORM의 onupdate를 태우지 않는다. 갱신 시각이
    첫 저장 때 값에 머물면 저널을 시간순으로 읽는 쪽이 재판정을 못 본다.
    """
    stale_at = datetime(2020, 1, 1, tzinfo=UTC)
    with session_factory() as session:
        _, proposal_id = _proposal(session, workspace_id)
        seeded_id = uuid.uuid4()
        session.add(
            KnowledgeBlockVerdict(
                id=seeded_id,
                workspace_id=workspace_id,
                proposal_id=proposal_id,
                block_index=0,
                block_content_hash=HASH_A,
                verdict="approved",
                reviewer=REVIEWER,
                reviewed_at=FIRST_AT,
                created_at=stale_at,
                updated_at=stale_at,
            )
        )
        session.flush()

        repository = SqlAlchemyBlockVerdictRepository(session, workspace_id)
        repository.upsert_verdict(
            proposal_id=proposal_id,
            block_index=0,
            block_content_hash=HASH_B,
            verdict="rejected",
            rejection_reason="다시 보니 근거가 낡았다.",
            chosen_winner_claim_id=None,
            reviewer=REVIEWER,
            reviewed_at=SECOND_AT,
        )
        session.expire_all()
        rows = session.execute(
            select(
                KnowledgeBlockVerdict.id,
                KnowledgeBlockVerdict.updated_at,
            ).where(KnowledgeBlockVerdict.proposal_id == proposal_id)
        ).all()

    assert len(rows) == 1
    assert rows[0][0] == seeded_id
    assert rows[0][1] > stale_at


def test_postgres_write_rejects_foreign_workspace_proposal(
    workspace_id: int,
    session_factory: Callable[[], Session],
) -> None:
    """다른 workspace의 변경안에는 판정을 쓸 수 없다.

    proposal_id는 단일 컬럼 FK라 DB가 workspace 교차 참조를 막지 못한다.
    저장소가 고정한 workspace로 그 구멍을 대신 막는다.
    """
    with session_factory() as session:
        other_workspace_id = _other_workspace(session, workspace_id)
        _, foreign_proposal_id = _proposal(session, other_workspace_id)
        repository = SqlAlchemyBlockVerdictRepository(session, workspace_id)

        with pytest.raises(ValueError):
            repository.upsert_verdict(
                proposal_id=foreign_proposal_id,
                block_index=0,
                block_content_hash=HASH_A,
                verdict="approved",
                rejection_reason=None,
                chosen_winner_claim_id=None,
                reviewer=REVIEWER,
                reviewed_at=FIRST_AT,
            )


def test_postgres_read_is_scoped_to_workspace(
    workspace_id: int,
    session_factory: Callable[[], Session],
) -> None:
    """남의 workspace 판정은 읽히지 않는다."""
    with session_factory() as session:
        other_workspace_id = _other_workspace(session, workspace_id)
        artifact_id, proposal_id = _proposal(session, other_workspace_id)
        owner = SqlAlchemyBlockVerdictRepository(session, other_workspace_id)
        owner.upsert_verdict(
            proposal_id=proposal_id,
            block_index=0,
            block_content_hash=HASH_A,
            verdict="rejected",
            rejection_reason="근거가 부족하다.",
            chosen_winner_claim_id=None,
            reviewer=REVIEWER,
            reviewed_at=FIRST_AT,
        )

        outsider = SqlAlchemyBlockVerdictRepository(session, workspace_id)
        assert outsider.list_for_proposal(proposal_id=proposal_id) == ()
        assert outsider.find_rejected_hashes(artifact_id=artifact_id) == {}
        assert len(owner.list_for_proposal(proposal_id=proposal_id)) == 1


def test_postgres_requires_workspace_scope(
    session_factory: Callable[[], Session],
) -> None:
    """workspace를 받지 못한 저장소는 아예 쓰지 못한다."""
    with session_factory() as session:
        repository = SqlAlchemyBlockVerdictRepository(session, None)
        with pytest.raises(RuntimeError):
            repository.list_for_proposal(proposal_id=uuid.uuid4())


def _fake_pair() -> tuple[FakeArtifactRepository, FakeBlockVerdictRepository]:
    """proposal 저장 dict를 공유하는 fake 한 쌍을 만든다."""
    artifacts = FakeArtifactRepository()
    return artifacts, FakeBlockVerdictRepository(artifacts.proposals)


def test_fake_upsert_and_list() -> None:
    """fake도 새 판정·재판정·정렬을 실 DB와 같이 다룬다."""
    artifacts, verdicts = _fake_pair()
    proposal_id = artifacts.add_proposal(
        artifact_id=uuid.uuid4(),
        blocks=(),
        base_revision_id=None,
    )

    _scenario_upsert_and_list(verdicts, proposal_id=proposal_id)


def test_fake_find_rejected_hashes() -> None:
    """fake도 반려 지문을 문서별로 가른다."""
    artifacts, verdicts = _fake_pair()
    artifact_id = uuid.uuid4()
    other_artifact_id = uuid.uuid4()
    proposal_id = artifacts.add_proposal(
        artifact_id=artifact_id,
        blocks=(),
        base_revision_id=None,
    )
    other_proposal_id = artifacts.add_proposal(
        artifact_id=other_artifact_id,
        blocks=(),
        base_revision_id=None,
    )

    _scenario_rejected_hashes(
        verdicts,
        artifact_id=artifact_id,
        proposal_id=proposal_id,
        other_artifact_id=other_artifact_id,
        other_proposal_id=other_proposal_id,
    )


def test_fake_latest_rejection_reason_wins() -> None:
    """fake도 같은 지문의 반려를 나중 사유로 접는다."""
    artifacts, verdicts = _fake_pair()
    artifact_id = uuid.uuid4()
    proposal_id = artifacts.add_proposal(
        artifact_id=artifact_id,
        blocks=(),
        base_revision_id=None,
    )

    _scenario_latest_rejection_wins(
        verdicts,
        artifact_id=artifact_id,
        proposal_id=proposal_id,
    )


def test_fake_mimics_rejection_reason_check() -> None:
    """사유 없는 반려는 fake도 실 DB CHECK처럼 막는다."""
    artifacts, verdicts = _fake_pair()
    proposal_id = artifacts.add_proposal(
        artifact_id=uuid.uuid4(),
        blocks=(),
        base_revision_id=None,
    )

    with pytest.raises(ValueError):
        verdicts.upsert_verdict(
            proposal_id=proposal_id,
            block_index=0,
            block_content_hash=HASH_A,
            verdict="rejected",
            rejection_reason="   ",
            chosen_winner_claim_id=None,
            reviewer=REVIEWER,
            reviewed_at=FIRST_AT,
        )


def test_fake_mimics_verdict_and_reviewer_checks() -> None:
    """약속 밖 판정 값과 빈 결정자도 fake가 막는다."""
    artifacts, verdicts = _fake_pair()
    proposal_id = artifacts.add_proposal(
        artifact_id=uuid.uuid4(),
        blocks=(),
        base_revision_id=None,
    )

    with pytest.raises(ValueError):
        verdicts.upsert_verdict(
            proposal_id=proposal_id,
            block_index=0,
            block_content_hash=HASH_A,
            verdict="banana",
            rejection_reason=None,
            chosen_winner_claim_id=None,
            reviewer=REVIEWER,
            reviewed_at=FIRST_AT,
        )

    with pytest.raises(ValueError):
        verdicts.upsert_verdict(
            proposal_id=proposal_id,
            block_index=0,
            block_content_hash=HASH_A,
            verdict="approved",
            rejection_reason=None,
            chosen_winner_claim_id=None,
            reviewer="  ",
            reviewed_at=FIRST_AT,
        )


def test_fake_mimics_proposal_foreign_key() -> None:
    """없는 변경안에는 fake도 판정을 붙이지 않는다."""
    _, verdicts = _fake_pair()

    with pytest.raises(ValueError):
        verdicts.upsert_verdict(
            proposal_id=uuid.uuid4(),
            block_index=0,
            block_content_hash=HASH_A,
            verdict="approved",
            rejection_reason=None,
            chosen_winner_claim_id=None,
            reviewer=REVIEWER,
            reviewed_at=FIRST_AT,
        )
