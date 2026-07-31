"""승인 서비스가 실 DB에서 한 transaction으로 끝나는지 확인한다.

승인은 변경안 상태를 바꾸는 쓰기와 새 판을 쌓는 쓰기를 함께 한다. fake는
둘을 같은 dict에 담아 두므로 경계가 하나인지 아닌지가 드러나지 않는다.
실 DB에 넣어 커밋 뒤 두 쓰기가 함께 보이는지, 중간에 터지면 앞선 쓰기까지
되감기는지, 판 번호를 선점당하면 서비스의 거부로 바뀌는지 본다.
"""

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
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker

from catchup.configs.config import settings
from catchup.db.models import KnowledgeArtifact
from catchup.db.models import KnowledgeArtifactChangeProposal as ProposalRow
from catchup.db.models import KnowledgeArtifactRevision as RevisionRow
from catchup.db.models import KnowledgeNode as NodeRow
from catchup.db.models import Workspace
from catchup.knowledge_maintenance.adapters.postgres.repositories import (
    SqlAlchemyArtifactRepository,
)
from catchup.knowledge_maintenance.adapters.postgres.unit_of_work import (
    KnowledgeMaintenanceUnitOfWork,
)
from catchup.knowledge_maintenance.domain.artifact import BLOCK_KIND_CLAIM_SECTION
from catchup.knowledge_maintenance.domain.artifact import ArtifactBlock
from catchup.knowledge_maintenance.domain.artifact import artifact_idempotency_key
from catchup.knowledge_maintenance.domain.artifact import blocks_content_hash
from catchup.knowledge_maintenance.domain.artifact import deserialize_blocks
from catchup.knowledge_maintenance.services.review_artifact_proposal import (
    ProposalReviewError,
)
from catchup.knowledge_maintenance.services.review_artifact_proposal import (
    review_artifact_proposal,
)

ARTIFACT_KIND = "entity_summary"
REVIEWER = "tester"


@pytest.fixture(scope="module")
def engine() -> Iterator[Engine]:
    engine = create_engine(settings.sqlalchemy_database_url)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except OperationalError:
        engine.dispose()
        pytest.skip("PostgreSQL이 없어 통합 테스트를 건너뛴다.")

    if not inspect(engine).has_table(KnowledgeArtifact.__tablename__):
        engine.dispose()
        pytest.skip("artifact 테이블이 없다. alembic upgrade head가 필요하다.")

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


def _blocks(body: str) -> tuple[ArtifactBlock, ...]:
    """근거를 갖춘 블록 한 벌을 만든다."""
    return (
        ArtifactBlock(
            block_kind=BLOCK_KIND_CLAIM_SECTION,
            heading="release_month",
            body=body,
            claim_ids=(uuid.uuid4(),),
            proposal_ids=(),
            ontology_version="1",
        ),
    )


def _artifact_id(
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
    session_factory: Callable[[], Session],
    workspace_id: int,
) -> uuid.UUID:
    """새 대상 노드에 붙는 artifact를 하나 확보한다."""
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
        session.commit()
        node_id = node.id

    with uow_factory() as uow:
        artifact_id = uow.artifacts.get_or_create_artifact(
            kind=ARTIFACT_KIND,
            subject_node_id=node_id,
            title="결제 기능",
        )
        uow.commit()
    return artifact_id


def _add(
    uow: KnowledgeMaintenanceUnitOfWork,
    artifact_id: uuid.UUID,
    blocks: tuple[ArtifactBlock, ...],
    base_revision_id: uuid.UUID | None = None,
) -> uuid.UUID:
    """블록 한 벌을 proposal로 올리고 식별자를 돌려준다."""
    content_hash = blocks_content_hash(blocks)
    return uow.artifacts.add_or_revive_proposal(
        artifact_id=artifact_id,
        blocks=blocks,
        content_hash=content_hash,
        idempotency_key=artifact_idempotency_key(artifact_id, content_hash),
        base_revision_id=base_revision_id,
    )


