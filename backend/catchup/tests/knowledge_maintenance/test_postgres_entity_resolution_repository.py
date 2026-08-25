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
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker

from catchup.configs.config import settings
from catchup.db.models import KnowledgeClaimCandidate as ClaimRow
from catchup.db.models import KnowledgeEntityCandidate as EntityCandidateRow
from catchup.db.models import KnowledgeMutationOperation as OperationRow
from catchup.db.models import KnowledgeMutationProposal as ProposalRow
from catchup.db.models import KnowledgeNode as NodeRow
from catchup.db.models import KnowledgeNodeAlias as AliasRow
from catchup.db.models import Workspace
from catchup.knowledge_maintenance.adapters.postgres.repositories import (
    SqlAlchemyKnowledgeNodeRepository,
)
from catchup.knowledge_maintenance.adapters.postgres.unit_of_work import (
    KnowledgeMaintenanceUnitOfWork,
)
from catchup.knowledge_maintenance.contracts.extraction import ClaimCandidateDraft
from catchup.knowledge_maintenance.contracts.extraction import EntityCandidateDraft
from catchup.knowledge_maintenance.contracts.extraction import KnowledgeCandidateBatch
from catchup.knowledge_maintenance.domain.entity_resolution import normalize_name
from catchup.knowledge_maintenance.domain.knowledge_candidate import (
    EntityResolutionStatus,
)
from catchup.knowledge_maintenance.domain.knowledge_node import NodeLifecycleState
from catchup.knowledge_maintenance.ports.mutation_proposals import (
    MergeProposalAlreadyDecided,
)
from catchup.knowledge_maintenance.services.query_knowledge_as_of import (
    query_claims_as_of,
)
from catchup.knowledge_maintenance.services.resolve_entity_candidates import (
    resolve_entity_candidates,
)
from catchup.knowledge_maintenance.services.store_knowledge_candidates import (
    store_knowledge_candidates,
)
from catchup.tests.knowledge_maintenance.test_postgres_knowledge_candidate_repository import (  # noqa: E501
    SOURCE_TYPE,
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

    if not inspect(engine).has_table(ProposalRow.__tablename__):
        engine.dispose()
        pytest.skip("resolution 테이블이 없다. alembic upgrade head가 필요하다.")

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
) -> Callable[[], KnowledgeMaintenanceUnitOfWork]:
    return lambda: KnowledgeMaintenanceUnitOfWork(session_factory)


def _stored_candidates(workspace_id, session_factory, uow_factory):
    """후보 한 벌을 실제로 저장하고 배치를 돌려준다."""
    observation = _stored_observation(workspace_id, session_factory)
    return store_knowledge_candidates(
        observation,
        _batch(),
        spec=SPEC,
        uow=uow_factory(),
    ).batch


