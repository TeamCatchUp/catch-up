"""발행된 문서를 읽는 endpoint를 실 PostgreSQL로 확인한다.

산문은 표현이고 근거 지위는 statement에만 있다. 그래서 이 응답은 산문과
근거 인용을 반드시 함께 싣는다. 발행 판이 없는 문서와 남의 workspace
문서는 똑같이 404다 — 코드가 갈려도 존재 여부가 새면 안 된다.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from collections.abc import Iterator
from datetime import datetime
from datetime import timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Connection
from sqlalchemy import Engine
from sqlalchemy import create_engine
from sqlalchemy import inspect
from sqlalchemy import select
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker

from catchup.configs.config import settings
from catchup.db.dependencies import get_db
from catchup.db.models import ChannelFolder
from catchup.db.models import KnowledgeArtifact
from catchup.db.models import KnowledgeArtifactChangeProposal
from catchup.db.models import KnowledgeArtifactRevision
from catchup.db.models import KnowledgeNode
from catchup.db.models import User
from catchup.db.models import UserStatus
from catchup.db.models import UserWorkspace
from catchup.db.models import Workspace
from catchup.knowledge_maintenance.domain.artifact import BLOCK_KIND_CLAIM_SECTION
from catchup.knowledge_maintenance.domain.artifact import ArtifactBlock
from catchup.knowledge_maintenance.domain.artifact import BlockSource
from catchup.knowledge_maintenance.domain.artifact import serialize_blocks
from catchup.server.knowledge_review.dependencies import get_reviewer_user
from catchup.server.wiki.api import router

# ======================= 실 DB fixture =======================


@pytest.fixture(scope="module")
def engine() -> Iterator[Engine]:
    engine = create_engine(settings.sqlalchemy_database_url)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except OperationalError:
        engine.dispose()
        pytest.skip("PostgreSQL이 없어 통합 테스트를 건너뛴다.")

    if not inspect(engine).has_table(ChannelFolder.__tablename__):
        engine.dispose()
        pytest.skip("채널 테이블이 없다. alembic upgrade head가 필요하다.")

    yield engine
    engine.dispose()


@pytest.fixture(scope="module")
def company_id(engine: Engine) -> int:
    """실 DB에 있는 회사 하나의 id를 빌린다."""
    with engine.connect() as connection:
        found = connection.execute(
            select(Workspace.company_id).order_by(Workspace.id).limit(1)
        ).scalar()

    if found is None:
        pytest.skip("workspace가 없어 통합 테스트를 건너뛴다.")
    return found


@pytest.fixture
def connection(engine: Engine) -> Iterator[Connection]:
    """테스트마다 되감는 연결 하나를 만든다."""
    connection = engine.connect()
    transaction = connection.begin()

    yield connection

    transaction.rollback()
    connection.close()


@pytest.fixture
def session_factory(connection: Connection) -> Callable[[], Session]:
    """같은 트랜잭션 위에 세션을 여는 factory를 만든다."""
    return sessionmaker(
        bind=connection,
        join_transaction_mode="create_savepoint",
        expire_on_commit=False,
    )


@pytest.fixture
def db(session_factory: Callable[[], Session]) -> Iterator[Session]:
    """행을 넣고 읽을 세션을 만든다."""
    session = session_factory()

    yield session

    session.close()


@pytest.fixture
def workspace_id(db: Session, company_id: int) -> int:
    """이 테스트만 쓰는 새 workspace를 만든다."""
    workspace = Workspace(
        name=f"읽기-{uuid.uuid4().hex[:8]}",
        company_id=company_id,
    )
    db.add(workspace)
    db.flush()
    return workspace.id


def _make_user(db: Session, *, email: str) -> User:
    """테스트용 사용자 한 명을 만든다."""
    user = User(
        email=email,
        name="구성원",
        provider="keycloak",
        status=UserStatus.ACTIVE,
    )
    db.add(user)
    db.flush()
    return user


def _join(db: Session, *, user: User, workspace_id: int) -> None:
    """사용자를 workspace 구성원으로 넣는다."""
    db.add(UserWorkspace(user_id=user.id, workspace_id=workspace_id))
    db.flush()


# ======================= 앱 fixture =======================


@pytest.fixture
def app() -> FastAPI:
    application = FastAPI()
    application.include_router(router)
    return application


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def as_user(app: FastAPI, db: Session) -> Callable[[User], None]:
    """인증만 우회한다. 소속 검사는 실 DB로 그대로 돈다."""

    def register(user: User) -> None:
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[get_reviewer_user] = lambda: user

    return register


@pytest.fixture
def member(
    db: Session,
    workspace_id: int,
    as_user: Callable[[User], None],
) -> User:
    """새 workspace에만 속한 구성원 한 명을 세운다."""
    user = _make_user(db, email=f"member-{uuid.uuid4().hex[:8]}@example.com")
    _join(db, user=user, workspace_id=workspace_id)
    as_user(user)
    return user


@pytest.fixture
def outsider(
    db: Session,
    as_user: Callable[[User], None],
) -> User:
    """어느 workspace에도 속하지 않은 사용자 한 명을 세운다."""
    user = _make_user(db, email=f"outsider-{uuid.uuid4().hex[:8]}@example.com")
    as_user(user)
    return user


# ======================= 문서·판 헬퍼 =======================


def _block(narrative: str | None) -> ArtifactBlock:
    """근거 인용이 붙은 claim 절 블록 하나를 만든다."""
    claim_id = uuid.uuid4()
    return ArtifactBlock(
        block_kind=BLOCK_KIND_CLAIM_SECTION,
        heading="request_status",
        body="검토 중 (2026-08-15 관찰)",
        claim_ids=(claim_id,),
        proposal_ids=(),
        ontology_version="v3",
        sources=(
            BlockSource(
                claim_id=claim_id,
                statement="상태는 검토 중이다",
                observed_at=datetime(2026, 8, 15, tzinfo=timezone.utc),
                citation_verified=True,
            ),
        ),
        narrative=narrative,
    )


def _artifact_without_revision(db: Session, *, workspace_id: int) -> uuid.UUID:
    """판이 하나도 없는 문서 한 편을 만든다."""
    node = KnowledgeNode(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        node_kind="entity",
        entity_type="feature_request",
        canonical_key=f"test:feature_request:{uuid.uuid4().hex}",
        display_name="요청 A",
        lifecycle_state="active",
    )
    db.add(node)
    db.flush()
    artifact = KnowledgeArtifact(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        kind="feature_request_status",
        subject_node_id=node.id,
        title="요청 현황: 요청 A",
    )
    db.add(artifact)
    db.flush()
    return artifact.id


def _publish(
    db: Session,
    *,
    workspace_id: int,
    narrative: str | None,
    artifact_id: uuid.UUID | None = None,
    revision_number: int = 1,
) -> tuple[uuid.UUID, uuid.UUID]:
    """문서 하나를 발행 상태까지 만들어 (문서 id, 판 id)를 돌려준다.

    승인 흐름을 흉내 내지 않고 행을 직접 심는다. 여기서 보는 것은 읽기
    표면이 최신 판을 어떻게 고르는가이지 승인 규칙이 아니다.
    """
    if artifact_id is None:
        artifact_id = _artifact_without_revision(db, workspace_id=workspace_id)
    blocks = serialize_blocks([_block(narrative)])
    proposal_id = uuid.uuid4()
    db.add(
        KnowledgeArtifactChangeProposal(
            id=proposal_id,
            workspace_id=workspace_id,
            artifact_id=artifact_id,
            blocks=blocks,
            status="approved",
            content_hash=uuid.uuid4().hex,
            idempotency_key=uuid.uuid4().hex,
            base_revision_id=None,
            reviewer="test",
            reviewed_at=datetime(2026, 8, 15, tzinfo=timezone.utc),
        )
    )
    db.flush()
    revision_id = uuid.uuid4()
    db.add(
        KnowledgeArtifactRevision(
            id=revision_id,
            workspace_id=workspace_id,
            artifact_id=artifact_id,
            revision_number=revision_number,
            blocks=blocks,
            source_proposal_id=proposal_id,
        )
    )
    db.flush()
    return artifact_id, revision_id


# ======================= 본문 =======================


def test_returns_the_latest_published_revision(client, member, db, workspace_id):
    """발행된 최신 판의 블록을 산문·근거와 함께 돌려준다."""
    artifact_id, revision_id = _publish(
        db, workspace_id=workspace_id, narrative="이 요구는 검토 중이다."
    )

    response = client.get(f"/api/v1/wiki/artifacts/{artifact_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["revision_id"] == str(revision_id)
    block = body["blocks"][0]
    assert block["block_index"] == 0
    assert block["narrative"] == "이 요구는 검토 중이다."
    assert block["sources"][0]["statement"] == "상태는 검토 중이다"
    assert block["sources"][0]["citation_verified"] is True


def test_second_revision_wins(client, member, db, workspace_id):
    """판이 두 개면 번호가 큰 쪽을 돌려준다."""
    artifact_id, _ = _publish(
        db, workspace_id=workspace_id, narrative="첫 번째 판의 문장이다."
    )
    _, second_id = _publish(
        db,
        workspace_id=workspace_id,
        narrative="두 번째 판의 문장이다.",
        artifact_id=artifact_id,
        revision_number=2,
    )

    response = client.get(f"/api/v1/wiki/artifacts/{artifact_id}")

    body = response.json()
    assert body["revision_id"] == str(second_id)
    assert body["blocks"][0]["narrative"] == "두 번째 판의 문장이다."


def test_block_without_narrative_is_null(client, member, db, workspace_id):
    """산문이 없던 블록은 없음으로 실린다."""
    artifact_id, _ = _publish(db, workspace_id=workspace_id, narrative=None)

    response = client.get(f"/api/v1/wiki/artifacts/{artifact_id}")

    assert response.json()["blocks"][0]["narrative"] is None


def test_unpublished_artifact_is_four_hundred_four(
    client, member, db, workspace_id
):
    """발행 판이 없는 문서는 404다."""
    artifact_id = _artifact_without_revision(db, workspace_id=workspace_id)

    response = client.get(f"/api/v1/wiki/artifacts/{artifact_id}")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "ARTIFACT_NOT_PUBLISHED"


def test_unknown_artifact_is_four_hundred_four(client, member):
    """없는 문서도 404다."""
    response = client.get(f"/api/v1/wiki/artifacts/{uuid.uuid4()}")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "ARTIFACT_NOT_FOUND"


def test_other_workspace_artifact_is_four_hundred_four(
    client, member, db, workspace_id, company_id
):
    """다른 workspace의 발행 문서도 없는 것으로 답한다."""
    other = Workspace(name=f"남의-{uuid.uuid4().hex[:8]}", company_id=company_id)
    db.add(other)
    db.flush()
    artifact_id, _ = _publish(db, workspace_id=other.id, narrative="문장이다.")

    response = client.get(f"/api/v1/wiki/artifacts/{artifact_id}")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "ARTIFACT_NOT_FOUND"


def test_requires_workspace_membership(client, outsider):
    """소속이 없으면 403이다."""
    response = client.get(f"/api/v1/wiki/artifacts/{uuid.uuid4()}")

    assert response.status_code == 403
