"""승인 서비스가 실 DB에서 한 transaction으로 끝나는지 확인한다.

승인은 변경안 상태를 바꾸는 쓰기와 새 판을 쌓는 쓰기를 함께 한다. fake는
둘을 같은 dict에 담아 두므로 경계가 하나인지 아닌지가 드러나지 않는다.
실 DB에 넣어 커밋 뒤 두 쓰기가 함께 보이는지, 중간에 터지면 앞선 쓰기까지
되감기는지, 판 번호를 선점당하면 서비스의 거부로 바뀌는지 본다.

두 검토가 같은 변경안을 두고 부딪히는 경합도 여기서 본다. 서비스의 계류
검사는 잠금 없는 읽기라 둘 다 통과하므로, 나중 쓰기가 먼저 확정된 결정을
덮지 않는지는 실 transaction 둘을 붙여야만 드러난다.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from collections.abc import Iterator

import pytest
from sqlalchemy import Engine
from sqlalchemy import create_engine
from sqlalchemy import delete
from sqlalchemy import inspect
from sqlalchemy import select
from sqlalchemy import text
from sqlalchemy import update as sa_update
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker

from catchup.configs.config import settings
from catchup.db.models import ArtifactDefinition
from catchup.db.models import Channel
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
from catchup.tests.knowledge_maintenance.test_artifact_definition_schema import (
    _definition_with_channel,
)

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


@pytest.fixture
def committed_artifacts() -> list[uuid.UUID]:
    """실 커밋으로 만든 문서의 식별자를 모은다. 뒤처리 대상이다."""
    return []


@pytest.fixture
def committed_session_factory(engine: Engine) -> Callable[[], Session]:
    """정말로 커밋하는 세션을 낸다. 세션마다 다른 연결을 쓴다.

    다른 테스트가 쓰는 `session_factory`는 한 연결 위의 savepoint라 여러
    세션이 사실은 같은 transaction이다. 결정 경합은 두 transaction이 각각
    커밋해야만 생기므로 여기서는 engine에 직접 물린다.
    """
    return sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture
def committed_uow_factory(
    committed_session_factory: Callable[[], Session],
    workspace_id: int,
    committed_artifacts: list[uuid.UUID],
) -> Iterator[Callable[[], KnowledgeMaintenanceUnitOfWork]]:
    """정말로 커밋하는 UnitOfWork를 낸다.

    되감기로 지워지지 않으니 만든 행은 끝나고 손으로 지운다. 문서가
    딛고 선 정의와 채널도 같이 지운다 — 남으면 다음 회차가 같은 채널에
    같은 kind의 정의를 또 만들지 못한다.
    """
    session_factory = committed_session_factory

    yield lambda: KnowledgeMaintenanceUnitOfWork(
        session_factory, workspace_id=workspace_id
    )

    with session_factory() as session:
        for artifact_id in committed_artifacts:
            found = session.execute(
                select(
                    KnowledgeArtifact.subject_node_id,
                    KnowledgeArtifact.definition_id,
                    KnowledgeArtifact.channel_id,
                ).where(KnowledgeArtifact.id == artifact_id)
            ).first()
            node_id, definition_id, channel_id = (
                found if found is not None else (None, None, None)
            )
            # 판과 변경안이 서로를 가리키므로(base_revision_id ↔
            # source_proposal_id) 참조를 먼저 끊고 지운다.
            session.execute(
                sa_update(ProposalRow)
                .where(ProposalRow.artifact_id == artifact_id)
                .values(base_revision_id=None)
            )
            session.execute(
                delete(RevisionRow).where(
                    RevisionRow.artifact_id == artifact_id
                )
            )
            session.execute(
                delete(ProposalRow).where(
                    ProposalRow.artifact_id == artifact_id
                )
            )
            session.execute(
                delete(KnowledgeArtifact).where(
                    KnowledgeArtifact.id == artifact_id
                )
            )
            if node_id is not None:
                session.execute(
                    delete(NodeRow).where(NodeRow.id == node_id)
                )
            if definition_id is not None:
                session.execute(
                    delete(ArtifactDefinition).where(
                        ArtifactDefinition.id == definition_id
                    )
                )
            if channel_id is not None:
                session.execute(
                    delete(Channel).where(Channel.id == channel_id)
                )
        session.commit()


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

    definition = _definition_with_channel(session_factory, workspace_id)
    with uow_factory() as uow:
        artifact_id = uow.artifacts.get_or_create_definition_artifact(
            definition_id=definition.id,
            channel_id=definition.channel_id,
            kind=definition.kind,
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
        idempotency_key=artifact_idempotency_key(
            artifact_id, content_hash, base_revision_id=base_revision_id
        ),
        base_revision_id=base_revision_id,
    )


def _committed_proposal(
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
    workspace_id: int,
    committed_artifacts: list[uuid.UUID],
    session_factory: Callable[[], Session],
) -> uuid.UUID:
    """정말로 커밋된 계류 변경안 하나를 새 문서 위에 마련한다."""
    definition = _definition_with_channel(session_factory, workspace_id)
    with uow_factory() as uow:
        node = uow.knowledge_nodes.create_entity_node(
            workspace_id=workspace_id,
            entity_type="feature",
            canonical_key=f"test:feature:{uuid.uuid4().hex}",
            display_name="결제 기능",
        )
        artifact_id = uow.artifacts.get_or_create_definition_artifact(
            definition_id=definition.id,
            channel_id=definition.channel_id,
            kind=definition.kind,
            subject_node_id=node.id,
            title="결제 기능",
        )
        proposal_id = _add(uow, artifact_id, _blocks("2026-09"))
        uow.commit()
    committed_artifacts.append(artifact_id)
    return proposal_id


def _let_rival_decide_after_read(
    monkeypatch: pytest.MonkeyPatch,
    rival: Callable[[], None],
) -> None:
    """계류 검사와 결정 쓰기 사이에 다른 검토를 끼워 넣는다.

    서비스는 변경안을 읽어 계류인지 보고 나서 결정을 쓴다. 그 읽기가
    끝난 직후에 다른 transaction이 결정을 확정하고 커밋하게 만들면,
    잠금 없는 검사를 통과한 쪽이 남의 결정을 덮으려 드는 순간이 그대로
    재현된다. 시간에 기대지 않으므로 실행마다 같은 순서가 나온다.

    끼워 넣기는 한 번만 한다. 다른 검토도 같은 서비스를 지나가므로
    막지 않으면 끝없이 스스로를 부른다.
    """
    original = SqlAlchemyArtifactRepository.get_proposal
    fired = False

    def _read_then_yield(self, *, proposal_id: uuid.UUID):
        nonlocal fired
        found = original(self, proposal_id=proposal_id)
        if not fired:
            fired = True
            rival()
        return found

    monkeypatch.setattr(
        SqlAlchemyArtifactRepository, "get_proposal", _read_then_yield
    )


def test_reject_committed_first_beats_late_approval(
    workspace_id: int,
    committed_artifacts: list[uuid.UUID],
    committed_uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
    committed_session_factory: Callable[[], Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """먼저 커밋된 반려를 뒤늦은 승인이 덮지 못한다.

    덮으면 반려된 변경안을 가리키는 판이 남는다. 감사 기록으로 읽으면
    "반려됐는데 문서에 실렸다"는 모순이라 조용히 넘길 수 없다.
    """
    proposal_id = _committed_proposal(
        committed_uow_factory,
        workspace_id,
        committed_artifacts,
        committed_session_factory,
    )

    def _rival() -> None:
        review_artifact_proposal(
            committed_uow_factory(),
            proposal_id=proposal_id,
            verdict="rejected",
            reviewer="first",
            reason="근거가 부족하다",
        )

    _let_rival_decide_after_read(monkeypatch, _rival)

    with pytest.raises(ProposalReviewError):
        review_artifact_proposal(
            committed_uow_factory(),
            proposal_id=proposal_id,
            verdict="approved",
            reviewer="second",
        )

    with committed_uow_factory() as uow:
        proposal = uow.artifacts.get_proposal(proposal_id=proposal_id)
        assert proposal is not None
        assert proposal.status == "rejected"
        assert proposal.rejection_reason == "근거가 부족하다"
        # 진 승인이 쌓던 판까지 함께 되감겨야 상태와 판이 어긋나지 않는다.
        assert (
            uow.artifacts.find_latest_revision_id_and_number(
                artifact_id=committed_artifacts[-1]
            )
            is None
        )


def test_approve_committed_first_beats_late_rejection(
    workspace_id: int,
    committed_artifacts: list[uuid.UUID],
    committed_uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
    committed_session_factory: Callable[[], Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """먼저 커밋된 승인을 뒤늦은 반려가 덮지 못한다.

    덮으면 반려로 적힌 변경안이 이미 발행된 판의 출처로 남는다.
    """
    proposal_id = _committed_proposal(
        committed_uow_factory,
        workspace_id,
        committed_artifacts,
        committed_session_factory,
    )

    def _rival() -> None:
        review_artifact_proposal(
            committed_uow_factory(),
            proposal_id=proposal_id,
            verdict="approved",
            reviewer="first",
        )

    _let_rival_decide_after_read(monkeypatch, _rival)

    with pytest.raises(ProposalReviewError):
        review_artifact_proposal(
            committed_uow_factory(),
            proposal_id=proposal_id,
            verdict="rejected",
            reviewer="second",
            reason="근거가 부족하다",
        )

    with committed_uow_factory() as uow:
        proposal = uow.artifacts.get_proposal(proposal_id=proposal_id)
        assert proposal is not None
        assert proposal.status == "approved"
        assert proposal.rejection_reason is None
        latest = uow.artifacts.find_latest_revision_id_and_number(
            artifact_id=committed_artifacts[-1]
        )
        assert latest is not None
        assert latest[1] == 1


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


def test_approved_revert_reaches_new_revision(
    workspace_id: int,
    committed_artifacts: list[uuid.UUID],
    committed_uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
    committed_session_factory: Callable[[], Session],
) -> None:
    """승인된 옛 판 내용으로 돌아와도 새 판으로 승인될 수 있다.

    멱등 키에 기준 판이 들어가므로 rev2 위에서 제안하는 A는 rev1을
    만든 옛 승인 행과 다른 검토 사건이다. A 승인 → B 승인 → A 복귀가
    rev3=A로 끝나야 문서가 현재 사실로 돌아올 길이 있다.
    """
    proposal_a = _committed_proposal(
        committed_uow_factory,
        workspace_id,
        committed_artifacts,
        committed_session_factory,
    )
    artifact_id = committed_artifacts[-1]
    blocks_a = _blocks("2026-09")

    first = review_artifact_proposal(
        committed_uow_factory(),
        proposal_id=proposal_a,
        verdict="approved",
        reviewer=REVIEWER,
    )
    assert first.revision_number == 1

    with committed_uow_factory() as uow:
        proposal_b = _add(
            uow, artifact_id, _blocks("2026-10"), base_revision_id=first.revision_id
        )
        uow.commit()
    second = review_artifact_proposal(
        committed_uow_factory(),
        proposal_id=proposal_b,
        verdict="approved",
        reviewer=REVIEWER,
    )
    assert second.revision_number == 2

    with committed_uow_factory() as uow:
        revert_id = _add(
            uow, artifact_id, blocks_a, base_revision_id=second.revision_id
        )
        uow.commit()
    assert revert_id not in (proposal_a, proposal_b)

    third = review_artifact_proposal(
        committed_uow_factory(),
        proposal_id=revert_id,
        verdict="approved",
        reviewer=REVIEWER,
    )
    assert third.revision_number == 3

    with committed_uow_factory() as uow:
        session = uow._session
        stored = session.scalars(
            select(RevisionRow).where(
                RevisionRow.artifact_id == artifact_id,
                RevisionRow.revision_number == 3,
            )
        ).one()
        assert deserialize_blocks(stored.blocks) == blocks_a