def test_approve_commits_revision_and_status_together(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """승인 한 번이 판과 상태 변경을 함께 남기고, 거절되면 둘 다 없다."""
    artifact_id = _artifact_id(uow_factory, session_factory, workspace_id)
    blocks = _blocks("2026-09")

    with uow_factory() as uow:
        proposal_id = _add(uow, artifact_id, blocks)
        uow.commit()

    result = review_artifact_proposal(
        uow_factory(),
        proposal_id=proposal_id,
        verdict="approved",
        reviewer=REVIEWER,
    )

    assert result.revision_number == 1
    assert result.revision_id is not None

    with session_factory() as session:
        proposal = session.get(ProposalRow, proposal_id)
        assert proposal is not None
        assert proposal.status == "approved"
        assert proposal.reviewer == REVIEWER
        assert proposal.reviewed_at is not None

        revision = session.get(RevisionRow, result.revision_id)
        assert revision is not None
        assert revision.artifact_id == artifact_id
        assert revision.revision_number == 1
        assert revision.source_proposal_id == proposal_id
        # 판은 변경안 본문을 그대로 얼려 담는다.
        assert deserialize_blocks(revision.blocks) == blocks

    # 딛고 선 판이 낡은 변경안은 거절되고 어떤 쓰기도 남기지 않는다.
    with uow_factory() as uow:
        stale_id = _add(uow, artifact_id, _blocks("낡은 근거"), None)
        uow.commit()

    with pytest.raises(ProposalReviewError):
        review_artifact_proposal(
            uow_factory(),
            proposal_id=stale_id,
            verdict="approved",
            reviewer=REVIEWER,
        )

    with session_factory() as session:
        stale = session.get(ProposalRow, stale_id)
        assert stale is not None
        assert stale.status == "pending"
        assert stale.reviewer is None
        numbers = session.scalars(
            select(RevisionRow.revision_number).where(
                RevisionRow.artifact_id == artifact_id
            )
        ).all()
        assert list(numbers) == [1]


def test_approve_rolls_back_revision_when_marking_fails(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """승인 표시가 터지면 앞서 쌓은 판까지 되감긴다.

    커밋 뒤 두 쓰기가 함께 보이는 것만으로는 경계가 하나라는 증거가 되지
    않는다. transaction을 둘로 쪼갠 구현도 그 검증은 통과한다. 중간에서
    터뜨려 앞선 쓰기가 남는지 보는 것이 경계를 실제로 재는 자리다.
    """
    artifact_id = _artifact_id(uow_factory, session_factory, workspace_id)

    with uow_factory() as uow:
        proposal_id = _add(uow, artifact_id, _blocks("2026-09"))
        uow.commit()

    def _fail(self, *, proposal_id: uuid.UUID, reviewer: str) -> None:
        raise RuntimeError("승인 표시가 실패했다")

    monkeypatch.setattr(SqlAlchemyArtifactRepository, "mark_approved", _fail)

    with pytest.raises(RuntimeError):
        review_artifact_proposal(
            uow_factory(),
            proposal_id=proposal_id,
            verdict="approved",
            reviewer=REVIEWER,
        )

    with session_factory() as session:
        assert (
            session.scalars(
                select(RevisionRow).where(
                    RevisionRow.artifact_id == artifact_id
                )
            ).all()
            == []
        )
        proposal = session.get(ProposalRow, proposal_id)
        assert proposal is not None
        assert proposal.status == "pending"


def test_approve_turns_number_collision_into_review_error(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """판 번호를 선점당하면 저장소 예외가 아니라 검토 거부로 나온다.

    최신 판을 읽은 뒤 쓰기까지 사이에 다른 승인이 끼어드는 race를, 최신
    판 조회가 낡은 답을 주도록 만들어 재현한다. 호출자는 저장 계층 예외를
    따로 잡지 않아야 하므로 ProposalReviewError로 나와야 한다.
    """
    artifact_id = _artifact_id(uow_factory, session_factory, workspace_id)

    with uow_factory() as uow:
        seed_id = _add(uow, artifact_id, _blocks("먼저 승인된 판"))
        uow.artifacts.mark_approved(proposal_id=seed_id, reviewer=REVIEWER)
        uow.artifacts.add_revision(
            artifact_id=artifact_id,
            revision_number=1,
            blocks=_blocks("먼저 승인된 판"),
            source_proposal_id=seed_id,
        )
        uow.commit()

    with uow_factory() as uow:
        proposal_id = _add(uow, artifact_id, _blocks("동시에 올라온 판"))
        uow.commit()

    def _stale(self, *, artifact_id: uuid.UUID) -> None:
        # 판이 아직 없던 시점의 답을 돌려준다. 서비스는 1번을 쓰려 한다.
        return None

    monkeypatch.setattr(
        SqlAlchemyArtifactRepository,
        "find_latest_revision_id_and_number",
        _stale,
    )

    with pytest.raises(ProposalReviewError):
        review_artifact_proposal(
            uow_factory(),
            proposal_id=proposal_id,
            verdict="approved",
            reviewer=REVIEWER,
        )

    with session_factory() as session:
        proposal = session.get(ProposalRow, proposal_id)
        assert proposal is not None
        assert proposal.status == "pending"
        numbers = session.scalars(
            select(RevisionRow.revision_number).where(
                RevisionRow.artifact_id == artifact_id
            )
        ).all()
        assert list(numbers) == [1]
