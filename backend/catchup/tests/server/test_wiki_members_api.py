"""워크스페이스 활성 멤버 목록 endpoint를 실 PostgreSQL로 확인한다.

담당자 피커가 쓰는 목록이라 응답 모양이 담당자 응답과 같아야 한다. 모양이
다르면 화면이 "고를 사람"과 "이미 담당인 사람"을 서로 다른 타입으로 다뤄야
한다.

활성 여부와 소속은 DB 사실이므로 실 연결로 본다. 인증만
dependency_overrides로 우회한다.
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
def db(connection: Connection) -> Iterator[Session]:
    """같은 트랜잭션 위에 세션을 연다."""
    session = sessionmaker(
        bind=connection,
        join_transaction_mode="create_savepoint",
        expire_on_commit=False,
    )()

    yield session

    session.close()


@pytest.fixture
def workspace_id(db: Session, company_id: int) -> int:
    """이 테스트만 쓰는 새 workspace를 만든다."""
    workspace = Workspace(
        name=f"멤버-{uuid.uuid4().hex[:8]}",
        company_id=company_id,
    )
    db.add(workspace)
    db.flush()
    return workspace.id


def _member(
    db: Session,
    *,
    workspace_id: int,
    name: str,
    status: UserStatus = UserStatus.ACTIVE,
) -> User:
    """이름과 상태를 지정한 workspace 구성원 한 명을 만든다."""
    user = User(
        email=f"{uuid.uuid4().hex[:8]}@example.com",
        name=name,
        picture=f"https://example.com/{uuid.uuid4().hex[:8]}.png",
        provider="keycloak",
        status=status,
    )
    db.add(user)
    db.flush()
    db.add(UserWorkspace(user_id=user.id, workspace_id=workspace_id))
    db.flush()
    return user


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
    user = _member(db, workspace_id=workspace_id, name="가")
    as_user(user)
    return user


# ======================= 목록 =======================


def test_list_members_returns_active_members_in_name_order(
    client, db, workspace_id, member
):
    """활성 구성원만 이름 순으로 담당자 응답과 같은 모양으로 실린다."""
    second = _member(db, workspace_id=workspace_id, name="나")
    _member(
        db,
        workspace_id=workspace_id,
        name="다",
        status=UserStatus.INACTIVE,
    )

    response = client.get("/api/v1/wiki/members")

    assert response.status_code == 200
    assert response.json()["items"] == [
        {
            "user_id": member.id,
            "display_name": member.name,
            "profile_image_url": member.picture,
        },
        {
            "user_id": second.id,
            "display_name": second.name,
            "profile_image_url": second.picture,
        },
    ]


def test_list_members_hides_other_workspace(
    client, db, workspace_id, company_id, member
):
    """다른 workspace의 구성원은 실리지 않는다."""
    other = Workspace(name=f"남의-{uuid.uuid4().hex[:8]}", company_id=company_id)
    db.add(other)
    db.flush()
    _member(db, workspace_id=other.id, name="라")

    response = client.get("/api/v1/wiki/members")

    assert [item["user_id"] for item in response.json()["items"]] == [member.id]


def test_list_members_requires_membership(client, db, as_user):
    """어느 workspace에도 속하지 않으면 403이다."""
    outsider = User(
        email=f"{uuid.uuid4().hex[:8]}@example.com",
        name="바깥",
        provider="keycloak",
        status=UserStatus.ACTIVE,
    )
    db.add(outsider)
    db.flush()
    as_user(outsider)

    response = client.get("/api/v1/wiki/members")

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "NOT_MEMBER"
