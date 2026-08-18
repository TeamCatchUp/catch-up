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
from catchup.db.models import ChannelFolder
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
from catchup.knowledge_maintenance.domain.artifact import BlockSource
from catchup.knowledge_maintenance.domain.artifact import artifact_idempotency_key
from catchup.knowledge_maintenance.domain.artifact import blocks_content_hash
from catchup.knowledge_maintenance.ports.artifacts import ArtifactProposalConflict
from catchup.tests.knowledge_maintenance.test_artifact_definition_schema import (
    _definition_with_channel,
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


def _resolved_candidate(
    session: Session,
    workspace_id: int,
    run_id: uuid.UUID,
    node_id: uuid.UUID,
) -> uuid.UUID:
    """어떤 노드로 해소를 마친 entity 후보를 하나 만든다."""
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
    return candidate.id


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
        idempotency_key=artifact_idempotency_key(
            artifact_id, content_hash, base_revision_id=base_revision_id
        ),
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


def test_get_or_create_definition_artifact_is_idempotent(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """같은 정의·같은 대상으로 두 번 불러도 문서가 하나만 생긴다."""
    with session_factory() as session:
        node_id = _entity_node(session, workspace_id, "결제 기능")
        session.commit()
    definition = _definition_with_channel(session_factory, workspace_id)

    with uow_factory() as uow:
        first = uow.artifacts.get_or_create_definition_artifact(
            definition_id=definition.id,
            channel_id=definition.channel_id,
            kind=definition.kind,
            subject_node_id=node_id,
            title="결제 기능",
        )
        uow.commit()

    with uow_factory() as uow:
        second = uow.artifacts.get_or_create_definition_artifact(
            definition_id=definition.id,
            channel_id=definition.channel_id,
            kind=definition.kind,
            subject_node_id=node_id,
            title="다른 제목",
        )
        uow.commit()

    assert first == second
    with session_factory() as session:
        # 제목은 문서의 정체성이라 다시 부른다고 갈아 끼우지 않는다.
        assert session.execute(
            select(KnowledgeArtifact.title).where(
                KnowledgeArtifact.id == first
            )
        ).scalar_one() == "결제 기능"


def test_get_or_create_definition_artifact_copies_folder_id(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """새 문서는 넘긴 folder_id를 받고, 이미 있는 문서의 folder_id는 바뀌지 않는다."""
    with session_factory() as session:
        node_id = _entity_node(session, workspace_id, "결제 기능")
        session.commit()
    definition = _definition_with_channel(session_factory, workspace_id)
    with session_factory() as session:
        folder = ChannelFolder(
            workspace_id=workspace_id,
            channel_id=definition.channel_id,
            name="기능 요청 문서",
        )
        session.add(folder)
        session.commit()
        folder_id = folder.id

    with uow_factory() as uow:
        first = uow.artifacts.get_or_create_definition_artifact(
            definition_id=definition.id,
            channel_id=definition.channel_id,
            kind=definition.kind,
            subject_node_id=node_id,
            title="결제 기능",
            folder_id=folder_id,
        )
        uow.commit()
    with uow_factory() as uow:
        second = uow.artifacts.get_or_create_definition_artifact(
            definition_id=definition.id,
            channel_id=definition.channel_id,
            kind=definition.kind,
            subject_node_id=node_id,
            title="결제 기능",
            folder_id=None,
        )
        uow.commit()

    assert first == second
    with session_factory() as session:
        # 폴더를 옮기는 일은 사람의 결정이라 컴파일이 다시 돌아도 그대로다.
        assert session.get(KnowledgeArtifact, first).folder_id == folder_id


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
            idempotency_key=artifact_idempotency_key(
                artifact_id, content_hash, base_revision_id=None
            ),
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
    key = artifact_idempotency_key(
        artifact_id, content_hash, base_revision_id=None
    )

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
                    artifact_id, rejected_hash, base_revision_id=None
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
                    artifact_id, content_hash, base_revision_id=None
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


def test_abandon_pending_proposals_keeps_requested_content_hash(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """현재 내용과 같은 계류안은 남기고 다른 계류안만 접는다."""
    artifact_id = _artifact_id(uow_factory, session_factory, workspace_id)

    with uow_factory() as uow:
        kept_id, kept_hash = _add(uow, artifact_id, _blocks("현재"))
        stale_id, _ = _add(uow, artifact_id, _blocks("이전"))
        uow.commit()

    with uow_factory() as uow:
        abandoned = uow.artifacts.abandon_pending_proposals(
            artifact_id=artifact_id,
            except_content_hash=kept_hash,
        )
        uow.commit()

    with session_factory() as session:
        assert abandoned == 1
        assert session.get(ProposalRow, kept_id).status == "pending"
        assert session.get(ProposalRow, stale_id).status == "abandoned"


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
    # 검토 큐가 정렬·표시에 쓰는 두 값이 port까지 왕복한다.
    assert found.origin == "compiled"
    assert found.created_at is not None


def test_list_pending_proposals_pages_the_oldest_first_order(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """limit/offset이 오래된 순 위에서 겹치지 않게 자른다."""
    artifact_id = _artifact_id(uow_factory, session_factory, workspace_id)

    with uow_factory() as uow:
        for index in range(3):
            _add(uow, artifact_id, _blocks(f"본문 {index}"))
        uow.commit()

    with uow_factory() as uow:
        everything = uow.artifacts.list_pending_proposals()
        first = uow.artifacts.list_pending_proposals(limit=2)
        second = uow.artifacts.list_pending_proposals(limit=2, offset=2)

    ordered = [proposal.id for proposal in everything]
    assert [proposal.id for proposal in first] == ordered[:2]
    assert [proposal.id for proposal in second] == ordered[2:4]


def _contradiction_proposal(
    uow: KnowledgeMaintenanceUnitOfWork,
    workspace_id: int,
    claim_id: uuid.UUID,
    node_id: uuid.UUID,
) -> uuid.UUID:
    """어떤 노드를 대상으로 삼는 모순 계획서를 하나 쓴다."""
    return uow.mutation_proposals.add_contradiction_proposal(
        workspace_id=workspace_id,
        idempotency_key=f"contradiction-{uuid.uuid4().hex}",
        trigger_claim_candidate_id=claim_id,
        detector="test",
        detector_version="1",
        summary="'release_month' 값이 2종으로 갈린다",
        resolver_metadata={
            "subject_key": f"node:{node_id}",
            "predicate": "release_month",
            # 판정기는 값 후보를 항상 함께 남긴다. 충돌 노드 조회가
            # 이 목록에서 claim을 되짚으므로 실제 모양대로 담는다.
            "values": [
                {
                    "claim_id": str(claim_id),
                    "value": "2026-09",
                    "normalized": "2026-09",
                    "statement": "9월 예정입니다.",
                    "observed_at": "2026-07-01T00:00:00+00:00",
                }
            ],
        },
    )


def _duplicate_proposal(
    uow: KnowledgeMaintenanceUnitOfWork,
    workspace_id: int,
    candidate_id: uuid.UUID,
) -> uuid.UUID:
    """어떤 후보를 멤버로 삼는 병합 계획서를 하나 쓴다."""
    return uow.mutation_proposals.add_duplicate_proposal(
        workspace_id=workspace_id,
        idempotency_key=f"duplicate-{uuid.uuid4().hex}",
        trigger_entity_candidate_id=candidate_id,
        detector="test",
        detector_version="1",
        summary="같은 이름 후보 2건 병합",
        resolver_metadata={"member_ids": [str(candidate_id)]},
        representative_candidate_id=candidate_id,
        merge_candidate_ids=(),
        proposed_type="feature",
        proposed_name="결제 기능",
    )


def test_find_pending_for_subject_node_matches_both_kinds(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """대상 노드에 걸린 모순·병합 안건만 돌아오고 남의 것은 빠진다."""
    with session_factory() as session:
        run_id = _extraction_run(session, workspace_id)
        node_id = _entity_node(session, workspace_id, "결제 기능")
        other_node_id = _entity_node(session, workspace_id, "정산 기능")
        claim_id = _claim_on_node(session, workspace_id, run_id, node_id)
        other_claim_id = _claim_on_node(
            session, workspace_id, run_id, other_node_id
        )
        member_id = _resolved_candidate(
            session, workspace_id, run_id, node_id
        )
        stranger_id = _resolved_candidate(
            session, workspace_id, run_id, other_node_id
        )
        session.commit()

    with uow_factory() as uow:
        contradiction_id = _contradiction_proposal(
            uow, workspace_id, claim_id, node_id
        )
        duplicate_id = _duplicate_proposal(uow, workspace_id, member_id)
        _contradiction_proposal(
            uow, workspace_id, other_claim_id, other_node_id
        )
        _duplicate_proposal(uow, workspace_id, stranger_id)
        uow.commit()

    with uow_factory() as uow:
        found = uow.mutation_proposals.find_pending_for_subject_node(
            workspace_id=workspace_id, node_id=node_id
        )

    assert {item.id for item in found} == {contradiction_id, duplicate_id}
    kinds = {item.id: item.proposal_kind for item in found}
    assert kinds[contradiction_id] == "contradiction"
    assert kinds[duplicate_id] == "duplicate"
    contradiction = next(
        item for item in found if item.id == contradiction_id
    )
    assert contradiction.summary == "'release_month' 값이 2종으로 갈린다"
    assert contradiction.resolver_metadata["subject_key"] == (
        f"node:{node_id}"
    )
    duplicate = next(item for item in found if item.id == duplicate_id)
    assert duplicate.resolver_metadata["member_ids"] == [str(member_id)]

    # 접힌 안건은 더 이상 답을 기다리지 않으므로 카드에 실리지 않는다.
    with uow_factory() as uow:
        uow.mutation_proposals.abandon(proposal_id=contradiction_id)
        uow.commit()

    with uow_factory() as uow:
        remaining = uow.mutation_proposals.find_pending_for_subject_node(
            workspace_id=workspace_id, node_id=node_id
        )
    assert {item.id for item in remaining} == {duplicate_id}


def test_find_pending_for_subject_node_stays_in_workspace(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """다른 workspace의 같은 모양 안건은 결과에 섞이지 않는다.

    판정 근거의 subject_key는 JSONB 문자열이라 어느 workspace에서도 남의
    노드를 가리키는 값을 담을 수 있다. workspace로 먼저 좁히지 않으면 그
    행이 카드에 실린다.
    """
    with session_factory() as session:
        company_id = session.scalars(
            select(Workspace.company_id).where(Workspace.id == workspace_id)
        ).one()
        stranger = Workspace(name="다른 워크스페이스", company_id=company_id)
        session.add(stranger)
        session.flush()
        stranger_workspace_id = stranger.id

        run_id = _extraction_run(session, workspace_id)
        node_id = _entity_node(session, workspace_id, "결제 기능")
        claim_id = _claim_on_node(session, workspace_id, run_id, node_id)

        stranger_run_id = _extraction_run(session, stranger_workspace_id)
        stranger_node_id = _entity_node(
            session, stranger_workspace_id, "결제 기능"
        )
        stranger_claim_id = _claim_on_node(
            session, stranger_workspace_id, stranger_run_id, stranger_node_id
        )
        session.commit()

    with uow_factory() as uow:
        mine = _contradiction_proposal(uow, workspace_id, claim_id, node_id)
        # 남의 workspace가 내 노드를 가리키는 근거를 담고 있는 상황이다.
        _contradiction_proposal(
            uow, stranger_workspace_id, stranger_claim_id, node_id
        )
        uow.commit()

    with uow_factory() as uow:
        found = uow.mutation_proposals.find_pending_for_subject_node(
            workspace_id=workspace_id, node_id=node_id
        )

    assert [item.id for item in found] == [mine]


def _publish_revision(
    uow: KnowledgeMaintenanceUnitOfWork,
    artifact_id: uuid.UUID,
    revision_number: int,
    body: str,
) -> uuid.UUID:
    """변경안을 올려 승인하고 그 내용으로 판을 하나 발행한다."""
    blocks = _blocks(body)
    proposal_id, _ = _add(uow, artifact_id, blocks)
    uow.artifacts.mark_approved(proposal_id=proposal_id, reviewer="tester")
    return uow.artifacts.add_revision(
        artifact_id=artifact_id,
        revision_number=revision_number,
        blocks=blocks,
        source_proposal_id=proposal_id,
    )


def test_find_current_revisions_returns_latest_only(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """artifact마다 최신 판 1건만 돌아오고 판 없는 문서는 빠진다."""
    published = _artifact_id(uow_factory, session_factory, workspace_id)
    empty = _artifact_id(uow_factory, session_factory, workspace_id)

    with uow_factory() as uow:
        _publish_revision(uow, published, 1, "옛 판")
        latest_id = _publish_revision(uow, published, 2, "새 판")
        uow.commit()

    with uow_factory() as uow:
        rows = uow.artifacts.find_current_revisions(workspace_id=workspace_id)

    by_artifact = {row.artifact_id: row for row in rows}
    # 판이 두 개라도 문서 하나당 행 하나만 나온다.
    assert len(rows) == len(by_artifact)
    assert empty not in by_artifact

    row = by_artifact[published]
    assert row.revision_id == latest_id
    assert row.revision_number == 2
    assert row.title == "결제 기능"
    assert row.created_at is not None
    # 블록이 JSONB에서 도메인 타입으로 복원된다.
    assert row.blocks[0].heading == "release_month"
    assert row.blocks[0].body == "새 판"
    assert row.blocks[0].block_kind == BLOCK_KIND_CLAIM_SECTION
    assert isinstance(row.blocks[0].claim_ids[0], uuid.UUID)


def test_find_current_revisions_stays_in_workspace(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """다른 workspace의 판은 결과에 섞이지 않는다."""
    with session_factory() as session:
        company_id = session.scalars(
            select(Workspace.company_id).where(Workspace.id == workspace_id)
        ).one()
        stranger = Workspace(name="다른 워크스페이스", company_id=company_id)
        session.add(stranger)
        session.flush()
        stranger_workspace_id = stranger.id
        stranger_node_id = _entity_node(
            session, stranger_workspace_id, "결제 기능"
        )
        session.commit()

    stranger_definition = _definition_with_channel(
        session_factory, stranger_workspace_id
    )
    with KnowledgeMaintenanceUnitOfWork(
        session_factory, workspace_id=stranger_workspace_id
    ) as uow:
        stranger_artifact = uow.artifacts.get_or_create_definition_artifact(
            definition_id=stranger_definition.id,
            channel_id=stranger_definition.channel_id,
            kind=stranger_definition.kind,
            subject_node_id=stranger_node_id,
            title="남의 결제 기능",
        )
        _publish_revision(uow, stranger_artifact, 1, "남의 판")
        uow.commit()

    with uow_factory() as uow:
        rows = uow.artifacts.find_current_revisions(workspace_id=workspace_id)

    assert stranger_artifact not in {row.artifact_id for row in rows}


def test_find_current_revisions_refuses_other_workspace(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """저장소가 고정한 workspace와 다른 값을 넘기면 막힌다.

    어긋난 채로 읽으면 재투영이 남의 문서를 검색 인덱스에 싣는다.
    """
    with uow_factory() as uow:
        with pytest.raises(ValueError):
            uow.artifacts.find_current_revisions(
                workspace_id=workspace_id + 1_000_000
            )


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


def test_blocks_with_sources_roundtrip_via_repository(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """근거 인용이 붙은 블록이 JSONB를 왕복해도 그대로 돌아온다."""
    artifact_id = _artifact_id(uow_factory, session_factory, workspace_id)
    verified_claim = uuid.uuid4()
    unlinked_claim = uuid.uuid4()
    blocks = (
        ArtifactBlock(
            block_kind=BLOCK_KIND_CLAIM_SECTION,
            heading="release_month",
            body="2026-09 (2026-07-30 관찰)",
            claim_ids=(verified_claim, unlinked_claim),
            proposal_ids=(),
            ontology_version="1",
            sources=(
                BlockSource(
                    claim_id=verified_claim,
                    statement="9월 예정입니다.",
                    observed_at=datetime(
                        2026, 7, 30, 9, 0, tzinfo=timezone.utc
                    ),
                    citation_verified=True,
                ),
                # evidence가 없는 인용은 None으로 남아야 한다. bool로 넓게
                # 받으면 이 값이 False로 뒤집혀 환각 의심과 뒤섞인다.
                BlockSource(
                    claim_id=unlinked_claim,
                    statement="10월로 미뤄질 수도 있습니다.",
                    observed_at=datetime(
                        2026, 7, 31, 9, 0, tzinfo=timezone.utc
                    ),
                    citation_verified=None,
                ),
            ),
        ),
    )

    with uow_factory() as uow:
        proposal_id, _ = _add(uow, artifact_id, blocks)
        uow.commit()

    with uow_factory() as uow:
        stored = uow.artifacts.get_proposal(proposal_id=proposal_id)

    assert stored is not None
    assert stored.blocks == blocks
    assert stored.blocks[0].sources[0].citation_verified is True
    assert stored.blocks[0].sources[1].citation_verified is None


def test_legacy_blocks_without_sources_still_load(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """sources 키가 없는 옛 저장 형태도 빈 인용으로 읽힌다.

    이 필드가 붙기 전에 저장된 행이 그대로 남아 있다. 검토 큐가 그 행을
    읽다 깨지면 옛 변경안을 사람이 결정할 수 없게 된다.
    """
    artifact_id = _artifact_id(uow_factory, session_factory, workspace_id)

    with uow_factory() as uow:
        proposal_id, _ = _add(uow, artifact_id, _blocks("2026-09"))
        uow.commit()

    with session_factory() as session:
        row = session.get(ProposalRow, proposal_id)
        assert row is not None
        row.blocks = [
            {key: value for key, value in block.items() if key != "sources"}
            for block in row.blocks
        ]
        session.commit()

    with session_factory() as session:
        row = session.get(ProposalRow, proposal_id)
        assert row is not None
        assert "sources" not in row.blocks[0]

    with uow_factory() as uow:
        stored = uow.artifacts.get_proposal(proposal_id=proposal_id)

    assert stored is not None
    assert stored.blocks[0].sources == ()
    assert stored.blocks[0].body == "2026-09"
