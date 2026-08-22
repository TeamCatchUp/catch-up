"""발행이 파생 모순 결정까지 한 transaction으로 묶는지 실 DB로 본다.

발행은 판을 쌓고 변경안을 끝맺는 것 말고도, 다툼 블록마다 모순 안건에
결정을 남긴다. 그 결정은 자기 UoW 안에서 스스로 commit하는 서비스가
만드는데, 발행은 `_JoinedUnitOfWork`로 그 경계를 삼켜 자기 transaction에
얹는다. fake는 저장소를 dict로 들고 있어 경계가 하나인지 둘인지 드러나지
않으므로, 실 DB에 넣어 두 가지를 본다.

성공하면 판·변경안 상태·모순 결정이 함께 보이는지, 그리고 여러 다툼
가운데 뒤쪽이 CONFLICT_RACE로 막히면 앞서 확정한 모순 결정까지 전부
되감기는지다. 뒤쪽이 남으면 문서에 실리지 않은 값으로 지식 원장만 닫혀
둘의 앎이 갈린다.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
from datetime import timezone

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
from catchup.db.models import KnowledgeArtifactChangeProposal as ProposalRow
from catchup.db.models import KnowledgeArtifactRevision as RevisionRow
from catchup.db.models import KnowledgeBlockVerdict as VerdictRow
from catchup.db.models import KnowledgeClaimCandidate as ClaimRow
from catchup.db.models import KnowledgeExtractionRun as RunRow
from catchup.db.models import KnowledgeMutationOperation as OperationRow
from catchup.db.models import KnowledgeNode as NodeRow
from catchup.db.models import KnowledgeOntologySnapshot as SnapshotRow
from catchup.db.models import Workspace
from catchup.knowledge_maintenance.adapters.postgres.unit_of_work import (
    KnowledgeMaintenanceUnitOfWork,
)
from catchup.knowledge_maintenance.domain.artifact import BLOCK_KIND_CLAIM_SECTION
from catchup.knowledge_maintenance.domain.artifact import BLOCK_KIND_CONTESTED
from catchup.knowledge_maintenance.domain.artifact import ArtifactBlock
from catchup.knowledge_maintenance.domain.artifact import BlockSource
from catchup.knowledge_maintenance.domain.artifact import ContestedVariant
from catchup.knowledge_maintenance.domain.artifact import artifact_idempotency_key
from catchup.knowledge_maintenance.domain.artifact import block_content_hash
from catchup.knowledge_maintenance.domain.artifact import blocks_content_hash
from catchup.knowledge_maintenance.domain.artifact import deserialize_blocks
from catchup.knowledge_maintenance.services.publish_artifact_proposal import (
    CODE_CONFLICT_RACE,
)
from catchup.knowledge_maintenance.services.publish_artifact_proposal import (
    CODE_STALE_BLOCK,
)
from catchup.knowledge_maintenance.services.publish_artifact_proposal import (
    PublishError,
)
from catchup.knowledge_maintenance.services.publish_artifact_proposal import (
    publish_artifact_proposal,
)
from catchup.knowledge_maintenance.services.review_block_verdict import (
    upsert_block_verdict,
)
from catchup.knowledge_maintenance.services.review_contradiction_proposal import (
    review_contradiction_proposal,
)
from catchup.tests.knowledge_maintenance.test_artifact_definition_schema import (
    _definition_with_channel,
)

REVIEWER = "tester"


@dataclass(frozen=True, slots=True)
class _Seed:
    """심어 둔 변경안 한 벌과 그것이 가리키는 것들을 함께 담는다."""

    artifact_id: uuid.UUID
    proposal_id: uuid.UUID
    blocks: tuple[ArtifactBlock, ...]
    release_contradiction: uuid.UUID
    owner_contradiction: uuid.UUID
    release_claims: tuple[uuid.UUID, uuid.UUID]
    owner_claims: tuple[uuid.UUID, uuid.UUID]
    calm_claim: uuid.UUID


@pytest.fixture(scope="module")
def engine() -> Iterator[Engine]:
    engine = create_engine(settings.sqlalchemy_database_url)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except OperationalError:
        engine.dispose()
        pytest.skip("PostgreSQL이 없어 통합 테스트를 건너뛴다.")

    if not inspect(engine).has_table(VerdictRow.__tablename__):
        engine.dispose()
        pytest.skip("블록 결정 테이블이 없다. alembic upgrade head가 필요하다.")

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
    """한 연결 위 savepoint로 세션을 낸다. 끝나면 전부 되감는다."""
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
def seed(
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
    workspace_id: int,
) -> _Seed:
    """다툼 블록 둘을 품은 계류 변경안 한 벌을 실 DB에 심는다."""
    with session_factory() as session:
        run_id = _extraction_run(session, workspace_id)
        node_id = _entity_node(session, workspace_id)
        release = (
            _claim(
                session, workspace_id, run_id, node_id,
                "release_month", "2026-09",
            ),
            _claim(
                session, workspace_id, run_id, node_id,
                "release_month", "2026-10",
            ),
        )
        owner = (
            _claim(
                session, workspace_id, run_id, node_id, "owner", "결제팀"
            ),
            _claim(
                session, workspace_id, run_id, node_id, "owner", "정산팀"
            ),
        )
        calm = _claim(
            session, workspace_id, run_id, node_id, "status", "운영 중"
        )
        session.commit()

    definition = _definition_with_channel(session_factory, workspace_id)
    with uow_factory() as uow:
        release_contradiction = _contradiction(
            uow, workspace_id, node_id, "release_month", release
        )
        owner_contradiction = _contradiction(
            uow, workspace_id, node_id, "owner", owner
        )
        artifact_id = uow.artifacts.get_or_create_definition_artifact(
            definition_id=definition.id,
            channel_id=definition.channel_id,
            kind=definition.kind,
            subject_node_id=node_id,
            title="결제 기능",
        )
        blocks = (
            _claim_section(calm),
            _contested("release_month", release, release_contradiction),
            _contested("owner", owner, owner_contradiction),
        )
        content_hash = blocks_content_hash(blocks)
        proposal_id = uow.artifacts.add_or_revive_proposal(
            artifact_id=artifact_id,
            blocks=blocks,
            content_hash=content_hash,
            idempotency_key=artifact_idempotency_key(
                artifact_id, content_hash, base_revision_id=None
            ),
            base_revision_id=None,
        )
        uow.commit()

    return _Seed(
        artifact_id=artifact_id,
        proposal_id=proposal_id,
        blocks=blocks,
        release_contradiction=release_contradiction,
        owner_contradiction=owner_contradiction,
        release_claims=release,
        owner_claims=owner,
        calm_claim=calm,
    )


def test_publish_commits_revision_and_contradiction_decisions_together(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
    seed: _Seed,
) -> None:
    """발행 한 번이 판·변경안 상태·파생 모순 결정을 함께 남긴다.

    파생 결정 서비스는 스스로 commit하려 든다. 그 경계를 발행이 삼키지
    못하면 결정만 먼저 확정되거나 발행의 commit이 갈 곳을 잃는다.
    """
    _approve_all(uow_factory, seed)

    result = publish_artifact_proposal(
        uow_factory(),
        workspace_id=workspace_id,
        proposal_id=seed.proposal_id,
        base_revision_id=None,
        reviewer=REVIEWER,
    )

    assert result.verdict == "approved"
    assert result.revision_number == 1
    assert result.contradictions_resolved == 2
    # 평범한 절 하나와 실체화된 다툼 승자 둘이 판에 오른다.
    assert result.blocks_published == 3
    assert result.claims_accepted == 3

    with session_factory() as session:
        proposal = session.get(ProposalRow, seed.proposal_id)
        assert proposal is not None
        assert proposal.status == "approved"
        assert proposal.reviewer == REVIEWER

        revision = session.get(RevisionRow, result.revision_id)
        assert revision is not None
        stored = deserialize_blocks(revision.blocks)
        # 다툼은 승자만 남은 평범한 절로 바뀌어 실린다.
        assert [block.block_kind for block in stored] == [
            BLOCK_KIND_CLAIM_SECTION
        ] * 3
        assert stored[1].claim_ids == (seed.release_claims[0],)
        assert stored[2].claim_ids == (seed.owner_claims[0],)

        accepted = set(
            session.scalars(
                select(ClaimRow.id).where(
                    ClaimRow.resolution_status == "accepted",
                    ClaimRow.id.in_(
                        [
                            seed.calm_claim,
                            *seed.release_claims,
                            *seed.owner_claims,
                        ]
                    ),
                )
            ).all()
        )
        # 패자는 발행이 확정하지 않는다. 닫는 일은 apply의 몫이다.
        assert accepted == {
            seed.calm_claim,
            seed.release_claims[0],
            seed.owner_claims[0],
        }

    with uow_factory() as uow:
        for contradiction_id in (
            seed.release_contradiction,
            seed.owner_contradiction,
        ):
            assert (
                uow.mutation_proposals.get_contradiction_status(
                    workspace_id=workspace_id,
                    proposal_id=contradiction_id,
                )
                == "approved"
            )

    with session_factory() as session:
        # 파생 결정은 패자를 닫을 적용 명령을 함께 남긴다.
        operations = session.scalars(
            select(OperationRow.operation_type).where(
                OperationRow.proposal_id.in_(
                    [seed.release_contradiction, seed.owner_contradiction]
                )
            )
        ).all()
        assert len(operations) == 2


def test_publish_rolls_back_earlier_contradiction_decision(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
    seed: _Seed,
) -> None:
    """둘째 다툼이 막히면 첫째 다툼의 결정까지 함께 되감긴다.

    둘째 안건을 미리 결정해 두면 발행은 첫째를 확정한 뒤 둘째에서
    CONFLICT_RACE로 막힌다. 그때 첫째 결정이 남으면, 문서에는 실리지
    않은 값으로 지식 원장만 닫혀 문서와 원장의 앎이 갈린다.
    """
    _approve_all(uow_factory, seed)

    # 다른 검토자가 둘째 안건을 먼저 끝내 둔 상태를 만든다.
    review_contradiction_proposal(
        uow_factory(),
        workspace_id=workspace_id,
        proposal_id=seed.owner_contradiction,
        winner_claim_id=seed.owner_claims[1],
        reviewer="first",
    )

    with pytest.raises(PublishError) as raised:
        publish_artifact_proposal(
            uow_factory(),
            workspace_id=workspace_id,
            proposal_id=seed.proposal_id,
            base_revision_id=None,
            reviewer=REVIEWER,
        )

    assert raised.value.code == CODE_CONFLICT_RACE

    with uow_factory() as uow:
        # 첫째 안건은 발행이 손대기 전 상태로 돌아와 있어야 한다.
        assert (
            uow.mutation_proposals.get_contradiction_status(
                workspace_id=workspace_id,
                proposal_id=seed.release_contradiction,
            )
            == "pending"
        )

    with session_factory() as session:
        assert (
            session.scalars(
                select(RevisionRow).where(
                    RevisionRow.artifact_id == seed.artifact_id
                )
            ).all()
            == []
        )
        proposal = session.get(ProposalRow, seed.proposal_id)
        assert proposal is not None
        assert proposal.status == "pending"
        assert proposal.reviewer is None
        # 첫째 안건에는 적용 명령도 남지 않는다.
        assert (
            session.scalars(
                select(OperationRow.id).where(
                    OperationRow.proposal_id == seed.release_contradiction
                )
            ).all()
            == []
        )
        # 승인해 둔 블록 결정은 발행 실패와 무관하게 저널에 남는다.
        assert (
            len(
                session.scalars(
                    select(VerdictRow.block_index).where(
                        VerdictRow.proposal_id == seed.proposal_id
                    )
                ).all()
            )
            == 3
        )


def test_publish_rolls_back_bulk_verdicts_when_publish_fails(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
    seed: _Seed,
) -> None:
    """일괄 승인이 적힌 뒤 발행이 막히면 그 판정 기록까지 되감긴다.

    사람이 미리 남긴 결정 하나의 지문을 본문과 어긋나게 심어 둔다. 발행은
    미결정 블록에 승인을 먼저 적고, 그다음 지문 검사에서 STALE_BLOCK으로
    막힌다. 두 쓰기가 한 transaction이 아니면 발행되지 않은 문서에 일괄
    승인만 남아, 다음 발행이 사람이 읽지도 않은 블록을 이미 결정된 것으로
    읽는다.

    지문이 어긋난 행은 저장소에 직접 넣는다. 단건 결정 서비스는 지문이
    다르면 거절하므로 이 상태를 서비스로는 만들 수 없다.
    """
    decided_at = datetime(2026, 8, 18, 9, 0, tzinfo=timezone.utc)

    with uow_factory() as uow:
        # 다툼 블록 둘만 사람이 미리 결정해 둔다. 첫 블록은 미결정으로
        # 남아 일괄 승인이 적을 자리가 된다.
        uow.block_verdicts.insert_verdict_if_absent(
            proposal_id=seed.proposal_id,
            block_index=1,
            block_content_hash="어긋난 지문",
            verdict="approved",
            rejection_reason=None,
            chosen_winner_claim_id=seed.release_claims[0],
            reviewer="user:human",
            reviewed_at=decided_at,
        )
        uow.block_verdicts.insert_verdict_if_absent(
            proposal_id=seed.proposal_id,
            block_index=2,
            block_content_hash=block_content_hash(seed.blocks[2]),
            verdict="approved",
            rejection_reason=None,
            chosen_winner_claim_id=seed.owner_claims[0],
            reviewer="user:human",
            reviewed_at=decided_at,
        )
        uow.commit()

    with pytest.raises(PublishError) as raised:
        publish_artifact_proposal(
            uow_factory(),
            workspace_id=workspace_id,
            proposal_id=seed.proposal_id,
            base_revision_id=None,
            reviewer=REVIEWER,
            undecided="approve",
        )

    assert raised.value.code == CODE_STALE_BLOCK

    with session_factory() as session:
        rows = list(
            session.scalars(
                select(VerdictRow)
                .where(VerdictRow.proposal_id == seed.proposal_id)
                .order_by(VerdictRow.block_index)
            )
        )
        proposal = session.get(ProposalRow, seed.proposal_id)

    # 미리 있던 사람의 결정 둘만 남는다. 일괄 승인이 적으려던 첫 블록에는
    # 행이 생기지 않는다.
    assert [row.block_index for row in rows] == [1, 2]
    assert {row.reviewer for row in rows} == {"user:human"}
    assert proposal is not None
    assert proposal.status == "pending"


def test_insert_verdict_if_absent_never_touches_an_existing_verdict(
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
    seed: _Seed,
) -> None:
    """없을 때만 쓰기는 첫 번만 들어가고 이미 있는 행은 한 컬럼도 안 바꾼다.

    일괄 처리가 이 함수만 쓰므로, 이 성질이 사람의 결정을 지키는 마지막
    울타리다. `ON CONFLICT DO NOTHING`이 실제 UNIQUE 위에서 그렇게 도는지
    실 DB로 본다.
    """
    block = seed.blocks[0]
    decided_at = datetime(2026, 8, 18, 9, 0, tzinfo=timezone.utc)

    with uow_factory() as uow:
        first = uow.block_verdicts.insert_verdict_if_absent(
            proposal_id=seed.proposal_id,
            block_index=0,
            block_content_hash=block_content_hash(block),
            verdict="rejected",
            rejection_reason="사람이 직접 반려했다",
            chosen_winner_claim_id=None,
            reviewer="user:human",
            reviewed_at=decided_at,
        )
        uow.commit()

    with uow_factory() as uow:
        second = uow.block_verdicts.insert_verdict_if_absent(
            proposal_id=seed.proposal_id,
            block_index=0,
            block_content_hash="다른 지문",
            verdict="approved",
            rejection_reason=None,
            chosen_winner_claim_id=None,
            reviewer="user:bulk",
            reviewed_at=datetime(2026, 8, 18, 10, 0, tzinfo=timezone.utc),
        )
        uow.commit()

    assert first is True
    assert second is False

    with session_factory() as session:
        rows = list(
            session.scalars(
                select(VerdictRow).where(
                    VerdictRow.proposal_id == seed.proposal_id,
                    VerdictRow.block_index == 0,
                )
            )
        )

    assert len(rows) == 1
    stored = rows[0]
    assert stored.verdict == "rejected"
    assert stored.rejection_reason == "사람이 직접 반려했다"
    assert stored.reviewer == "user:human"
    assert stored.block_content_hash == block_content_hash(block)


def test_unchanged_block_publishes_without_a_verdict_row(
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
    workspace_id: int,
) -> None:
    """미변경 블록은 결정 행 없이 새 판에 실린다.

    fake는 저장소를 dict로 들고 있어 결정 행이 실제로 안 생겼는지까지는
    보여 주지 못한다. 면제가 자동 승인으로 새지 않았는지, 즉 사람이
    결정하지 않은 블록에 결정 저널이 비어 있는지를 실 DB로 본다.
    """
    with session_factory() as session:
        run_id = _extraction_run(session, workspace_id)
        node_id = _entity_node(session, workspace_id)
        kept_claim = _claim(
            session, workspace_id, run_id, node_id, "status", "운영 중"
        )
        changed_claim = _claim(
            session, workspace_id, run_id, node_id, "owner", "결제팀"
        )
        session.commit()

    definition = _definition_with_channel(session_factory, workspace_id)
    kept = _section(kept_claim, "status", "운영 중입니다.")
    old = _section(changed_claim, "owner", "담당은 결제팀입니다.")
    with uow_factory() as uow:
        artifact_id = uow.artifacts.get_or_create_definition_artifact(
            definition_id=definition.id,
            channel_id=definition.channel_id,
            kind=definition.kind,
            subject_node_id=node_id,
            title="결제 기능",
        )
        first_id = _add_proposal(uow, artifact_id, (kept, old), None)
        uow.commit()

    _approve_blocks(uow_factory, first_id, (kept, old))
    first = publish_artifact_proposal(
        uow_factory(),
        workspace_id=workspace_id,
        proposal_id=first_id,
        base_revision_id=None,
        reviewer=REVIEWER,
    )

    changed = _section(changed_claim, "owner", "담당은 정산팀입니다.")
    with uow_factory() as uow:
        second_id = _add_proposal(
            uow, artifact_id, (kept, changed), first.revision_id
        )
        uow.commit()

    # 검토자는 화면에 변경으로 보인 둘째 블록만 결정한다.
    upsert_block_verdict(
        uow_factory(),
        proposal_id=second_id,
        block_index=1,
        block_content_hash_seen=block_content_hash(changed),
        verdict="approved",
        rejection_reason=None,
        chosen_winner_claim_id=None,
        reviewer=REVIEWER,
    )

    second = publish_artifact_proposal(
        uow_factory(),
        workspace_id=workspace_id,
        proposal_id=second_id,
        base_revision_id=first.revision_id,
        reviewer=REVIEWER,
    )

    assert second.verdict == "approved"
    assert second.blocks_published == 2
    assert second.blocks_rejected == 0
    assert second.revision_number == 2

    with session_factory() as session:
        revision = session.get(RevisionRow, second.revision_id)
        rows = list(
            session.scalars(
                select(VerdictRow).where(VerdictRow.proposal_id == second_id)
            )
        )

    assert revision is not None
    published = deserialize_blocks(revision.blocks)
    assert [block.heading for block in published] == ["status", "owner"]
    assert published[0].body == "운영 중입니다."
    assert published[1].body == "담당은 정산팀입니다."
    # 면제는 자동 승인이 아니다. 사람이 결정한 블록에만 저널이 남는다.
    assert [row.block_index for row in rows] == [1]


def _add_proposal(
    uow: KnowledgeMaintenanceUnitOfWork,
    artifact_id: uuid.UUID,
    blocks: tuple[ArtifactBlock, ...],
    base_revision_id: uuid.UUID | None,
) -> uuid.UUID:
    """블록 한 벌을 계류 변경안으로 심는다."""
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


def _approve_blocks(
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
    proposal_id: uuid.UUID,
    blocks: tuple[ArtifactBlock, ...],
) -> None:
    """다툼이 없는 블록 한 벌을 모두 승인으로 적는다."""
    for index, block in enumerate(blocks):
        upsert_block_verdict(
            uow_factory(),
            proposal_id=proposal_id,
            block_index=index,
            block_content_hash_seen=block_content_hash(block),
            verdict="approved",
            rejection_reason=None,
            chosen_winner_claim_id=None,
            reviewer=REVIEWER,
        )


def _section(claim_id: uuid.UUID, heading: str, body: str) -> ArtifactBlock:
    """제목과 본문을 지정한 평범한 절을 하나 만든다."""
    return ArtifactBlock(
        block_kind=BLOCK_KIND_CLAIM_SECTION,
        heading=heading,
        body=body,
        claim_ids=(claim_id,),
        proposal_ids=(),
        ontology_version="1",
        sources=(_source(claim_id, body),),
    )


def _approve_all(
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
    seed: _Seed,
) -> None:
    """블록 셋을 모두 승인으로 적는다. 다툼은 첫 후보를 승자로 고른다."""
    for index, block in enumerate(seed.blocks):
        winner = (
            block.variants[0].claim_id
            if block.block_kind == BLOCK_KIND_CONTESTED
            else None
        )
        upsert_block_verdict(
            uow_factory(),
            proposal_id=seed.proposal_id,
            block_index=index,
            block_content_hash_seen=block_content_hash(block),
            verdict="approved",
            rejection_reason=None,
            chosen_winner_claim_id=winner,
            reviewer=REVIEWER,
        )


def _entity_node(session: Session, workspace_id: int) -> uuid.UUID:
    """canonical entity 노드를 하나 만든다."""
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


def _claim(
    session: Session,
    workspace_id: int,
    run_id: uuid.UUID,
    node_id: uuid.UUID,
    predicate: str,
    value: str,
) -> uuid.UUID:
    """어떤 노드에 붙는 계류 claim 후보를 하나 만든다."""
    row = ClaimRow(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        extraction_run_id=run_id,
        local_key=f"c-{uuid.uuid4().hex}",
        subject_node_id=node_id,
        predicate=predicate,
        value_type="string",
        value=value,
        value_hash=uuid.uuid4().hex * 2,
        statement=f"{predicate}는 {value}입니다.",
        ontology_id="test",
        ontology_version="1",
        extraction_method="llm",
    )
    session.add(row)
    session.flush()
    return row.id


def _contradiction(
    uow: KnowledgeMaintenanceUnitOfWork,
    workspace_id: int,
    node_id: uuid.UUID,
    predicate: str,
    claim_ids: tuple[uuid.UUID, uuid.UUID],
) -> uuid.UUID:
    """값이 갈린 claim 둘을 후보로 삼는 모순 안건을 하나 쓴다."""
    return uow.mutation_proposals.add_contradiction_proposal(
        workspace_id=workspace_id,
        idempotency_key=f"contradiction-{uuid.uuid4().hex}",
        trigger_claim_candidate_id=claim_ids[0],
        detector="test",
        detector_version="1",
        summary=f"'{predicate}' 값이 2종으로 갈린다",
        resolver_metadata={
            "subject_key": f"node:{node_id}",
            "predicate": predicate,
            "values": [
                {
                    "claim_id": str(claim_id),
                    "value": f"값 {index}",
                    "normalized": f"값 {index}",
                    "statement": f"{predicate} 후보 {index}입니다.",
                    "observed_at": "2026-07-01T00:00:00+00:00",
                }
                for index, claim_id in enumerate(claim_ids)
            ],
        },
    )


def _claim_section(claim_id: uuid.UUID) -> ArtifactBlock:
    """다툼이 없는 평범한 절을 하나 만든다."""
    return ArtifactBlock(
        block_kind=BLOCK_KIND_CLAIM_SECTION,
        heading="status",
        body="운영 중입니다.",
        claim_ids=(claim_id,),
        proposal_ids=(),
        ontology_version="1",
        sources=(_source(claim_id, "운영 중입니다."),),
    )


def _contested(
    predicate: str,
    claim_ids: tuple[uuid.UUID, uuid.UUID],
    contradiction_id: uuid.UUID,
) -> ArtifactBlock:
    """값이 갈린 후보 둘을 나란히 놓은 다툼 블록을 만든다."""
    return ArtifactBlock(
        block_kind=BLOCK_KIND_CONTESTED,
        heading=predicate,
        body="상충하는 값 2개 — 검토 필요",
        claim_ids=claim_ids,
        proposal_ids=(contradiction_id,),
        ontology_version="1",
        sources=tuple(
            _source(claim_id, f"{predicate} 후보 {index}입니다.")
            for index, claim_id in enumerate(claim_ids)
        ),
        variants=tuple(
            ContestedVariant(
                claim_id=claim_id,
                body=f"{predicate} 후보 {index}입니다.",
                sources=(
                    _source(claim_id, f"{predicate} 후보 {index}입니다."),
                ),
            )
            for index, claim_id in enumerate(claim_ids)
        ),
    )


def _source(claim_id: uuid.UUID, statement: str) -> BlockSource:
    """근거 인용 하나를 만든다."""
    return BlockSource(
        claim_id=claim_id,
        statement=statement,
        observed_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
        citation_verified=True,
    )
