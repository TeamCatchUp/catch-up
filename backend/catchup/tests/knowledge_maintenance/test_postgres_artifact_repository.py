"""artifact 저장 포트의 PostgreSQL 어댑터를 실 DB로 확인한다.

이 저장소는 UNIQUE 제약 위에서 되살리기로 멱등을 만든다. 제약을 흉내 낸
fake로는 되살리기가 필요한지조차 드러나지 않으므로 실 DB에 넣어 본다.
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
from sqlalchemy.exc import IntegrityError
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker

from catchup.configs.config import settings
from catchup.db.models import KnowledgeArtifact
from catchup.db.models import KnowledgeArtifactChangeProposal as ProposalRow
from catchup.db.models import KnowledgeClaimCandidate as ClaimRow
from catchup.db.models import KnowledgeEntityCandidate as EntityCandidateRow
from catchup.db.models import KnowledgeExtractionRun as RunRow
from catchup.db.models import KnowledgeNode as NodeRow
from catchup.db.models import KnowledgeOntologySnapshot as SnapshotRow
from catchup.db.models import Workspace
from catchup.knowledge_maintenance.adapters.postgres.unit_of_work import (
    KnowledgeMaintenanceUnitOfWork,
)
from catchup.knowledge_maintenance.domain.artifact import BLOCK_KIND_CLAIM_SECTION
from catchup.knowledge_maintenance.domain.artifact import BLOCK_KIND_OPEN_QUESTION
from catchup.knowledge_maintenance.domain.artifact import ArtifactBlock
from catchup.knowledge_maintenance.domain.artifact import ArtifactBlockError
from catchup.knowledge_maintenance.domain.artifact import artifact_idempotency_key
from catchup.knowledge_maintenance.domain.artifact import blocks_content_hash
from catchup.knowledge_maintenance.ports.artifacts import ArtifactProposalConflict

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


def _entity_node(session: Session, workspace_id: int, name: str) -> uuid.UUID:
    """canonical entity 노드를 하나 만든다."""
    node = NodeRow(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        node_kind="entity",
        entity_type="feature",
        canonical_key=f"test:feature:{uuid.uuid4().hex}",
        display_name=name,
    )
    session.add(node)
    session.flush()
    return node.id


def _extraction_run(session: Session, workspace_id: int) -> uuid.UUID:
    """claim을 매달 추출 실행을 하나 만든다."""
    ontology_version = uuid.uuid4().hex[:8]
    session.add(
        SnapshotRow(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            ontology_id="test",
            version=ontology_version,
            predicates=[],
            relation_types=[],
        )
    )
    session.flush()
    input_node = NodeRow(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        node_kind="observation",
        resource_type="observation",
        resource_id=str(uuid.uuid4()),
    )
    session.add(input_node)
    session.flush()
    run = RunRow(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        input_node_id=input_node.id,
        provider="test",
        model="test",
        extractor_version="1",
        prompt_version="1",
        ontology_id="test",
        ontology_version=ontology_version,
        status="succeeded",
        started_at=datetime.now(timezone.utc),
    )
    session.add(run)
    session.flush()
    return run.id


def _claim_on_node(
    session: Session,
    workspace_id: int,
    run_id: uuid.UUID,
    node_id: uuid.UUID,
) -> uuid.UUID:
    """canonical 노드를 subject로 삼는 claim을 하나 만든다."""
    row = ClaimRow(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        extraction_run_id=run_id,
        local_key=f"c-{uuid.uuid4().hex}",
        subject_node_id=node_id,
        predicate="release_month",
        value_type="string",
        value="2026-09",
        value_hash="0" * 64,
        statement="9월 예정입니다.",
        ontology_id="test",
        ontology_version="1",
        extraction_method="llm",
    )
    session.add(row)
    session.flush()
    return row.id


def _claim_via_candidate(
    session: Session,
    workspace_id: int,
    run_id: uuid.UUID,
    node_id: uuid.UUID,
) -> uuid.UUID:
    """해소된 entity 후보를 거쳐 노드에 붙는 claim을 하나 만든다."""
    candidate = EntityCandidateRow(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        extraction_run_id=run_id,
        local_key=f"e-{uuid.uuid4().hex}",
        proposed_type="feature",
        proposed_name="결제 기능",
        extraction_method="llm",
        resolution_status="accepted",
        resolved_node_id=node_id,
    )
    session.add(candidate)
    session.flush()
    row = ClaimRow(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        extraction_run_id=run_id,
        local_key=f"c-{uuid.uuid4().hex}",
        subject_entity_candidate_id=candidate.id,
        predicate="owner",
        value_type="string",
        value="결제팀",
        value_hash="1" * 64,
        statement="결제팀이 맡습니다.",
        ontology_id="test",
        ontology_version="1",
        extraction_method="llm",
    )
    session.add(row)
    session.flush()
    return row.id


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


def _add(
    uow: KnowledgeMaintenanceUnitOfWork,
    artifact_id: uuid.UUID,
    blocks: tuple[ArtifactBlock, ...],
    base_revision_id: uuid.UUID | None = None,
) -> tuple[uuid.UUID, str]:
    """블록 한 벌을 proposal로 올리고 식별자와 지문을 돌려준다."""
    content_hash = blocks_content_hash(blocks)
    proposal_id = uow.artifacts.add_or_revive_proposal(
        artifact_id=artifact_id,
        blocks=blocks,
        content_hash=content_hash,
        idempotency_key=artifact_idempotency_key(artifact_id, content_hash),
        base_revision_id=base_revision_id,
    )
    return proposal_id, content_hash


def _artifact_id(
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
    session_factory: Callable[[], Session],
    workspace_id: int,
) -> uuid.UUID:
    """새 대상 노드에 붙는 artifact를 하나 확보한다."""
    with session_factory() as session:
        node_id = _entity_node(session, workspace_id, "결제 기능")
        session.commit()

    with uow_factory() as uow:
        artifact_id = uow.artifacts.get_or_create_artifact(
            kind=ARTIFACT_KIND,
            subject_node_id=node_id,
            title="결제 기능",
        )
        uow.commit()
    return artifact_id


def test_get_or_create_artifact_is_idempotent(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """같은 대상·같은 kind로 두 번 불러도 문서가 하나만 생긴다."""
    with session_factory() as session:
        node_id = _entity_node(session, workspace_id, "결제 기능")
        session.commit()

    with uow_factory() as uow:
        first = uow.artifacts.get_or_create_artifact(
            kind=ARTIFACT_KIND,
            subject_node_id=node_id,
            title="결제 기능",
        )
        uow.commit()

    with uow_factory() as uow:
        second = uow.artifacts.get_or_create_artifact(
            kind=ARTIFACT_KIND,
            subject_node_id=node_id,
            title="결제 기능",
        )
        uow.commit()

    assert first == second


def test_find_top_entity_nodes_orders_by_claim_count(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """claim이 많은 노드가 앞에 오고 claim 0개인 노드는 빠진다."""
    with session_factory() as session:
        run_id = _extraction_run(session, workspace_id)
        busy = _entity_node(session, workspace_id, "많이 언급된 기능")
        quiet = _entity_node(session, workspace_id, "조금 언급된 기능")
        empty = _entity_node(session, workspace_id, "언급 없는 기능")
        for _ in range(3):
            _claim_on_node(session, workspace_id, run_id, busy)
        # 후보를 거쳐 해소된 claim도 그 노드의 것으로 센다.
        _claim_via_candidate(session, workspace_id, run_id, quiet)
        session.commit()

    with uow_factory() as uow:
        found = uow.artifacts.find_top_entity_nodes(limit=10_000)

    counts = {source.node_id: source.claim_count for source in found}
    order = [source.node_id for source in found]
    assert counts[busy] == 3
    assert counts[quiet] == 1
    assert empty not in counts
    assert order.index(busy) < order.index(quiet)
    assert next(
        source.display_name for source in found if source.node_id == busy
    ) == "많이 언급된 기능"

    with uow_factory() as uow:
        limited = uow.artifacts.find_top_entity_nodes(limit=1)
    assert len(limited) == 1


def test_add_or_revive_proposal_revives_abandoned_row(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """같은 key가 다시 오면 접힌 행을 되살리고 본문을 갈아끼운다."""
    artifact_id = _artifact_id(uow_factory, session_factory, workspace_id)
    blocks = _blocks("2026-09")

    with uow_factory() as uow:
        first_id, content_hash = _add(uow, artifact_id, blocks)
        uow.commit()

    with uow_factory() as uow:
        assert uow.artifacts.abandon_pending_proposals(
            artifact_id=artifact_id
        ) == 1
        uow.commit()

    # 같은 지문이지만 근거 claim이 달라진 블록으로 되살린다.
    revived_blocks = (
        ArtifactBlock(
            block_kind=BLOCK_KIND_OPEN_QUESTION,
            heading="열린 질문",
            body="2026-09",
            claim_ids=(),
            proposal_ids=(uuid.uuid4(),),
            ontology_version="1",
        ),
    )
    with uow_factory() as uow:
        second_id = uow.artifacts.add_or_revive_proposal(
            artifact_id=artifact_id,
            blocks=revived_blocks,
            content_hash=content_hash,
            idempotency_key=artifact_idempotency_key(artifact_id, content_hash),
            base_revision_id=None,
        )
        uow.commit()

    assert second_id == first_id

    with uow_factory() as uow:
        stored = uow.artifacts.get_proposal(proposal_id=second_id)
    assert stored is not None
    assert stored.status == "pending"
    assert stored.blocks == revived_blocks
    assert stored.artifact_id == artifact_id
    assert stored.title == "결제 기능"


def test_add_or_revive_proposal_never_reopens_decided_rows(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """이미 결정된 변경안은 같은 키가 다시 와도 그대로 남는다.

    멱등 키가 문서와 내용 지문으로만 만들어지므로 내용이 A→B→A로 돌아오면
    옛 승인과 같은 키가 다시 온다. 그때 되살리면 발행된 판이 가리키는 승인
    행이 pending으로 뒤집히고 승인 감사 기록이 사라진다.
    """
    artifact_id = _artifact_id(uow_factory, session_factory, workspace_id)
    blocks = _blocks("첫 판")
    content_hash = blocks_content_hash(blocks)
    key = artifact_idempotency_key(artifact_id, content_hash)

    with uow_factory() as uow:
        approved_id, _ = _add(uow, artifact_id, blocks)
        uow.artifacts.mark_approved(proposal_id=approved_id, reviewer="tester")
        uow.artifacts.add_revision(
            artifact_id=artifact_id,
            revision_number=1,
            blocks=blocks,
            source_proposal_id=approved_id,
        )
        uow.commit()

    with uow_factory() as uow:
        with pytest.raises(ArtifactProposalConflict):
            uow.artifacts.add_or_revive_proposal(
                artifact_id=artifact_id,
                blocks=blocks,
                content_hash=content_hash,
                idempotency_key=key,
                base_revision_id=None,
            )

    with session_factory() as session:
        row = session.get(ProposalRow, approved_id)
        assert row is not None
        assert row.status == "approved"
        assert row.reviewer == "tester"
        assert row.reviewed_at is not None

    # 반려도 사람이 내린 결정이므로 같은 키로 뒤집히지 않는다.
    rejected_blocks = _blocks("반려된 판")
    rejected_hash = blocks_content_hash(rejected_blocks)
    with uow_factory() as uow:
        rejected_id, _ = _add(uow, artifact_id, rejected_blocks)
        uow.artifacts.mark_rejected(
            proposal_id=rejected_id,
            reviewer="tester",
            reason="근거가 부족하다",
        )
        uow.commit()

    with uow_factory() as uow:
        with pytest.raises(ArtifactProposalConflict):
            uow.artifacts.add_or_revive_proposal(
                artifact_id=artifact_id,
                blocks=rejected_blocks,
                content_hash=rejected_hash,
                idempotency_key=artifact_idempotency_key(
                    artifact_id, rejected_hash
                ),
                base_revision_id=None,
            )

    with session_factory() as session:
        row = session.get(ProposalRow, rejected_id)
        assert row is not None
        assert row.status == "rejected"
        assert row.rejection_reason == "근거가 부족하다"


def test_add_or_revive_proposal_refuses_unsupported_blocks(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """근거 없는 블록은 저장 전에 막힌다."""
    artifact_id = _artifact_id(uow_factory, session_factory, workspace_id)
    blocks = (
        ArtifactBlock(
            block_kind=BLOCK_KIND_CLAIM_SECTION,
            heading="release_month",
            body="2026-09",
            claim_ids=(),
            proposal_ids=(),
            ontology_version="1",
        ),
    )
    content_hash = blocks_content_hash(blocks)

    with uow_factory() as uow:
        with pytest.raises(ArtifactBlockError):
            uow.artifacts.add_or_revive_proposal(
                artifact_id=artifact_id,
                blocks=blocks,
                content_hash=content_hash,
                idempotency_key=artifact_idempotency_key(
                    artifact_id, content_hash
                ),
                base_revision_id=None,
            )
        uow.commit()

    with session_factory() as session:
        assert (
            session.scalars(
                select(ProposalRow).where(ProposalRow.artifact_id == artifact_id)
            ).all()
            == []
        )


def test_abandon_pending_proposals_counts_only_pending(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """접히는 것은 계류 중인 것뿐이고 그 수가 돌아온다."""
    artifact_id = _artifact_id(uow_factory, session_factory, workspace_id)

    with uow_factory() as uow:
        _add(uow, artifact_id, _blocks("2026-09"))
        _add(uow, artifact_id, _blocks("2026-10"))
        rejected_id, _ = _add(uow, artifact_id, _blocks("2026-11"))
        uow.artifacts.mark_rejected(
            proposal_id=rejected_id,
            reviewer="tester",
            reason="근거가 부족하다",
        )
        uow.commit()

    with uow_factory() as uow:
        abandoned = uow.artifacts.abandon_pending_proposals(
            artifact_id=artifact_id
        )
        uow.commit()
    assert abandoned == 2

    with uow_factory() as uow:
        stored = uow.artifacts.get_proposal(proposal_id=rejected_id)
    assert stored is not None
    assert stored.status == "rejected"
    assert stored.rejection_reason == "근거가 부족하다"


def test_find_latest_content_hashes_covers_revision_and_open_reviews(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """최신 revision과 계류·반려 지문이 무동작 판정 집합에 들어간다."""
    artifact_id = _artifact_id(uow_factory, session_factory, workspace_id)

    with uow_factory() as uow:
        old_id, old_hash = _add(uow, artifact_id, _blocks("옛 판"))
        uow.artifacts.mark_approved(proposal_id=old_id, reviewer="tester")
        uow.artifacts.add_revision(
            artifact_id=artifact_id,
            revision_number=1,
            blocks=_blocks("옛 판"),
            source_proposal_id=old_id,
        )
        uow.commit()

    with uow_factory() as uow:
        latest_id, latest_hash = _add(uow, artifact_id, _blocks("새 판"))
        uow.artifacts.mark_approved(proposal_id=latest_id, reviewer="tester")
        revision_id = uow.artifacts.add_revision(
            artifact_id=artifact_id,
            revision_number=2,
            blocks=_blocks("새 판"),
            source_proposal_id=latest_id,
        )
        uow.commit()

    with uow_factory() as uow:
        assert uow.artifacts.find_latest_revision_id_and_number(
            artifact_id=artifact_id
        ) == (revision_id, 2)

    with uow_factory() as uow:
        _, pending_hash = _add(uow, artifact_id, _blocks("계류 중"))
        rejected_id, rejected_hash = _add(uow, artifact_id, _blocks("반려된"))
        uow.artifacts.mark_rejected(
            proposal_id=rejected_id,
            reviewer="tester",
            reason="근거가 부족하다",
        )
        abandoned_id, abandoned_hash = _add(uow, artifact_id, _blocks("접힌"))
        uow.commit()

    with session_factory() as session:
        row = session.get(ProposalRow, abandoned_id)
        assert row is not None
        row.status = "abandoned"
        session.commit()

    with uow_factory() as uow:
        hashes = uow.artifacts.find_latest_content_hashes(
            artifact_id=artifact_id
        )

    assert latest_hash in hashes
    assert pending_hash in hashes
    assert rejected_hash in hashes
    # 지나간 판과 접힌 변경안은 다시 올릴 수 있어야 한다.
    assert old_hash not in hashes
    assert abandoned_hash not in hashes


def test_list_pending_proposals_returns_only_open_rows(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """검토 큐에는 계류 중인 변경안만 담긴다."""
    artifact_id = _artifact_id(uow_factory, session_factory, workspace_id)

    with uow_factory() as uow:
        pending_id, _ = _add(uow, artifact_id, _blocks("계류 중"))
        rejected_id, _ = _add(uow, artifact_id, _blocks("반려된"))
        uow.artifacts.mark_rejected(
            proposal_id=rejected_id,
            reviewer="tester",
            reason="근거가 부족하다",
        )
        uow.commit()

    with uow_factory() as uow:
        listed = uow.artifacts.list_pending_proposals()

    ids = [proposal.id for proposal in listed]
    assert pending_id in ids
    assert rejected_id not in ids
    found = next(item for item in listed if item.id == pending_id)
    assert found.title == "결제 기능"
    assert found.base_revision_id is None
    assert found.rejection_reason is None
    assert found.blocks[0].block_kind == BLOCK_KIND_CLAIM_SECTION


def test_duplicate_revision_number_is_rejected(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """같은 판 번호를 두 번 쓰면 DB가 막는다."""
    artifact_id = _artifact_id(uow_factory, session_factory, workspace_id)

    with uow_factory() as uow:
        proposal_id, _ = _add(uow, artifact_id, _blocks("첫 판"))
        uow.artifacts.mark_approved(proposal_id=proposal_id, reviewer="tester")
        uow.artifacts.add_revision(
            artifact_id=artifact_id,
            revision_number=1,
            blocks=_blocks("첫 판"),
            source_proposal_id=proposal_id,
        )
        uow.commit()

    with uow_factory() as uow:
        with pytest.raises(IntegrityError):
            uow.artifacts.add_revision(
                artifact_id=artifact_id,
                revision_number=1,
                blocks=_blocks("첫 판"),
                source_proposal_id=proposal_id,
            )
