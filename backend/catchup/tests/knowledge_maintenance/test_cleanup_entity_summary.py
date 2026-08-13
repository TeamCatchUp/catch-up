"""정의 이전 entity_summary 문서를 지우는 러너를 실 PostgreSQL로 확인한다.

지우는 일은 되돌릴 수 없고, 대상이 아닌 문서까지 딸려가면 손으로 복구할
길이 없다. 그래서 fake가 아니라 실 DB에 문서·변경안·판·판정을 한 벌로
심어 두고, 기본 실행이 정말 아무것도 지우지 않는지와 `--apply`가 파생
행까지 함께 지우는지를 본다.

정의를 딛고 선 문서가 살아남는지도 같은 자리에서 본다. 삭제 범위를
`definition_id IS NULL`로 좁힌 것이 이 러너의 유일한 안전 장치이기
때문이다.
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
from sqlalchemy import func
from sqlalchemy import inspect
from sqlalchemy import select
from sqlalchemy import text
from sqlalchemy import update as sa_update
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker

from catchup.configs.config import settings
from catchup.db.models import KnowledgeArtifact
from catchup.db.models import KnowledgeArtifactChangeProposal as ProposalRow
from catchup.db.models import KnowledgeArtifactRevision as RevisionRow
from catchup.db.models import KnowledgeBlockVerdict
from catchup.db.models import KnowledgeNode as NodeRow
from catchup.db.models import Workspace
from catchup.evaluation.cleanup_entity_summary_artifacts import format_report
from catchup.evaluation.cleanup_entity_summary_artifacts import run_cleanup
from catchup.tests.knowledge_maintenance.test_artifact_definition_schema import (
    _definition_with_channel,
)

LEGACY_KIND = "entity_summary"
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

    if not inspect(engine).has_table(KnowledgeBlockVerdict.__tablename__):
        engine.dispose()
        pytest.skip("문서 테이블이 없다. alembic upgrade head가 필요하다.")

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
    """문서가 다룰 주제 노드 한 개를 만든다."""
    node_id = uuid.uuid4()
    session.add(
        NodeRow(
            id=node_id,
            workspace_id=workspace_id,
            node_kind="entity",
            entity_type="feature",
            canonical_key=f"test:feature:{uuid.uuid4().hex}",
            display_name="결제 기능",
        )
    )
    session.flush()
    return node_id


def _artifact(
    session: Session,
    workspace_id: int,
    *,
    kind: str = LEGACY_KIND,
    definition_id: uuid.UUID | None = None,
    channel_id: uuid.UUID | None = None,
) -> uuid.UUID:
    """문서 한 편을 만든다. 정의를 주면 정의를 딛고 선 문서가 된다."""
    artifact_id = uuid.uuid4()
    session.add(
        KnowledgeArtifact(
            id=artifact_id,
            workspace_id=workspace_id,
            kind=kind,
            definition_id=definition_id,
            channel_id=channel_id,
            subject_node_id=_subject_node(session, workspace_id),
            title="결제 기능",
        )
    )
    session.flush()
    return artifact_id


def _full_tree(session: Session, workspace_id: int) -> uuid.UUID:
    """문서 한 편과 그 아래 변경안·판·블록 판정을 한 벌로 심는다.

    변경안과 판이 서로를 가리키는 모양(base_revision_id ↔
    source_proposal_id)까지 그대로 만든다. 러너가 그 순환을 끊고 지우는지
    확인하려면 순환이 실제로 있어야 한다.

    변경안은 승인 상태로 둔다. 사람이 이미 결정한 행까지 이 러너가 지운다는
    점이 확인 대상이기 때문이다.
    """
    artifact_id = _artifact(session, workspace_id)
    proposal_id = uuid.uuid4()
    revision_id = uuid.uuid4()
    decided_at = datetime.now(timezone.utc)

    session.add(
        ProposalRow(
            id=proposal_id,
            workspace_id=workspace_id,
            artifact_id=artifact_id,
            blocks=[],
            status="approved",
            content_hash=uuid.uuid4().hex,
            idempotency_key=uuid.uuid4().hex,
            reviewer=REVIEWER,
            reviewed_at=decided_at,
        )
    )
    session.flush()
    session.add(
        RevisionRow(
            id=revision_id,
            workspace_id=workspace_id,
            artifact_id=artifact_id,
            revision_number=1,
            blocks=[],
            source_proposal_id=proposal_id,
        )
    )
    session.flush()
    session.execute(
        sa_update(ProposalRow)
        .where(ProposalRow.id == proposal_id)
        .values(base_revision_id=revision_id)
    )
    session.add(
        KnowledgeBlockVerdict(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            proposal_id=proposal_id,
            block_index=0,
            block_content_hash=uuid.uuid4().hex,
            verdict="approved",
            reviewer=REVIEWER,
            reviewed_at=decided_at,
        )
    )
    session.flush()
    return artifact_id


def _count(session: Session, model: type, **filters: object) -> int:
    """조건에 맞는 행 수를 센다."""
    statement = select(func.count()).select_from(model)
    for column, value in filters.items():
        statement = statement.where(getattr(model, column) == value)
    return session.execute(statement).scalar_one()


def _legacy_artifacts(session: Session, workspace_id: int) -> int:
    """정의 이전 entity_summary 문서 수를 센다."""
    return session.execute(
        select(func.count())
        .select_from(KnowledgeArtifact)
        .where(KnowledgeArtifact.workspace_id == workspace_id)
        .where(KnowledgeArtifact.kind == LEGACY_KIND)
        .where(KnowledgeArtifact.definition_id.is_(None))
    ).scalar_one()


def test_dry_run_deletes_nothing(
    session: Session,
    workspace_id: int,
) -> None:
    """기본 실행은 세어 보기만 하고 한 행도 지우지 않는다."""
    _full_tree(session, workspace_id)
    before = _legacy_artifacts(session, workspace_id)

    counts = run_cleanup(session, workspace_id=workspace_id, apply=False)

    assert counts.artifacts == before
    assert counts.proposals >= 1
    assert counts.revisions >= 1
    assert counts.block_verdicts >= 1
    assert _legacy_artifacts(session, workspace_id) == before


def test_apply_deletes_legacy_and_derived_rows(
    session: Session,
    workspace_id: int,
) -> None:
    """--apply는 문서와 그 아래 변경안·판·판정을 함께 지운다."""
    artifact_id = _full_tree(session, workspace_id)

    run_cleanup(session, workspace_id=workspace_id, apply=True)

    assert _count(session, KnowledgeArtifact, id=artifact_id) == 0
    assert _count(session, ProposalRow, artifact_id=artifact_id) == 0
    assert _count(session, RevisionRow, artifact_id=artifact_id) == 0
    assert _legacy_artifacts(session, workspace_id) == 0


def test_definition_documents_survive(
    session: Session,
    workspace_id: int,
    session_factory: Callable[[], Session],
) -> None:
    """정의를 딛고 선 문서와 다른 kind 문서는 남는다."""
    definition = _definition_with_channel(session_factory, workspace_id)
    kept_id = _artifact(
        session,
        workspace_id,
        kind=definition.kind,
        definition_id=definition.id,
        channel_id=definition.channel_id,
    )
    other_kind_id = _artifact(session, workspace_id, kind="channel_digest")
    legacy_id = _full_tree(session, workspace_id)

    run_cleanup(session, workspace_id=workspace_id, apply=True)

    assert _count(session, KnowledgeArtifact, id=kept_id) == 1
    assert _count(session, KnowledgeArtifact, id=other_kind_id) == 1
    assert _count(session, KnowledgeArtifact, id=legacy_id) == 0


def test_other_workspace_survives(
    session: Session,
    session_factory: Callable[[], Session],
    workspace_id: int,
) -> None:
    """다른 workspace의 같은 모양 문서는 건드리지 않는다."""
    company_id = session.execute(
        select(Workspace.company_id).where(Workspace.id == workspace_id)
    ).scalar_one()
    other = Workspace(name=f"ws-{uuid.uuid4().hex[:8]}", company_id=company_id)
    session.add(other)
    session.flush()
    other_id = _artifact(session, other.id)
    _full_tree(session, workspace_id)

    run_cleanup(session, workspace_id=workspace_id, apply=True)

    assert _count(session, KnowledgeArtifact, id=other_id) == 1


def test_dry_run_report_mentions_reprojection(
    session: Session,
    workspace_id: int,
) -> None:
    """dry-run 보고는 검색 projection 잔존분 안내를 함께 적는다."""
    counts = run_cleanup(session, workspace_id=workspace_id, apply=False)

    report = format_report(counts, apply=False)

    assert "재투영" in report
    assert "knowledge_artifacts" in report
