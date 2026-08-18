"""즐겨찾기 endpoint를 실 PostgreSQL로 확인한다.

즐겨찾기는 있고 없고만 의미가 있어 지정·해제 모두 멱등이다. 같은 요청을
두 번 보내도 결과 상태가 같으므로 두 번째를 실패로 답하지 않는다.

남의 workspace 문서는 없는 것으로 답한다. 403으로 가르면 응답만으로 그
문서의 존재를 떠볼 수 있다.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from collections.abc import Iterator

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
from catchup.db.models import KnowledgeNode
from catchup.db.models import User
from catchup.db.models import UserStatus
from catchup.db.models import UserWorkspace
from catchup.db.models import Workspace
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
        name=f"즐겨찾기-{uuid.uuid4().hex[:8]}",
        company_id=company_id,
    )
    db.add(workspace)
    db.flush()
    return workspace.id


def _make_user(db: Session, *, prefix: str) -> User:
    """테스트용 사용자 한 명을 만든다."""
    user = User(
        email=f"{prefix}-{uuid.uuid4().hex[:8]}@example.com",
        name=f"구성원-{prefix}",
        picture=f"https://example.com/{prefix}.png",
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
    """인증만 우회한다. 소속·역할 검사는 실 DB로 그대로 돈다."""

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
    user = _make_user(db, prefix="member")
    _join(db, user=user, workspace_id=workspace_id)
    as_user(user)
    return user


# ======================= 문서 헬퍼 =======================


def _make_artifact(
    db: Session, *, workspace_id: int, title: str = "즐겨찾을 문서"
) -> uuid.UUID:
    """문서 한 편을 만든다. 주제 노드도 같이 만든다."""
    node_id = uuid.uuid4()
    db.add(
        KnowledgeNode(
            id=node_id,
            workspace_id=workspace_id,
            node_kind="entity",
            entity_type="feature",
            canonical_key=f"test:favorite:{uuid.uuid4().hex}",
            display_name=title,
            lifecycle_state="active",
        )
    )
    db.flush()
    artifact_id = uuid.uuid4()
    db.add(
        KnowledgeArtifact(
            id=artifact_id,
            workspace_id=workspace_id,
            kind="entity_summary",
            subject_node_id=node_id,
            title=title,
        )
    )
    db.flush()
    return artifact_id


# ======================= 본문 =======================


def test_favorite_twice_is_idempotent(client, member, db, workspace_id):
    """같은 문서를 두 번 담아도 둘 다 200이고 결과는 같다."""
    artifact_id = _make_artifact(db, workspace_id=workspace_id)

    first = client.put(f"/api/v1/wiki/favorites/{artifact_id}")
    second = client.put(f"/api/v1/wiki/favorites/{artifact_id}")

    assert first.status_code == 200
    assert first.json() == {
        "artifact_id": str(artifact_id),
        "is_favorite": True,
    }
    assert second.status_code == 200
    assert second.json()["is_favorite"] is True


def test_list_favorites_returns_the_added_one(
    client, member, db, workspace_id
):
    """담은 문서 한 건이 목록에 실린다."""
    artifact_id = _make_artifact(db, workspace_id=workspace_id, title="즐겨찾기 A")
    client.put(f"/api/v1/wiki/favorites/{artifact_id}")

    response = client.get("/api/v1/wiki/favorites")

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["artifact_id"] == str(artifact_id)
    assert items[0]["title"] == "즐겨찾기 A"
    assert items[0]["kind"] == "entity_summary"
    assert items[0]["channel_id"] is None
    assert items[0]["folder_id"] is None
    assert items[0]["favorited_at"] is not None


def test_unfavorite_twice_is_idempotent(client, member, db, workspace_id):
    """해제를 두 번 보내도 둘 다 204다."""
    artifact_id = _make_artifact(db, workspace_id=workspace_id)
    client.put(f"/api/v1/wiki/favorites/{artifact_id}")

    first = client.delete(f"/api/v1/wiki/favorites/{artifact_id}")
    second = client.delete(f"/api/v1/wiki/favorites/{artifact_id}")

    assert first.status_code == 204
    assert second.status_code == 204
    assert client.get("/api/v1/wiki/favorites").json()["items"] == []


def test_favorite_unknown_artifact_is_four_hundred_four(client, member):
    """없는 문서는 담을 수 없다."""
    response = client.put(f"/api/v1/wiki/favorites/{uuid.uuid4()}")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "ARTIFACT_NOT_FOUND"


def test_favorite_other_workspace_artifact_is_four_hundred_four(
    client, member, db, workspace_id, company_id
):
    """남의 workspace 문서도 없는 것으로 답한다."""
    other = Workspace(name=f"남의-{uuid.uuid4().hex[:8]}", company_id=company_id)
    db.add(other)
    db.flush()
    artifact_id = _make_artifact(db, workspace_id=other.id)

    response = client.put(f"/api/v1/wiki/favorites/{artifact_id}")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "ARTIFACT_NOT_FOUND"


def test_unfavorite_unknown_artifact_is_four_hundred_four(client, member):
    """없는 문서는 해제도 404다."""
    response = client.delete(f"/api/v1/wiki/favorites/{uuid.uuid4()}")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "ARTIFACT_NOT_FOUND"
