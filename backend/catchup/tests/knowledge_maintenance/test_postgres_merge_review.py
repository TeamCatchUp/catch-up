"""병합 결정 저널을 실 PostgreSQL에서 확인한다.

결정 UPDATE의 낙관적 가드, 결정된 행의 불변, 되살리기 시 결정 흔적
초기화는 전부 실 DB의 행 재평가 위에서만 증명된다.
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
from catchup.db.models import KnowledgeClaimCandidate as ClaimRow
from catchup.db.models import KnowledgeEntityCandidate as CandidateRow
from catchup.db.models import KnowledgeMutationOperation as OperationRow
from catchup.db.models import KnowledgeMutationProposal as ProposalRow
from catchup.db.models import KnowledgeNode as KnowledgeNodeRow
from catchup.db.models import KnowledgeNodeAlias as AliasRow
from catchup.db.models import Workspace
from catchup.knowledge_maintenance.adapters.postgres.repositories import (
    SqlAlchemyKnowledgeCandidateRepository,
)
from catchup.knowledge_maintenance.adapters.postgres.unit_of_work import (
    KnowledgeMaintenanceUnitOfWork,
)
from catchup.knowledge_maintenance.domain.artifact import BLOCK_KIND_CLAIM_SECTION
from catchup.knowledge_maintenance.domain.artifact import ArtifactBlock
from catchup.knowledge_maintenance.domain.artifact import artifact_idempotency_key
from catchup.knowledge_maintenance.domain.artifact import blocks_content_hash
from catchup.knowledge_maintenance.domain.entity_resolution import normalize_name
from catchup.knowledge_maintenance.services.apply_mutation_proposals import (
    apply_mutation_proposals,
)
from catchup.knowledge_maintenance.services.review_artifact_proposal import (
    review_artifact_proposal,
)
from catchup.knowledge_maintenance.services.review_merge_proposal import (
    MergeReviewError,
)
from catchup.knowledge_maintenance.services.review_merge_proposal import (
    review_merge_proposal,
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


def _merge_proposal(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> tuple[uuid.UUID, str, uuid.UUID, uuid.UUID]:
    """실제 후보 위에 병합 안건 하나를 만든다."""
    observation = _stored_observation(workspace_id, session_factory)
    stored = store_knowledge_candidates(
        observation,
        _batch(),
        spec=SPEC,
        uow=uow_factory(),
    ).batch
    representative = stored.entity_ids["e1"]
    other = stored.entity_ids["e2"]
    key = f"merge:{uuid.uuid4().hex}"
    with uow_factory() as uow:
        proposal_id = uow.mutation_proposals.add_duplicate_proposal(
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
    return proposal_id, key, representative, other


def _readd_same_key(
    uow: KnowledgeMaintenanceUnitOfWork,
    *,
    workspace_id: int,
    key: str,
    representative: uuid.UUID,
    other: uuid.UUID,
) -> uuid.UUID:
    """judge 재실행이 같은 key로 안건을 다시 쓰는 상황을 재현한다."""
    return uow.mutation_proposals.add_duplicate_proposal(
        workspace_id=workspace_id,
        idempotency_key=key,
        trigger_entity_candidate_id=representative,
        detector="catchup.name_group_judge",
        detector_version="2",
        summary="재실행이 다시 쓴 병합",
        resolver_metadata={"member_hash": "def"},
        representative_candidate_id=representative,
        merge_candidate_ids=(other,),
        proposed_type="feature",
        proposed_name="결제 기능",
    )


def test_approve_and_reject_record_journal(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """승인·반려가 결정 저널로 남는다."""
    approved_id, *_ = _merge_proposal(
        workspace_id, session_factory, uow_factory
    )
    rejected_id, *_ = _merge_proposal(
        workspace_id, session_factory, uow_factory
    )

    review_merge_proposal(
        uow_factory(),
        workspace_id=workspace_id,
        proposal_id=approved_id,
        verdict="approved",
        reviewer="ba2slk",
    )
    review_merge_proposal(
        uow_factory(),
        workspace_id=workspace_id,
        proposal_id=rejected_id,
        verdict="rejected",
        reviewer="ba2slk",
        reason="다른 기능이다",
    )

    with session_factory() as session:
        approved = session.get(ProposalRow, approved_id)
        rejected = session.get(ProposalRow, rejected_id)
    assert approved is not None and rejected is not None
    assert approved.status == "approved"
    assert approved.reviewer == "ba2slk"
    assert approved.reviewed_at is not None
    assert rejected.status == "rejected"
    assert rejected.rejection_reason == "다른 기능이다"


def test_second_decision_loses_and_changes_nothing(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """먼저 확정된 결정을 나중 결정이 덮지 못한다."""
    proposal_id, *_ = _merge_proposal(
        workspace_id, session_factory, uow_factory
    )
    review_merge_proposal(
        uow_factory(),
        workspace_id=workspace_id,
        proposal_id=proposal_id,
        verdict="approved",
        reviewer="first",
    )

    with pytest.raises(MergeReviewError):
        review_merge_proposal(
            uow_factory(),
            workspace_id=workspace_id,
            proposal_id=proposal_id,
            verdict="rejected",
            reviewer="second",
            reason="번복 시도",
        )

    with session_factory() as session:
        row = session.get(ProposalRow, proposal_id)
    assert row is not None
    assert row.status == "approved"
    assert row.reviewer == "first"
    assert row.rejection_reason is None


def test_decided_row_survives_judge_rerun(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """judge 재실행이 결정된 안건을 되살리지 못한다."""
    proposal_id, key, representative, other = _merge_proposal(
        workspace_id, session_factory, uow_factory
    )
    review_merge_proposal(
        uow_factory(),
        workspace_id=workspace_id,
        proposal_id=proposal_id,
        verdict="rejected",
        reviewer="ba2slk",
        reason="다른 기능이다",
    )

    with uow_factory() as uow:
        returned = _readd_same_key(
            uow,
            workspace_id=workspace_id,
            key=key,
            representative=representative,
            other=other,
        )
        uow.commit()

    assert returned == proposal_id
    with session_factory() as session:
        row = session.get(ProposalRow, proposal_id)
        operations = session.scalars(
            select(OperationRow).where(
                OperationRow.proposal_id == proposal_id
            )
        ).all()
    assert row is not None
    assert row.status == "rejected"
    assert row.summary == "같은 이름 후보 병합"
    assert row.rejection_reason == "다른 기능이다"
    # 결정된 안건의 operations도 그대로 남아야 한다. 지워지면 감사
    # 기록이 가리키는 적용 계획이 사라진다.
    assert len(operations) == 2


def test_revive_clears_decision_fields(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """접힌 안건을 되살리면 이전 결정 흔적이 지워진다."""
    proposal_id, key, representative, other = _merge_proposal(
        workspace_id, session_factory, uow_factory
    )
    with uow_factory() as uow:
        uow.mutation_proposals.abandon(proposal_id=proposal_id)
        uow.commit()
    # 접힌 행에 결정 흔적이 남은 이상 상태를 임의로 만든다.
    with session_factory() as session:
        row = session.get(ProposalRow, proposal_id)
        assert row is not None
        row.reviewer = "ghost"
        row.rejection_reason = "옛 사유"
        session.commit()

    with uow_factory() as uow:
        returned = _readd_same_key(
            uow,
            workspace_id=workspace_id,
            key=key,
            representative=representative,
            other=other,
        )
        uow.commit()

    assert returned == proposal_id
    with session_factory() as session:
        row = session.get(ProposalRow, proposal_id)
    assert row is not None
    assert row.status == "pending"
    assert row.reviewer is None
    assert row.reviewed_at is None
    assert row.rejection_reason is None
    assert row.applied_at is None


def test_list_pending_duplicates_renders_members_in_order(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """계류 병합 안건이 후보 상세를 sequence 순으로 싣는다."""
    proposal_id, _, representative, other = _merge_proposal(
        workspace_id, session_factory, uow_factory
    )

    with uow_factory() as uow:
        listed = uow.mutation_proposals.list_pending_duplicates(
            workspace_id=workspace_id,
        )

    match = [item for item in listed if item.id == proposal_id]
    assert len(match) == 1
    candidates = match[0].candidates
    assert [candidate.id for candidate in candidates] == [
        representative,
        other,
    ]
    assert candidates[0].proposed_name
    assert candidates[0].proposed_type
    assert candidates[0].resolution_status == "pending"


def test_contradiction_is_not_decidable_here(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """모순 안건은 병합 결정 경로로 결정할 수 없다."""
    observation = _stored_observation(workspace_id, session_factory)
    stored = store_knowledge_candidates(
        observation,
        _batch(),
        spec=SPEC,
        uow=uow_factory(),
    ).batch
    trigger = next(iter(stored.claim_ids.values()))
    with uow_factory() as uow:
        contradiction_id = uow.mutation_proposals.add_contradiction_proposal(
            workspace_id=workspace_id,
            idempotency_key=f"contradiction:{uuid.uuid4().hex}",
            trigger_claim_candidate_id=trigger,
            detector="catchup.claim_conflict",
            detector_version="1",
            summary="값이 갈린다",
            resolver_metadata={},
        )
        uow.commit()

    with pytest.raises(MergeReviewError):
        review_merge_proposal(
            uow_factory(),
            workspace_id=workspace_id,
            proposal_id=contradiction_id,
            verdict="approved",
            reviewer="ba2slk",
        )
    with session_factory() as session:
        row = session.get(ProposalRow, contradiction_id)
    assert row is not None
    assert row.status == "pending"


def test_apply_resolves_candidates_on_real_rows(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """승인된 안건이 실 DB에서 적용되어 후보가 해소된다."""
    proposal_id, _, representative, other = _merge_proposal(
        workspace_id, session_factory, uow_factory
    )
    review_merge_proposal(
        uow_factory(),
        workspace_id=workspace_id,
        proposal_id=proposal_id,
        verdict="approved",
        reviewer="ba2slk",
    )

    result = apply_mutation_proposals(uow_factory, workspace_id=workspace_id)

    assert result.proposals_applied >= 1
    with session_factory() as session:
        row = session.get(ProposalRow, proposal_id)
        assert row is not None
        assert row.status == "applied"
        assert row.applied_at is not None
        rep = session.get(CandidateRow, representative)
        member = session.get(CandidateRow, other)
    assert rep is not None and member is not None
    assert rep.resolution_status == "accepted"
    assert member.resolution_status == "merged"
    assert rep.resolved_node_id == member.resolved_node_id
    assert rep.resolved_node_id is not None

    rerun = apply_mutation_proposals(uow_factory, workspace_id=workspace_id)
    assert rerun.proposals_applied == 0
    assert rerun.candidates_resolved == 0


def test_apply_writes_name_alias_for_created_node(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """적용이 만든 노드는 실 DB에서도 이름으로 찾을 수 있다."""
    proposal_id, _, representative, _other = _merge_proposal(
        workspace_id, session_factory, uow_factory
    )
    review_merge_proposal(
        uow_factory(),
        workspace_id=workspace_id,
        proposal_id=proposal_id,
        verdict="approved",
        reviewer="ba2slk",
    )

    apply_mutation_proposals(uow_factory, workspace_id=workspace_id)

    with session_factory() as session:
        rep = session.get(CandidateRow, representative)
        assert rep is not None and rep.resolved_node_id is not None
        node_id = rep.resolved_node_id
        node = session.get(KnowledgeNodeRow, node_id)
        rows = list(
            session.execute(
                select(AliasRow).where(AliasRow.node_id == node_id)
            ).scalars()
        )
    assert node is not None
    assert node.canonical_key is None
    assert len(rows) == 1
    assert rows[0].alias == "결제 기능"
    assert rows[0].normalized_alias == normalize_name("결제 기능")
    assert rows[0].source == "system"

    # 읽기 경로가 그 이름으로 노드를 실제로 찾아낸다.
    with uow_factory() as uow:
        found = uow.knowledge_nodes.find_entity_by_normalized_alias(
            workspace_id=workspace_id,
            normalized_alias=normalize_name("결제 기능"),
        )
    assert found is not None and found.id == node_id

    apply_mutation_proposals(uow_factory, workspace_id=workspace_id)
    with session_factory() as session:
        rerun_rows = list(
            session.execute(
                select(AliasRow).where(AliasRow.node_id == node_id)
            ).scalars()
        )
    assert len(rerun_rows) == 1


def test_apply_isolates_failing_proposal(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """미지 명령을 가진 안건만 실패하고 나머지는 적용된다."""
    good_id, _, good_rep, good_member = _merge_proposal(
        workspace_id, session_factory, uow_factory
    )
    bad_id, _, bad_rep, _bad_member = _merge_proposal(
        workspace_id, session_factory, uow_factory
    )
    for proposal_id in (good_id, bad_id):
        review_merge_proposal(
            uow_factory(),
            workspace_id=workspace_id,
            proposal_id=proposal_id,
            verdict="approved",
            reviewer="ba2slk",
        )
    # 실패 유도: bad 안건에 이 슬라이스가 지원하지 않는 명령을 심는다.
    with session_factory() as session:
        session.add(
            OperationRow(
                id=uuid.uuid4(),
                workspace_id=workspace_id,
                proposal_id=bad_id,
                sequence=9,
                operation_type="invalidate_claim",
                operation_data={},
            )
        )
        session.commit()

    result = apply_mutation_proposals(uow_factory, workspace_id=workspace_id)

    assert result.proposals_applied == 1
    assert result.proposals_failed == 1
    with session_factory() as session:
        good = session.get(ProposalRow, good_id)
        bad = session.get(ProposalRow, bad_id)
        bad_rep_row = session.get(CandidateRow, bad_rep)
    assert good is not None and bad is not None
    assert good.status == "applied"
    assert bad.status == "approved"
    assert bad_rep_row is not None
    assert bad_rep_row.resolved_node_id is None


def _artifact_proposal_over_claim(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> tuple[uuid.UUID, uuid.UUID]:
    """실 claim을 근거로 실은 문서 변경안을 만든다."""
    observation = _stored_observation(workspace_id, session_factory)
    stored = store_knowledge_candidates(
        observation,
        _batch(),
        spec=SPEC,
        uow=uow_factory(),
    ).batch
    claim_id = next(iter(stored.claim_ids.values()))
    blocks = (
        ArtifactBlock(
            block_kind=BLOCK_KIND_CLAIM_SECTION,
            heading="release_month",
            body="2026-09",
            claim_ids=(claim_id,),
            proposal_ids=(),
            ontology_version="2",
        ),
    )
    with uow_factory() as uow:
        node = uow.knowledge_nodes.create_entity_node(
            workspace_id=workspace_id,
            entity_type="feature",
            canonical_key=f"test:feature:{uuid.uuid4().hex}",
            display_name="결제 기능",
        )
        artifact_id = uow.artifacts.get_or_create_artifact(
            kind="entity_summary",
            subject_node_id=node.id,
            title="결제 기능",
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
    return proposal_id, claim_id


def test_document_approval_accepts_backing_claims(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """문서 승인이 근거 claim을 확정하고 valid_from을 채운다."""
    proposal_id, claim_id = _artifact_proposal_over_claim(
        workspace_id, session_factory, uow_factory
    )

    result = review_artifact_proposal(
        uow_factory(),
        proposal_id=proposal_id,
        verdict="approved",
        reviewer="ba2slk",
    )

    assert result.claims_accepted == 1
    with session_factory() as session:
        claim = session.get(ClaimRow, claim_id)
    assert claim is not None
    assert claim.resolution_status == "accepted"
    # 테스트 관찰은 occurred_at을 갖고 있으므로 valid_from이 그 시각으로
    # 채워져야 한다.
    assert claim.valid_from is not None


def test_approval_rolls_back_when_acceptance_fails(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """claim 확정이 터지면 판·승인까지 함께 되감긴다."""
    proposal_id, claim_id = _artifact_proposal_over_claim(
        workspace_id, session_factory, uow_factory
    )

    def _boom(self, *, claim_ids):
        raise RuntimeError("확정 실패 재현")

    monkeypatch.setattr(
        SqlAlchemyKnowledgeCandidateRepository, "accept_claims", _boom
    )

    with pytest.raises(RuntimeError):
        review_artifact_proposal(
            uow_factory(),
            proposal_id=proposal_id,
            verdict="approved",
            reviewer="ba2slk",
        )

    with session_factory() as session:
        claim = session.get(ClaimRow, claim_id)
        revision_count = session.scalar(
            text(
                "SELECT count(*) FROM knowledge_artifact_revisions r "
                "JOIN knowledge_artifact_change_proposals p "
                "ON p.id = r.source_proposal_id WHERE p.id = :pid"
            ),
            {"pid": str(proposal_id)},
        )
        proposal_status = session.scalar(
            text(
                "SELECT status FROM knowledge_artifact_change_proposals "
                "WHERE id = :pid"
            ),
            {"pid": str(proposal_id)},
        )
    assert claim is not None
    assert claim.resolution_status == "pending"
    assert revision_count == 0
    assert proposal_status == "pending"


def test_blank_reviewer_is_refused_at_repository(
    workspace_id: int,
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """공백 reviewer는 저장소가 결정 기록 전에 거부한다."""
    with uow_factory() as uow:
        with pytest.raises(ValueError):
            uow.mutation_proposals.mark_merge_approved(
                workspace_id=workspace_id,
                proposal_id=uuid.uuid4(),
                reviewer="",
            )
