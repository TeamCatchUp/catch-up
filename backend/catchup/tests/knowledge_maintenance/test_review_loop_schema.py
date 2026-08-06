"""검수 루프 API가 딛고 설 스키마 제약을 실 PostgreSQL로 확인한다.

origin 값 집합, 결정 저널 강제, 검토자 권한의 한 벌 유일성은 모두 DB
제약 안에 산다. fake 저장소는 제약을 흉내내는 쪽이라 제약 문구가 틀려도
드러나지 않으므로 실 DB에 직접 넣어 본다.
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
from catchup.db.models import KnowledgeNode as NodeRow
from catchup.db.models import User
from catchup.db.models import WikiReviewerGrant
from catchup.db.models import Workspace
from catchup.tests.knowledge_maintenance.test_artifact_schema import (
    _violated_constraint,
)

ARTIFACT_KIND = "entity_summary"
TABLE = "knowledge_artifact_change_proposals"


@pytest.fixture(scope="module")
def engine() -> Iterator[Engine]:
    engine = create_engine(settings.sqlalchemy_database_url)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except OperationalError:
        engine.dispose()
        pytest.skip("PostgreSQL이 없어 통합 테스트를 건너뛴다.")

    if not inspect(engine).has_table(WikiReviewerGrant.__tablename__):
        engine.dispose()
        pytest.skip("검토자 권한 테이블이 없다. alembic upgrade head가 필요하다.")

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


def _artifact_id(
    session_factory: Callable[[], Session],
    workspace_id: int,
) -> uuid.UUID:
    """새 대상 노드에 붙는 문서 하나를 마련한다."""
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
        session.commit()
    return artifact_id


def _proposal(
    workspace_id: int,
    artifact_id: uuid.UUID,
    **overrides: object,
) -> ProposalRow:
    """필수 컬럼을 채운 변경안 행을 만든다."""
    values: dict[str, object] = {
        "id": uuid.uuid4(),
        "workspace_id": workspace_id,
        "artifact_id": artifact_id,
        "blocks": [],
        "content_hash": uuid.uuid4().hex,
        "idempotency_key": uuid.uuid4().hex,
    }
    values.update(overrides)
    return ProposalRow(**values)


def _user_id(session: Session) -> int:
    """권한을 붙일 사용자 하나를 새로 만든다."""
    user = User(
        email=f"reviewer-{uuid.uuid4().hex}@example.com",
        name="검토자",
        provider="google",
        status="active",
    )
    session.add(user)
    session.flush()
    return user.id


def test_origin_check_rejects_unknown_value(
    workspace_id: int,
    session_factory: Callable[[], Session],
) -> None:
    """origin에 약속되지 않은 값이 들어가면 DB가 막는다."""
    artifact_id = _artifact_id(session_factory, workspace_id)

    with session_factory() as session:
        session.add(_proposal(workspace_id, artifact_id, origin="banana"))
        with pytest.raises(IntegrityError) as excinfo:
            session.commit()

    assert _violated_constraint(excinfo) == f"ck_{TABLE}_origin"


def test_origin_defaults_to_compiled(
    workspace_id: int,
    session_factory: Callable[[], Session],
) -> None:
    """origin을 주지 않으면 compile 기원으로 남는다."""
    artifact_id = _artifact_id(session_factory, workspace_id)
    proposal = _proposal(workspace_id, artifact_id)

    with session_factory() as session:
        session.add(proposal)
        session.commit()
        stored = session.get(ProposalRow, proposal.id)
        assert stored is not None
        assert stored.origin == "compiled"


def test_journal_check_rejects_decision_without_reviewer(
    workspace_id: int,
    session_factory: Callable[[], Session],
) -> None:
    """결정 상태인데 결정자가 없으면 DB가 막는다."""
    artifact_id = _artifact_id(session_factory, workspace_id)

    with session_factory() as session:
        session.add(_proposal(workspace_id, artifact_id, status="approved"))
        with pytest.raises(IntegrityError) as excinfo:
            session.commit()

    assert _violated_constraint(excinfo) == f"ck_{TABLE}_decision_journal"


def test_journal_check_allows_pending_without_reviewer(
    workspace_id: int,
    session_factory: Callable[[], Session],
) -> None:
    """계류 행은 결정자가 비어 있어도 그대로 남는다."""
    artifact_id = _artifact_id(session_factory, workspace_id)
    proposal = _proposal(workspace_id, artifact_id, status="pending")

    with session_factory() as session:
        session.add(proposal)
        session.commit()
        stored = session.get(ProposalRow, proposal.id)
        assert stored is not None
        assert stored.reviewer is None
        assert stored.reviewed_at is None


def test_journal_check_allows_decision_with_journal(
    workspace_id: int,
    session_factory: Callable[[], Session],
) -> None:
    """결정자와 시각이 함께 있으면 승인 행이 저장된다."""
    artifact_id = _artifact_id(session_factory, workspace_id)
    proposal = _proposal(
        workspace_id,
        artifact_id,
        status="approved",
        reviewer="tester",
        reviewed_at=datetime.now(timezone.utc),
    )

    with session_factory() as session:
        session.add(proposal)
        session.commit()
        stored = session.get(ProposalRow, proposal.id)
        assert stored is not None
        assert stored.status == "approved"


def test_reviewer_grant_unique(
    workspace_id: int,
    session_factory: Callable[[], Session],
) -> None:
    """같은 사용자에게 같은 워크스페이스 권한이 두 번 생기지 않는다."""
    with session_factory() as session:
        user_id = _user_id(session)
        session.add(
            WikiReviewerGrant(user_id=user_id, workspace_id=workspace_id)
        )
        session.commit()

    with session_factory() as session:
        session.add(
            WikiReviewerGrant(user_id=user_id, workspace_id=workspace_id)
        )
        with pytest.raises(IntegrityError) as excinfo:
            session.commit()

    assert _violated_constraint(excinfo) == "wiki_reviewer_grants_pkey"
