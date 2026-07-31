"""artifact 계열 테이블의 제약을 실 PostgreSQL에서 확인한다.

제약은 DB가 강제해야 의미가 있다. 모델 정의만 보고 통과했다고 믿으면
마이그레이션이 빠졌을 때 알아채지 못하므로 실제 스키마에 넣어 본다.
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
from sqlalchemy.exc import IntegrityError
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker

from catchup.configs.config import settings
from catchup.db.models import KnowledgeArtifact
from catchup.db.models import KnowledgeArtifactChangeProposal
from catchup.db.models import KnowledgeArtifactRevision
from catchup.db.models import KnowledgeNode
from catchup.db.models import Workspace


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
def session(session_factory: Callable[[], Session]) -> Iterator[Session]:
    with session_factory() as session:
        yield session


def _subject_node(session: Session, workspace_id: int) -> uuid.UUID:
    """artifact가 설명할 대상 node를 하나 만든다."""
    node = KnowledgeNode(
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


def _artifact(
    session: Session,
    workspace_id: int,
    subject_node_id: uuid.UUID,
    kind: str = "entity_page",
) -> uuid.UUID:
    """대상 node에 붙는 artifact를 하나 만든다."""
    artifact = KnowledgeArtifact(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        kind=kind,
        subject_node_id=subject_node_id,
        title="결제 기능",
    )
    session.add(artifact)
    session.flush()
    return artifact.id


def _violated_constraint(excinfo: pytest.ExceptionInfo[IntegrityError]) -> str:
    """터진 제약의 이름을 꺼낸다.

    어떤 제약이 막았는지까지 확인해야 계약이 잠긴다. IntegrityError만 보면
    이름이 바뀌거나 엉뚱한 제약(NOT NULL 등)이 대신 막아도 테스트가 통과한다.
    """
    original = excinfo.value.orig
    diagnostic = getattr(original, "diag", None)
    name = getattr(diagnostic, "constraint_name", None)
    if name:
        return name
    return str(original)


def _proposal(
    workspace_id: int,
    artifact_id: uuid.UUID,
    **overrides: object,
) -> KnowledgeArtifactChangeProposal:
    """기본값이 채워진 change proposal을 만든다."""
    values: dict[str, object] = {
        "id": uuid.uuid4(),
        "workspace_id": workspace_id,
        "artifact_id": artifact_id,
        "blocks": [],
        "status": "pending",
        "content_hash": "0" * 64,
        "idempotency_key": f"key:{uuid.uuid4().hex}",
    }
    values.update(overrides)
    return KnowledgeArtifactChangeProposal(**values)


def test_rejected_requires_reason(
    workspace_id: int,
    session: Session,
) -> None:
    """rejected인데 사유가 없으면 DB가 막는다."""
    artifact_id = _artifact(
        session, workspace_id, _subject_node(session, workspace_id)
    )
    session.add(
        _proposal(
            workspace_id,
            artifact_id,
            status="rejected",
            rejection_reason=None,
        )
    )

    with pytest.raises(IntegrityError) as excinfo:
        session.flush()

    assert (
        _violated_constraint(excinfo)
        == "ck_knowledge_artifact_change_proposals_rejection_reason"
    )


def test_rejected_with_reason_is_allowed(
    workspace_id: int,
    session: Session,
) -> None:
    """사유가 있으면 rejected가 저장된다."""
    artifact_id = _artifact(
        session, workspace_id, _subject_node(session, workspace_id)
    )
    session.add(
        _proposal(
            workspace_id,
            artifact_id,
            status="rejected",
            rejection_reason="근거가 부족하다",
        )
    )

    session.flush()


def test_unknown_status_is_rejected(
    workspace_id: int,
    session: Session,
) -> None:
    """정의되지 않은 status는 DB가 막는다."""
    artifact_id = _artifact(
        session, workspace_id, _subject_node(session, workspace_id)
    )
    session.add(_proposal(workspace_id, artifact_id, status="bogus"))

    with pytest.raises(IntegrityError) as excinfo:
        session.flush()

    assert (
        _violated_constraint(excinfo)
        == "ck_knowledge_artifact_change_proposals_status"
    )


def test_idempotency_key_is_unique_per_workspace(
    workspace_id: int,
    session: Session,
) -> None:
    """같은 workspace에서 같은 key로 두 번 만들 수 없다."""
    artifact_id = _artifact(
        session, workspace_id, _subject_node(session, workspace_id)
    )
    key = f"key:{uuid.uuid4().hex}"
    session.add(_proposal(workspace_id, artifact_id, idempotency_key=key))
    session.flush()

    session.add(_proposal(workspace_id, artifact_id, idempotency_key=key))
    with pytest.raises(IntegrityError) as excinfo:
        session.flush()

    assert (
        _violated_constraint(excinfo)
        == "uq_knowledge_artifact_change_proposals_idempotency_key"
    )


def test_one_artifact_per_subject_and_kind(
    workspace_id: int,
    session: Session,
) -> None:
    """같은 대상·같은 kind로 artifact가 둘 생기지 않는다."""
    node_id = _subject_node(session, workspace_id)
    _artifact(session, workspace_id, node_id)

    with pytest.raises(IntegrityError) as excinfo:
        _artifact(session, workspace_id, node_id)

    assert _violated_constraint(excinfo) == "uq_knowledge_artifacts_subject"


def test_other_kind_on_same_subject_is_allowed(
    workspace_id: int,
    session: Session,
) -> None:
    """kind가 다르면 같은 대상에 artifact를 더 붙일 수 있다."""
    node_id = _subject_node(session, workspace_id)
    _artifact(session, workspace_id, node_id, kind="entity_page")

    _artifact(session, workspace_id, node_id, kind="timeline")


def test_revision_number_is_unique_per_artifact(
    workspace_id: int,
    session: Session,
) -> None:
    """한 artifact에 같은 revision 번호가 둘 생기지 않는다."""
    artifact_id = _artifact(
        session, workspace_id, _subject_node(session, workspace_id)
    )
    proposal = _proposal(workspace_id, artifact_id, status="approved")
    session.add(proposal)
    session.flush()

    def _revision() -> KnowledgeArtifactRevision:
        return KnowledgeArtifactRevision(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            artifact_id=artifact_id,
            revision_number=1,
            blocks=[],
            source_proposal_id=proposal.id,
        )

    session.add(_revision())
    session.flush()

    session.add(_revision())
    with pytest.raises(IntegrityError) as excinfo:
        session.flush()

    assert (
        _violated_constraint(excinfo)
        == "uq_knowledge_artifact_revisions_number"
    )


def test_proposal_can_point_at_base_revision(
    workspace_id: int,
    session: Session,
) -> None:
    """후속 proposal이 자기가 딛고 선 revision을 가리킨다."""
    artifact_id = _artifact(
        session, workspace_id, _subject_node(session, workspace_id)
    )
    first = _proposal(workspace_id, artifact_id, status="approved")
    session.add(first)
    session.flush()

    revision = KnowledgeArtifactRevision(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        artifact_id=artifact_id,
        revision_number=1,
        blocks=[{"type": "paragraph", "text": "첫 판"}],
        source_proposal_id=first.id,
    )
    session.add(revision)
    session.flush()

    second = _proposal(workspace_id, artifact_id, base_revision_id=revision.id)
    session.add(second)
    session.flush()

    session.expire_all()
    stored = session.get(KnowledgeArtifactChangeProposal, second.id)
    assert stored is not None
    assert stored.base_revision_id == revision.id
    assert stored.status == "pending"
    assert stored.blocks == []


def test_base_revision_must_exist(
    workspace_id: int,
    session: Session,
) -> None:
    """없는 revision을 가리키면 DB가 막는다."""
    artifact_id = _artifact(
        session, workspace_id, _subject_node(session, workspace_id)
    )
    session.add(
        _proposal(workspace_id, artifact_id, base_revision_id=uuid.uuid4())
    )

    with pytest.raises(IntegrityError) as excinfo:
        session.flush()

    assert (
        _violated_constraint(excinfo)
        == "fk_knowledge_artifact_change_proposals_base_revision"
    )
