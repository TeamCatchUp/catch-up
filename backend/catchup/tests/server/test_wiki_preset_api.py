"""preset 카탈로그 조회 API의 내용·인가 계약을 확인한다.

핸들러는 DB를 읽지 않지만 인가는 실 PostgreSQL로 본다. 소속
(user_workspaces)이 DB 사실이라, 소속 없는 사용자가 403으로 막히는 일은
대역으로는 재현되지 않는다. 인증만 dependency_overrides로 우회한다.

응답이 선택 규칙을 흘리지 않는다는 것도 함께 못박는다. 규칙이 응답에
실리면 소비자가 그것을 되돌려 보낼 입구가 생기고, 그 순간 raw spec이
뒷문으로 열린다.
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
def workspace_ids(engine: Engine) -> tuple[int, int]:
    """실 DB에 있는 workspace 두 개를 빌린다."""
    with engine.connect() as connection:
        found = (
            connection.execute(
                select(Workspace.id).order_by(Workspace.id).limit(2)
            )
            .scalars()
            .all()
        )

    if len(found) < 2:
        pytest.skip("workspace가 둘 이상 없어 통합 테스트를 건너뛴다.")
    return found[0], found[1]


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
    workspace_ids: tuple[int, int],
    as_user: Callable[[User], None],
) -> User:
    """역할이 하나도 없는 구성원 한 명을 세운다."""
    workspace_id, _ = workspace_ids
    user = _make_user(db, email=f"member-{uuid.uuid4().hex[:8]}@example.com")
    _join(db, user=user, workspace_id=workspace_id)
    as_user(user)
    return user


@pytest.fixture
def outsider(
    db: Session,
    workspace_ids: tuple[int, int],
    as_user: Callable[[User], None],
) -> User:
    """어느 workspace에도 속하지 않은 사용자 한 명을 세운다."""
    user = _make_user(db, email=f"outsider-{uuid.uuid4().hex[:8]}@example.com")
    as_user(user)
    return user


# ======================= 브리프 케이스 =======================


def test_lists_all_six_domains_including_the_empty_ones(
    client: TestClient, member: User
) -> None:
    """콘텐츠가 없는 도메인도 목록에 실린다."""
    response = client.get("/api/v1/wiki/definition-presets")
    assert response.status_code == 200
    domains = response.json()["domains"]
    assert len(domains) == 6
    voc = next(d for d in domains if d["id"] == "voc")
    assert len(voc["purposes"]) == 6
    assert len(voc["kinds"]) == 5
    others = [d for d in domains if d["id"] != "voc"]
    assert all(d["purposes"] == [] and d["kinds"] == [] for d in others)


def test_does_not_leak_selection_spec(
    client: TestClient, member: User
) -> None:
    """선택 규칙은 응답에 담기지 않는다."""
    response = client.get("/api/v1/wiki/definition-presets")
    assert "selection_spec" not in response.text
    assert "entity_filter" not in response.text


def test_requires_workspace_membership(
    client: TestClient, outsider: User
) -> None:
    """소속이 없으면 403이다."""
    response = client.get("/api/v1/wiki/definition-presets")
    assert response.status_code == 403