def test_find_pending_returns_source_type_and_payload(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """pending 후보가 source_type과 raw_payload를 갖고 조회된다."""
    stored = _stored_candidates(workspace_id, session_factory, uow_factory)

    with uow_factory() as uow:
        pending = uow.knowledge_candidates.find_pending_entity_candidates(
            workspace_id=workspace_id,
        )

    ids = {candidate.id for candidate in pending}
    assert set(stored.entity_ids.values()) <= ids
    sample = next(c for c in pending if c.id == stored.entity_ids["m1"])
    assert sample.source_type == SOURCE_TYPE
    assert sample.raw_payload["attributes"]["external_key"] == "user-abc"
    assert sample.extraction_method.value == "deterministic"
    assert sample.observation_excerpt is not None
    assert sample.observation_excerpt.startswith("고객:")


def test_mark_entity_resolved_excludes_from_pending(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """해소된 후보는 pending 조회에서 빠진다."""
    stored = _stored_candidates(workspace_id, session_factory, uow_factory)
    target = stored.entity_ids["m1"]

    with uow_factory() as uow:
        node = uow.knowledge_nodes.create_entity_node(
            workspace_id=workspace_id,
            entity_type="channel_talk_user",
            canonical_key=f"{SOURCE_TYPE}:channel_talk_user:user-abc",
            display_name="사용자 008",
        )
        uow.knowledge_candidates.mark_entity_resolved(
            candidate_id=target,
            status=EntityResolutionStatus.ACCEPTED,
            resolved_node_id=node.id,
        )
        uow.commit()

    with uow_factory() as uow:
        pending_ids = {
            c.id
            for c in uow.knowledge_candidates.find_pending_entity_candidates(
                workspace_id=workspace_id,
            )
        }
    assert target not in pending_ids


def test_count_entities_resolved_to_filters_by_name_and_exclusion(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """노드를 가리키는 후보 수를 이름과 제외 목록으로 좁혀 센다.

    되돌림이 별칭을 지우기 전에 "이 이름으로 이 노드에 아직 붙어 있는
    다른 후보가 있는가"를 이 조회로 묻는다.
    """
    stored = _stored_candidates(workspace_id, session_factory, uow_factory)
    payment = stored.entity_ids["e1"]
    auth = stored.entity_ids["e2"]

    with uow_factory() as uow:
        node = uow.knowledge_nodes.create_entity_node(
            workspace_id=workspace_id,
            entity_type="feature",
            canonical_key=None,
            display_name="결제 기능",
        )
        for candidate_id in (payment, auth):
            uow.knowledge_candidates.mark_entity_resolved(
                candidate_id=candidate_id,
                status=EntityResolutionStatus.MERGED,
                resolved_node_id=node.id,
            )
        uow.commit()

    with uow_factory() as uow:
        count = uow.knowledge_candidates.count_entities_resolved_to
        assert count(workspace_id=workspace_id, node_id=node.id) == 2
        assert (
            count(
                workspace_id=workspace_id,
                node_id=node.id,
                normalized_name=normalize_name("결제 기능"),
            )
            == 1
        )
        # 이름이 같아도 제외 목록에 든 후보는 남은 참조로 세지 않는다.
        assert (
            count(
                workspace_id=workspace_id,
                node_id=node.id,
                normalized_name=normalize_name("결제 기능"),
                exclude_candidate_ids=(payment,),
            )
            == 0
        )
        assert (
            count(
                workspace_id=workspace_id,
                node_id=node.id,
                exclude_candidate_ids=(payment, auth),
            )
            == 0
        )


def test_list_entity_candidate_ids_resolved_to_returns_sorted_ids(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """노드를 가리키는 후보 id를 오름차순으로 돌려준다.

    다른 노드에 붙은 후보는 빠진다. 적용은 이 값을 event에 적고, 되돌림은
    같은 값을 다시 읽어 견준다.
    """
    stored = _stored_candidates(workspace_id, session_factory, uow_factory)
    payment = stored.entity_ids["e1"]
    auth = stored.entity_ids["e2"]
    elsewhere = stored.entity_ids["m1"]

    with uow_factory() as uow:
        node = uow.knowledge_nodes.create_entity_node(
            workspace_id=workspace_id,
            entity_type="feature",
            canonical_key=None,
            display_name="결제 기능",
        )
        other = uow.knowledge_nodes.create_entity_node(
            workspace_id=workspace_id,
            entity_type="feature",
            canonical_key=None,
            display_name="다른 기능",
        )
        for candidate_id, target in (
            (payment, node.id),
            (auth, node.id),
            (elsewhere, other.id),
        ):
            uow.knowledge_candidates.mark_entity_resolved(
                candidate_id=candidate_id,
                status=EntityResolutionStatus.MERGED,
                resolved_node_id=target,
            )
        uow.commit()

    with uow_factory() as uow:
        found = uow.knowledge_candidates.list_entity_candidate_ids_resolved_to(
            workspace_id=workspace_id,
            node_id=node.id,
        )
    assert found == tuple(sorted((payment, auth)))


def test_lock_entity_node_returns_node_or_none(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """잠근 노드를 도메인 값으로 돌려주고, 없는 노드에는 None을 준다."""
    with uow_factory() as uow:
        node = uow.knowledge_nodes.create_entity_node(
            workspace_id=workspace_id,
            entity_type="feature",
            canonical_key=None,
            display_name="결제 기능",
        )
        uow.commit()

    with uow_factory() as uow:
        locked = uow.knowledge_nodes.lock_entity_node(
            workspace_id=workspace_id,
            node_id=node.id,
        )
        missing = uow.knowledge_nodes.lock_entity_node(
            workspace_id=workspace_id,
            node_id=uuid.uuid4(),
        )
    assert locked is not None
    assert locked.id == node.id
    assert locked.lifecycle_state is NodeLifecycleState.ACTIVE
    assert missing is None


def test_entity_node_roundtrip_by_canonical_key(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """canonical key로 만든 entity 노드를 같은 key로 되찾는다."""
    key = f"{SOURCE_TYPE}:channel_talk_manager:manager-xyz"
    with uow_factory() as uow:
        created = uow.knowledge_nodes.create_entity_node(
            workspace_id=workspace_id,
            entity_type="channel_talk_manager",
            canonical_key=key,
            display_name="캐치업 팀",
        )
        uow.commit()

    with uow_factory() as uow:
        found = uow.knowledge_nodes.get_entity_by_canonical_key(
            workspace_id=workspace_id,
            canonical_key=key,
        )
    assert found is not None
    assert found.id == created.id
    assert found.entity_type == "channel_talk_manager"


def test_add_alias_ignores_duplicates(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """같은 정규화 alias를 다시 넣어도 조용히 넘어간다.

    두 번째 호출은 거짓을 준다. 부르는 쪽이 "이 이름은 내가 붙였다"를
    저널에 적을지 이 값으로 가른다.
    """
    with uow_factory() as uow:
        node = uow.knowledge_nodes.create_entity_node(
            workspace_id=workspace_id,
            entity_type="channel_talk_manager",
            canonical_key=f"{SOURCE_TYPE}:channel_talk_manager:m-1",
            display_name="캐치업 팀",
        )
        first = uow.knowledge_nodes.add_alias(
            workspace_id=workspace_id,
            node_id=node.id,
            alias="캐치업 팀",
            normalized_alias="캐치업 팀",
            source="source",
        )
        second = uow.knowledge_nodes.add_alias(
            workspace_id=workspace_id,
            node_id=node.id,
            alias="캐치업 팀",
            normalized_alias="캐치업 팀",
            source="source",
        )
        uow.commit()

    assert first is True
    assert second is False

    with session_factory() as session:
        count = len(
            session.scalars(
                select(AliasRow).where(AliasRow.node_id == node.id)
            ).all()
        )
    assert count == 1


def test_remove_alias_only_removes_confirmation_source(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """되돌림의 alias 제거는 확정이 남긴 행만 지운다.

    같은 노드는 정규화 alias 하나당 행 하나라(uq_knowledge_node_aliases_
    normalized), 추출기가 먼저 붙여 둔 이름에는 병합이 add_alias를 불러도
    행이 늘지 않는다. 그 행까지 지우면 병합이 만들지도 않은 단서가
    되돌림에 딸려 사라진다. 다른 노드에 붙은 같은 표기도 건드리면 안
    된다.
    """
    with uow_factory() as uow:
        node = uow.knowledge_nodes.create_entity_node(
            workspace_id=workspace_id,
            entity_type="feature",
            canonical_key=None,
            display_name="결제 기능",
        )
        other = uow.knowledge_nodes.create_entity_node(
            workspace_id=workspace_id,
            entity_type="feature",
            canonical_key=None,
            display_name="결제 기능",
        )
        # 추출기가 먼저 붙인 이름이다. 병합이 남긴 것이 아니다.
        uow.knowledge_nodes.add_alias(
            workspace_id=workspace_id,
            node_id=node.id,
            alias="결제 기능",
            normalized_alias="결제 기능",
            source="extractor",
        )
        # 병합이 남긴 이름이다.
        uow.knowledge_nodes.add_alias(
            workspace_id=workspace_id,
            node_id=node.id,
            alias="페이먼트",
            normalized_alias="페이먼트",
            source="system",
        )
        # 같은 표기가 다른 노드에도 확정으로 붙어 있다.
        uow.knowledge_nodes.add_alias(
            workspace_id=workspace_id,
            node_id=other.id,
            alias="페이먼트",
            normalized_alias="페이먼트",
            source="system",
        )
        uow.commit()

    with uow_factory() as uow:
        uow.knowledge_nodes.remove_alias(
            workspace_id=workspace_id,
            node_id=node.id,
            normalized_alias="결제 기능",
        )
        uow.knowledge_nodes.remove_alias(
            workspace_id=workspace_id,
            node_id=node.id,
            normalized_alias="페이먼트",
        )
        # 없는 이름을 지우라고 해도 조용히 넘어간다.
        uow.knowledge_nodes.remove_alias(
            workspace_id=workspace_id,
            node_id=node.id,
            normalized_alias="없는 이름",
        )
        uow.commit()

    with session_factory() as session:
        remaining = session.scalars(
            select(AliasRow).where(AliasRow.node_id == node.id)
        ).all()
        untouched = session.scalars(
            select(AliasRow).where(AliasRow.node_id == other.id)
        ).all()
    assert [(row.normalized_alias, row.source) for row in remaining] == [
        ("결제 기능", "extractor")
    ]
    assert [(row.normalized_alias, row.source) for row in untouched] == [
        ("페이먼트", "system")
    ]


def test_retire_entity_node_clears_merge_target(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """퇴역은 lifecycle을 retired로 바꾸고 흡수처를 비운 채 commit된다.

    ck_knowledge_nodes_merged_target이 merged가 아닌 행에 흡수처가 남아
    있는 것을 막으므로, 흡수된 노드를 물릴 때 merged_into_node_id를 함께
    비우지 않으면 flush에서 막힌다.
    """
    with uow_factory() as uow:
        absorbed = uow.knowledge_nodes.create_entity_node(
            workspace_id=workspace_id,
            entity_type="feature",
            canonical_key=None,
            display_name="결제",
        )
        target = uow.knowledge_nodes.create_entity_node(
            workspace_id=workspace_id,
            entity_type="feature",
            canonical_key=None,
            display_name="결제 기능",
        )
        uow.commit()

    with session_factory() as session:
        row = session.get(NodeRow, absorbed.id)
        assert row is not None
        row.lifecycle_state = "merged"
        row.merged_into_node_id = target.id
        session.commit()

    with uow_factory() as uow:
        retired = uow.knowledge_nodes.retire_entity_node(
            workspace_id=workspace_id,
            node_id=absorbed.id,
        )
        uow.commit()
    assert retired is True

    with session_factory() as session:
        row = session.get(NodeRow, absorbed.id)
        assert row is not None
        assert row.lifecycle_state == "retired"
        assert row.merged_into_node_id is None

    with uow_factory() as uow:
        found = uow.knowledge_nodes.get_entity_by_id(
            workspace_id=workspace_id,
            node_id=absorbed.id,
        )
    assert found is not None
    assert found.lifecycle_state is NodeLifecycleState.RETIRED


def test_retire_entity_node_keeps_a_node_a_candidate_still_points_to(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """가리키는 후보가 남아 있는 노드는 물리지 않고 거짓을 돌려준다.

    남은 후보 확인은 저장소가 노드 행을 잠근 채로 한다. 부르는 쪽이 먼저
    세어 보고 그 뒤에 물리면 그 사이에 붙은 후보가 퇴역한 노드를 가리키게
    된다.
    """
    stored = _stored_candidates(workspace_id, session_factory, uow_factory)

    with uow_factory() as uow:
        node = uow.knowledge_nodes.create_entity_node(
            workspace_id=workspace_id,
            entity_type="feature",
            canonical_key=None,
            display_name="결제 기능",
        )
        uow.knowledge_candidates.mark_entity_resolved(
            candidate_id=stored.entity_ids["e1"],
            status=EntityResolutionStatus.MERGED,
            resolved_node_id=node.id,
        )
        uow.commit()

    with uow_factory() as uow:
        retired = uow.knowledge_nodes.retire_entity_node(
            workspace_id=workspace_id,
            node_id=node.id,
        )
        uow.commit()
    assert retired is False

    with uow_factory() as uow:
        found = uow.knowledge_nodes.get_entity_by_id(
            workspace_id=workspace_id,
            node_id=node.id,
        )
    assert found is not None
    assert found.lifecycle_state is NodeLifecycleState.ACTIVE


def test_mark_entity_resolved_rejects_a_retired_node(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """퇴역한 노드에는 후보를 붙이지 않는다.

    붙이면 그 후보와 그 후보로 읽히는 지식이 살아 있는 graph에서 사라진다.
    """
    stored = _stored_candidates(workspace_id, session_factory, uow_factory)

    with uow_factory() as uow:
        node = uow.knowledge_nodes.create_entity_node(
            workspace_id=workspace_id,
            entity_type="feature",
            canonical_key=None,
            display_name="결제 기능",
        )
        assert uow.knowledge_nodes.retire_entity_node(
            workspace_id=workspace_id,
            node_id=node.id,
        )
        uow.commit()

    with uow_factory() as uow:
        with pytest.raises(ValueError):
            uow.knowledge_candidates.mark_entity_resolved(
                candidate_id=stored.entity_ids["e1"],
                status=EntityResolutionStatus.MERGED,
                resolved_node_id=node.id,
            )


def test_mark_entity_resolved_rejects_an_unknown_node(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """없는 노드로 해소했다고 적을 수 없다."""
    stored = _stored_candidates(workspace_id, session_factory, uow_factory)

    with uow_factory() as uow:
        with pytest.raises(ValueError):
            uow.knowledge_candidates.mark_entity_resolved(
                candidate_id=stored.entity_ids["e1"],
                status=EntityResolutionStatus.MERGED,
                resolved_node_id=uuid.uuid4(),
            )


def test_retire_unknown_entity_node_is_rejected(
    workspace_id: int,
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """없는 노드를 물리라는 요청은 거부한다."""
    with uow_factory() as uow:
        with pytest.raises(ValueError):
            uow.knowledge_nodes.retire_entity_node(
                workspace_id=workspace_id,
                node_id=uuid.uuid4(),
            )


def test_duplicate_proposal_roundtrip_and_abandon(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """병합 proposal이 operation과 함께 저장되고 abandon으로 접힌다."""
    stored = _stored_candidates(workspace_id, session_factory, uow_factory)
    representative = stored.entity_ids["e1"]
    other = stored.entity_ids["e2"]

    with uow_factory() as uow:
        proposal_id = uow.mutation_proposals.add_duplicate_proposal(
            workspace_id=workspace_id,
            idempotency_key="결제 기능",
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

    with uow_factory() as uow:
        found = uow.mutation_proposals.find_pending_by_idempotency_key(
            workspace_id=workspace_id,
            idempotency_key="결제 기능",
        )
    assert found is not None
    assert found.id == proposal_id
    assert found.resolver_metadata["member_hash"] == "abc"

    with session_factory() as session:
        operations = session.scalars(
            select(OperationRow)
            .where(OperationRow.proposal_id == proposal_id)
            .order_by(OperationRow.sequence)
        ).all()
    assert [op.operation_type for op in operations] == [
        "create_entity",
        "merge_entity",
    ]
    assert operations[0].operation_data["proposed_type"] == "feature"
    assert operations[1].operation_data["merge_into_sequence"] == 1

    with uow_factory() as uow:
        uow.mutation_proposals.abandon(proposal_id=proposal_id)
        uow.commit()

    with uow_factory() as uow:
        assert (
            uow.mutation_proposals.find_pending_by_idempotency_key(
                workspace_id=workspace_id,
                idempotency_key="결제 기능",
            )
            is None
        )


def test_replacing_proposal_reuses_key_row(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """같은 key로 다시 쓰면 UNIQUE 충돌 없이 행이 교체된다.

    abandoned 행이 key를 계속 차지하므로, 새 INSERT가 아니라 기존 행을
    되살려 내용과 operation을 갈아끼워야 한다.
    """
    stored = _stored_candidates(workspace_id, session_factory, uow_factory)
    representative = stored.entity_ids["e1"]
    other = stored.entity_ids["e2"]

    with uow_factory() as uow:
        first_id = uow.mutation_proposals.add_duplicate_proposal(
            workspace_id=workspace_id,
            idempotency_key="group-key",
            trigger_entity_candidate_id=representative,
            detector="catchup.name_group_judge",
            detector_version="1",
            summary="첫 계획",
            resolver_metadata={"member_hash": "old"},
            representative_candidate_id=representative,
            merge_candidate_ids=(other,),
            proposed_type="feature",
            proposed_name="결제 기능",
        )
        uow.mutation_proposals.abandon(proposal_id=first_id)
        uow.commit()

    with uow_factory() as uow:
        second_id = uow.mutation_proposals.add_duplicate_proposal(
            workspace_id=workspace_id,
            idempotency_key="group-key",
            trigger_entity_candidate_id=other,
            detector="catchup.name_group_judge",
            detector_version="1",
            summary="멤버가 달라진 새 계획",
            resolver_metadata={"member_hash": "new"},
            representative_candidate_id=other,
            merge_candidate_ids=(representative,),
            proposed_type="feature",
            proposed_name="결제 기능",
        )
        uow.commit()

    with uow_factory() as uow:
        found = uow.mutation_proposals.find_pending_by_idempotency_key(
            workspace_id=workspace_id,
            idempotency_key="group-key",
        )
    assert found is not None
    assert found.id == second_id
    assert found.resolver_metadata["member_hash"] == "new"

    with session_factory() as session:
        operations = session.scalars(
            select(OperationRow)
            .where(OperationRow.proposal_id == second_id)
            .order_by(OperationRow.sequence)
        ).all()
    assert operations[0].entity_candidate_id == other
    assert operations[1].entity_candidate_id == representative


def test_mark_stale_moves_only_an_approved_proposal(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """approved 안건만 stale이 되고 결정 저널은 그대로 남는다.

    승인 뒤 세계가 바뀌어 실행할 수 없게 된 안건을 끝맺는 자리다. 사람이
    승인했다는 사실을 지우면 안 되므로 reviewer와 reviewed_at은 건드리지
    않는다. 이미 끝난 안건을 다시 끝맺으려 하면 거부한다.
    """
    stored = _stored_candidates(workspace_id, session_factory, uow_factory)
    representative = stored.entity_ids["e1"]
    other = stored.entity_ids["e2"]

    with uow_factory() as uow:
        proposal_id = uow.mutation_proposals.add_duplicate_proposal(
            workspace_id=workspace_id,
            idempotency_key=f"stale-{uuid.uuid4().hex[:8]}",
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
        uow.mutation_proposals.mark_merge_approved(
            workspace_id=workspace_id,
            proposal_id=proposal_id,
            reviewer="tester",
        )
        uow.commit()

    with uow_factory() as uow:
        uow.mutation_proposals.mark_stale(
            workspace_id=workspace_id,
            proposal_id=proposal_id,
        )
        uow.commit()

    with session_factory() as session:
        row = session.get(ProposalRow, proposal_id)
        assert row is not None
        assert row.status == "stale"
        assert row.reviewer == "tester"
        assert row.reviewed_at is not None

    with uow_factory() as uow:
        with pytest.raises(MergeProposalAlreadyDecided):
            uow.mutation_proposals.mark_stale(
                workspace_id=workspace_id,
                proposal_id=proposal_id,
            )


class _UnusedJudge:
    """단일 그룹만 있는 실행에서 판정이 불리지 않음을 강제한다."""

    def judge(self, group):
        raise AssertionError(f"단일 후보에 판정이 불렸다: {group}")


def _singleton_batch(name: str) -> KnowledgeCandidateBatch:
    """이름이 하나뿐인 entity와 그 entity에 대한 claim을 만든다."""
    return KnowledgeCandidateBatch(
        entities=[
            EntityCandidateDraft(
                local_key="e1",
                proposed_type="feature",
                proposed_name=name,
            )
        ],
        claims=[
            ClaimCandidateDraft(
                local_key="c1",
                subject_local_key="e1",
                predicate="release_month",
                value_type="text",
                value="2026-09",
                statement="9월 예정입니다.",
            )
        ],
        relation_assertions=[],
    )


def test_promoted_singleton_carries_claims_into_read_path(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """승격된 entity의 claim이 노드에 매달려 이름으로 조회된다.

    승격의 값어치는 노드 행이 생기는 데 있지 않고, 그 노드를 통해
    claim이 읽기 경로에 드러나는 데 있다. claim은 여전히 후보 행을
    subject로 가리키므로 `resolved_node_id`가 그 사슬의 유일한 연결
    고리다. 조회 이름이 canonical_key가 아니라 alias로만 걸린다는 것도
    여기서 함께 확인한다 — 승격 노드에는 key가 없다.
    """
    name = f"결제 기능 {uuid.uuid4().hex[:8]}"
    observation = _stored_observation(workspace_id, session_factory)
    stored = store_knowledge_candidates(
        observation,
        _singleton_batch(name),
        spec=SPEC,
        uow=uow_factory(),
    ).batch
    candidate_id = stored.entity_ids["e1"]
    claim_id = stored.claim_ids["c1"]

    result = resolve_entity_candidates(
        workspace_id=workspace_id,
        judge=_UnusedJudge(),
        uow=uow_factory(),
    )

    assert result.singletons_promoted >= 1
    with session_factory() as session:
        candidate = session.get(EntityCandidateRow, candidate_id)
        assert candidate is not None
        assert candidate.resolution_status == "accepted"
        node_id = candidate.resolved_node_id
        assert node_id is not None
        # 승격 노드는 canonical_key 없이 alias로만 불린다.
        node = session.get(NodeRow, node_id)
        assert node is not None
        assert node.canonical_key is None
        aliases = session.scalars(
            select(AliasRow).where(AliasRow.node_id == node_id)
        ).all()
        assert [(alias.alias, alias.source) for alias in aliases] == [
            (name, "extractor")
        ]
        # 읽기 경로는 accepted claim만 본다. claim 승인은 다른 단계의
        # 일이라 여기서는 결과 상태만 만들어 둔다.
        claim = session.get(ClaimRow, claim_id)
        assert claim is not None
        claim.resolution_status = "accepted"
        session.commit()

    with uow_factory() as uow:
        claims = uow.knowledge_candidates.find_claim_candidates(
            workspace_id=workspace_id,
        )
    found = next(claim for claim in claims if claim.id == claim_id)
    assert found.subject_resolved_node_id == node_id

    as_of = query_claims_as_of(
        workspace_id=workspace_id,
        subject=name,
        at=datetime(2026, 8, 5, tzinfo=timezone.utc),
        uow=uow_factory(),
    )

    assert as_of.subject is not None
    assert as_of.subject.node_id == node_id
    assert [claim.claim_id for claim in as_of.claims] == [claim_id]
    assert as_of.claims[0].value == "2026-09"


def test_actor_key_lookup_and_attribute_update(
    workspace_id: int,
    session_factory: Callable[[], Session],
) -> None:
    """행위자 노드는 attributes에 쌓인 키로 다시 찾힌다."""
    actor = {
        "actor": {
            "emails": ["neo@x.com"],
            "external_keys": ["ext-1"],
            "unified_ids": [],
            "source_entity_type": "channel_talk_user",
        }
    }
    with session_factory() as session:
        repo = SqlAlchemyKnowledgeNodeRepository(session)
        node = repo.create_entity_node(
            workspace_id=workspace_id,
            entity_type="customer",
            canonical_key=f"channel_talk:customer:email:{uuid.uuid4()}@x.com",
            display_name="팀원A",
            attributes=actor,
        )

        by_email = repo.find_entity_by_actor_key(
            workspace_id=workspace_id,
            entity_type="customer",
            key_kind="emails",
            value="neo@x.com",
        )
        assert by_email is not None and by_email.id == node.id

        by_key = repo.find_entity_by_actor_key(
            workspace_id=workspace_id,
            entity_type="customer",
            key_kind="external_keys",
            value="ext-1",
        )
        assert by_key is not None and by_key.id == node.id

        assert (
            repo.find_entity_by_actor_key(
                workspace_id=workspace_id,
                entity_type="customer",
                key_kind="external_keys",
                value="ext-9",
            )
            is None
        )

        grown = dict(actor["actor"]) | {"external_keys": ["ext-1", "ext-2"]}
        updated = repo.set_entity_attributes(
            workspace_id=workspace_id,
            node_id=node.id,
            attributes={"actor": grown},
        )
        assert updated.attributes["actor"]["external_keys"] == [
            "ext-1",
            "ext-2",
        ]

        rebound = repo.find_entity_by_actor_key(
            workspace_id=workspace_id,
            entity_type="customer",
            key_kind="external_keys",
            value="ext-2",
        )
        assert rebound is not None and rebound.id == node.id

        # 같은 키라도 다른 workspace에서는 보이지 않아야 한다. 행위자
        # 키는 workspace마다 다른 사람을 가리킬 수 있다.
        assert (
            repo.find_entity_by_actor_key(
                workspace_id=workspace_id + 100_000,
                entity_type="customer",
                key_kind="emails",
                value="neo@x.com",
            )
            is None
        )
