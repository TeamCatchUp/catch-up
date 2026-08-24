"""해소 event 저널 어댑터를 실 PostgreSQL로 확인한다.

저널이 지켜야 할 것 가운데 여러 개가 DB 제약에 들어 있다. 되돌림 행에
원본이 반드시 있어야 한다는 CHECK가 그렇고, JSONB 왕복도 가짜 저장소로는
컬럼 종류가 틀려도 드러나지 않는다. 그래서 실 DB로 본다.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import Engine
from sqlalchemy import create_engine
from sqlalchemy import delete
from sqlalchemy import inspect
from sqlalchemy import select
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker

from catchup.configs.config import settings
from catchup.db.models import KnowledgeResolutionEvent
from catchup.db.models import Workspace
from catchup.knowledge_maintenance.adapters.postgres.resolution_events import (
    SqlAlchemyResolutionEventRepository,
)

MEMBER_HASH = "test-resolution-event-member-hash"
OTHER_MEMBER_HASH = "test-resolution-event-member-hash-other"
TEST_MEMBER_HASHES = (MEMBER_HASH, OTHER_MEMBER_HASH)


@pytest.fixture(scope="module")
def engine() -> Iterator[Engine]:
    engine = create_engine(settings.sqlalchemy_database_url)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except OperationalError:
        engine.dispose()
        pytest.skip("PostgreSQL이 없어 통합 테스트를 건너뛴다.")

    if not inspect(engine).has_table(KnowledgeResolutionEvent.__tablename__):
        engine.dispose()
        pytest.skip("해소 event 표가 없다. alembic upgrade head가 필요하다.")

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
def session(engine: Engine, workspace_id: int) -> Iterator[Session]:
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    session = session_factory()
    try:
        yield session
    finally:
        session.rollback()
        session.close()

    with session_factory() as cleanup:
        # 되돌림 행이 원본을 외래 키로 가리키므로 되돌림 행부터 지운다.
        for only_reversals in (True, False):
            statement = delete(KnowledgeResolutionEvent).where(
                KnowledgeResolutionEvent.workspace_id == workspace_id,
                KnowledgeResolutionEvent.member_hash.in_(TEST_MEMBER_HASHES),
            )
            if only_reversals:
                statement = statement.where(
                    KnowledgeResolutionEvent.reverses_event_id.is_not(None)
                )
            cleanup.execute(statement)
        cleanup.commit()


@pytest.fixture
def repository(session: Session) -> SqlAlchemyResolutionEventRepository:
    return SqlAlchemyResolutionEventRepository(session)


def test_recorded_event_comes_back(
    repository: SqlAlchemyResolutionEventRepository,
    session: Session,
    workspace_id: int,
) -> None:
    """적어 둔 event를 식별자로 그대로 읽어온다."""
    event_id = uuid.uuid4()
    node_id = uuid.uuid4()

    repository.record(
        workspace_id=workspace_id,
        event_id=event_id,
        event_type="merge_create_node",
        decider="system",
        decider_id=None,
        node_id=node_id,
        member_hash=MEMBER_HASH,
        member_snapshot={"members": ["a", "b"]},
        basis={"similarity": 0.94},
    )
    session.commit()

    found = repository.get(workspace_id=workspace_id, event_id=event_id)

    assert found is not None
    assert found.id == event_id
    assert found.workspace_id == workspace_id
    assert found.event_type == "merge_create_node"
    assert found.decider == "system"
    assert found.decider_id is None
    assert found.node_id == node_id
    assert found.member_hash == MEMBER_HASH
    assert found.member_snapshot == {"members": ["a", "b"]}
    assert found.basis == {"similarity": 0.94}
    assert found.reverses_event_id is None
    assert found.created_at is not None


def test_missing_event_reads_as_none(
    repository: SqlAlchemyResolutionEventRepository, workspace_id: int
) -> None:
    """적힌 적 없는 식별자는 None으로 읽힌다."""
    assert (
        repository.get(workspace_id=workspace_id, event_id=uuid.uuid4()) is None
    )


def test_other_workspace_does_not_see_the_event(
    repository: SqlAlchemyResolutionEventRepository,
    session: Session,
    workspace_id: int,
) -> None:
    """다른 workspace로 물으면 같은 식별자여도 읽히지 않는다."""
    event_id = uuid.uuid4()
    repository.record(
        workspace_id=workspace_id,
        event_id=event_id,
        event_type="merge_into_node",
        decider="system",
        decider_id=None,
        node_id=uuid.uuid4(),
        member_hash=MEMBER_HASH,
        member_snapshot={},
        basis={},
    )
    session.commit()

    assert (
        repository.get(workspace_id=workspace_id + 10_000, event_id=event_id)
        is None
    )


def test_reversal_is_found_by_the_event_it_reverses(
    repository: SqlAlchemyResolutionEventRepository,
    session: Session,
    workspace_id: int,
) -> None:
    """되돌림 행은 원본 식별자로 찾힌다."""
    merge_id = uuid.uuid4()
    unmerge_id = uuid.uuid4()
    node_id = uuid.uuid4()

    repository.record(
        workspace_id=workspace_id,
        event_id=merge_id,
        event_type="merge_create_node",
        decider="system",
        decider_id=None,
        node_id=node_id,
        member_hash=MEMBER_HASH,
        member_snapshot={},
        basis={},
    )
    repository.record(
        workspace_id=workspace_id,
        event_id=unmerge_id,
        event_type="unmerge",
        decider="human",
        decider_id="reviewer-1",
        node_id=node_id,
        member_hash=MEMBER_HASH,
        member_snapshot={},
        basis={"reason": "다른 사람이다"},
        reverses_event_id=merge_id,
    )
    session.commit()

    found = repository.find_reversal(
        workspace_id=workspace_id, event_id=merge_id
    )

    assert found is not None
    assert found.id == unmerge_id
    assert found.reverses_event_id == merge_id
    assert found.decider_id == "reviewer-1"


def test_event_without_a_reversal_reads_as_none(
    repository: SqlAlchemyResolutionEventRepository,
    session: Session,
    workspace_id: int,
) -> None:
    """되돌려지지 않은 event를 물으면 None이다."""
    merge_id = uuid.uuid4()
    repository.record(
        workspace_id=workspace_id,
        event_id=merge_id,
        event_type="merge_create_node",
        decider="system",
        decider_id=None,
        node_id=uuid.uuid4(),
        member_hash=MEMBER_HASH,
        member_snapshot={},
        basis={},
    )
    session.commit()

    assert (
        repository.find_reversal(workspace_id=workspace_id, event_id=merge_id)
        is None
    )


def test_human_unmerge_is_seen_for_the_same_members(
    repository: SqlAlchemyResolutionEventRepository,
    session: Session,
    workspace_id: int,
) -> None:
    """사람이 되돌린 구성은 참으로 읽힌다."""
    merge_id = uuid.uuid4()
    node_id = uuid.uuid4()
    repository.record(
        workspace_id=workspace_id,
        event_id=merge_id,
        event_type="merge_create_node",
        decider="system",
        decider_id=None,
        node_id=node_id,
        member_hash=MEMBER_HASH,
        member_snapshot={},
        basis={},
    )
    repository.record(
        workspace_id=workspace_id,
        event_id=uuid.uuid4(),
        event_type="unmerge",
        decider="human",
        decider_id="reviewer-1",
        node_id=node_id,
        member_hash=MEMBER_HASH,
        member_snapshot={},
        basis={},
        reverses_event_id=merge_id,
    )
    session.commit()

    assert repository.has_human_unmerge(
        workspace_id=workspace_id, member_hash=MEMBER_HASH
    )
    assert not repository.has_human_unmerge(
        workspace_id=workspace_id, member_hash=OTHER_MEMBER_HASH
    )


def test_system_unmerge_is_not_a_human_unmerge(
    repository: SqlAlchemyResolutionEventRepository,
    session: Session,
    workspace_id: int,
) -> None:
    """시스템이 되돌린 구성은 사람의 되돌림으로 세지 않는다."""
    merge_id = uuid.uuid4()
    node_id = uuid.uuid4()
    repository.record(
        workspace_id=workspace_id,
        event_id=merge_id,
        event_type="merge_create_node",
        decider="system",
        decider_id=None,
        node_id=node_id,
        member_hash=MEMBER_HASH,
        member_snapshot={},
        basis={},
    )
    repository.record(
        workspace_id=workspace_id,
        event_id=uuid.uuid4(),
        event_type="unmerge",
        decider="system",
        decider_id=None,
        node_id=node_id,
        member_hash=MEMBER_HASH,
        member_snapshot={},
        basis={},
        reverses_event_id=merge_id,
    )
    session.commit()

    assert not repository.has_human_unmerge(
        workspace_id=workspace_id, member_hash=MEMBER_HASH
    )


def test_second_reversal_of_the_same_event_is_rejected(
    repository: SqlAlchemyResolutionEventRepository,
    session: Session,
    workspace_id: int,
) -> None:
    """같은 원본을 두 번째로 되돌리는 행은 DB가 막는다.

    되돌림 여부를 미리 읽어 보는 검사만으로는 두 운영자가 동시에 되돌릴 때
    둘 다 통과한다. 원본 하나에 되돌림 행이 하나뿐이라는 것은 DB가 지켜야
    한다.
    """
    merge_id = uuid.uuid4()
    node_id = uuid.uuid4()
    repository.record(
        workspace_id=workspace_id,
        event_id=merge_id,
        event_type="merge_create_node",
        decider="system",
        decider_id=None,
        node_id=node_id,
        member_hash=MEMBER_HASH,
        member_snapshot={},
        basis={},
    )
    repository.record(
        workspace_id=workspace_id,
        event_id=uuid.uuid4(),
        event_type="unmerge",
        decider="human",
        decider_id="reviewer-1",
        node_id=node_id,
        member_hash=MEMBER_HASH,
        member_snapshot={},
        basis={},
        reverses_event_id=merge_id,
    )
    session.commit()

    with pytest.raises(IntegrityError) as raised:
        repository.record(
            workspace_id=workspace_id,
            event_id=uuid.uuid4(),
            event_type="unmerge",
            decider="human",
            decider_id="reviewer-2",
            node_id=node_id,
            member_hash=MEMBER_HASH,
            member_snapshot={},
            basis={},
            reverses_event_id=merge_id,
        )

    assert "uq_knowledge_resolution_events_reversal" in str(raised.value)
    session.rollback()


def test_second_reversal_from_another_transaction_is_rejected(
    engine: Engine,
    repository: SqlAlchemyResolutionEventRepository,
    session: Session,
    workspace_id: int,
) -> None:
    """다른 transaction에서 적는 두 번째 되돌림도 DB가 막는다.

    두 운영자는 저마다 자기 transaction에서 되돌린다. 제약이 연결을 건너
    지켜지지 않으면 한 원본에 되돌림 행이 둘 남는다.
    """
    merge_id = uuid.uuid4()
    node_id = uuid.uuid4()
    repository.record(
        workspace_id=workspace_id,
        event_id=merge_id,
        event_type="merge_create_node",
        decider="system",
        decider_id=None,
        node_id=node_id,
        member_hash=MEMBER_HASH,
        member_snapshot={},
        basis={},
    )
    repository.record(
        workspace_id=workspace_id,
        event_id=uuid.uuid4(),
        event_type="unmerge",
        decider="human",
        decider_id="reviewer-1",
        node_id=node_id,
        member_hash=MEMBER_HASH,
        member_snapshot={},
        basis={},
        reverses_event_id=merge_id,
    )
    session.commit()

    other_factory = sessionmaker(bind=engine, expire_on_commit=False)
    with other_factory() as other:
        other_repository = SqlAlchemyResolutionEventRepository(other)
        with pytest.raises(IntegrityError) as raised:
            other_repository.record(
                workspace_id=workspace_id,
                event_id=uuid.uuid4(),
                event_type="unmerge",
                decider="human",
                decider_id="reviewer-2",
                node_id=node_id,
                member_hash=MEMBER_HASH,
                member_snapshot={},
                basis={},
                reverses_event_id=merge_id,
            )
        assert "uq_knowledge_resolution_events_reversal" in str(raised.value)
        other.rollback()


def test_unmerge_without_an_original_is_rejected(
    repository: SqlAlchemyResolutionEventRepository,
    session: Session,
    workspace_id: int,
) -> None:
    """무엇을 되돌리는지 없는 되돌림 행은 DB가 막는다."""
    with pytest.raises(IntegrityError) as raised:
        repository.record(
            workspace_id=workspace_id,
            event_id=uuid.uuid4(),
            event_type="unmerge",
            decider="human",
            decider_id="reviewer-1",
            node_id=uuid.uuid4(),
            member_hash=MEMBER_HASH,
            member_snapshot={},
            basis={},
        )

    assert "ck_knowledge_resolution_events_unmerge_reversal" in str(
        raised.value
    )
    session.rollback()
