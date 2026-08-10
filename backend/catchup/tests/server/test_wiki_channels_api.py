"""채널·폴더 관리 API의 인가·응답·오류 계약을 확인한다.

권한 판정은 실 PostgreSQL로 본다. 소속(user_workspaces)과 채널 관리자
(channel_admins)가 모두 DB 사실이고, UNIQUE 위반을 409로 옮기는 일은
대역으로는 아예 재현되지 않기 때문이다. 인증만 dependency_overrides로
우회한다 — 쿠키 JWT를 만드는 일은 이 라우터의 검증 대상이 아니다.

이 라우터의 첫 겹은 소속뿐이다. 검수 API와 달리 역할이 하나도 없는
구성원이 첫 채널을 만들 수 있어야 하므로, 그 사실 자체를 테스트로
못박는다.
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
from catchup.db.models import Channel
from catchup.db.models import ChannelAdmin
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
    """같은 트랜잭션 위에 세션을 여는 factory를 만든다.

    핸들러가 db.commit()을 부르므로 savepoint로 참여시킨다. 바깥
    트랜잭션은 그대로라 테스트가 끝나면 전부 되감긴다.
    """
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


def _make_channel(
    db: Session, *, workspace_id: int, created_by: int, name: str | None = None
) -> uuid.UUID:
    """채널 하나를 만든다. 관리자는 세우지 않는다."""
    channel_id = uuid.uuid4()
    db.add(
        Channel(
            id=channel_id,
            workspace_id=workspace_id,
            name=name or f"채널-{uuid.uuid4().hex[:8]}",
            created_by=created_by,
        )
    )
    db.flush()
    return channel_id


def _make_artifact(
    db: Session,
    *,
    workspace_id: int,
    channel_id: uuid.UUID,
    folder_id: uuid.UUID | None = None,
) -> uuid.UUID:
    """그 채널(과 폴더)에 놓인 문서 한 편을 만든다.

    workspace_id는 채널·폴더와 같은 값을 그대로 받는다. 문서는 채널과
    폴더에 각각 (workspace_id, ...) 복합 FK로 묶여 있어, 어긋나면 삽입
    자체가 막힌다.
    """
    node_id = uuid.uuid4()
    db.add(
        KnowledgeNode(
            id=node_id,
            workspace_id=workspace_id,
            node_kind="entity",
            entity_type="feature",
            canonical_key=f"test:channels:{uuid.uuid4().hex}",
            display_name="속도 제한 기능",
        )
    )
    db.flush()
    artifact_id = uuid.uuid4()
    db.add(
        KnowledgeArtifact(
            id=artifact_id,
            workspace_id=workspace_id,
            kind="entity_summary",
            channel_id=channel_id,
            folder_id=folder_id,
            subject_node_id=node_id,
            title="오픈 API",
        )
    )
    db.flush()
    return artifact_id


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
    """인증만 우회한다. 소속·관리자 검사는 실 DB로 그대로 돈다."""

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


# ======================= 브리프 케이스 =======================


def test_member_creates_channel_and_becomes_admin(
    client: TestClient, member: User
) -> None:
    """구성원이 만든 채널의 관리자는 생성자다 — 이름을 바꿀 수 있다."""
    response = client.post("/api/v1/wiki/channels", json={"name": "VOC 위키"})

    assert response.status_code == 201
    channel_id = response.json()["id"]

    ok = client.patch(
        f"/api/v1/wiki/channels/{channel_id}", json={"name": "VOC"}
    )

    assert ok.status_code == 200
    assert ok.json()["name"] == "VOC"


def test_duplicate_channel_name_conflicts(
    client: TestClient, member: User
) -> None:
    """같은 workspace에 같은 이름은 409다."""
    name = f"VOC-{uuid.uuid4().hex[:8]}"
    client.post("/api/v1/wiki/channels", json={"name": name})

    dup = client.post("/api/v1/wiki/channels", json={"name": name})

    assert dup.status_code == 409
    assert dup.json()["detail"]["code"] == "CHANNEL_NAME_TAKEN"


def test_non_admin_cannot_manage_folders(
    client: TestClient, db: Session, member: User, workspace_ids: tuple[int, int]
) -> None:
    """남의 채널에는 폴더를 못 만든다 — 403 NOT_CHANNEL_ADMIN이다."""
    workspace_id, _ = workspace_ids
    other = _make_user(db, email=f"other-{uuid.uuid4().hex[:8]}@example.com")
    other_channel = _make_channel(
        db, workspace_id=workspace_id, created_by=other.id
    )
    db.add(ChannelAdmin(channel_id=other_channel, user_id=other.id))
    db.flush()

    denied = client.post(
        f"/api/v1/wiki/channels/{other_channel}/folders",
        json={"name": "미분류"},
    )

    assert denied.status_code == 403
    assert denied.json()["detail"]["code"] == "NOT_CHANNEL_ADMIN"


def test_folder_crud_by_admin(client: TestClient, member: User) -> None:
    """관리자는 폴더를 만들고 이름을 바꾸고 지운다."""
    channel_id = client.post(
        "/api/v1/wiki/channels", json={"name": f"CRUD-{uuid.uuid4().hex[:8]}"}
    ).json()["id"]

    created = client.post(
        f"/api/v1/wiki/channels/{channel_id}/folders",
        json={"name": "요구사항"},
    )
    assert created.status_code == 201
    folder_id = created.json()["id"]

    renamed = client.patch(
        f"/api/v1/wiki/channels/{channel_id}/folders/{folder_id}",
        json={"name": "요구"},
    )
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "요구"

    deleted = client.delete(
        f"/api/v1/wiki/channels/{channel_id}/folders/{folder_id}"
    )
    assert deleted.status_code == 204


# ======================= depth·정합 =======================


def test_folder_cannot_nest_under_folder(
    client: TestClient, member: User
) -> None:
    """폴더는 채널 바로 아래 한 겹뿐이라 상위 폴더 지정이 거부된다."""
    channel_id = client.post(
        "/api/v1/wiki/channels", json={"name": f"깊이-{uuid.uuid4().hex[:8]}"}
    ).json()["id"]
    parent = client.post(
        f"/api/v1/wiki/channels/{channel_id}/folders", json={"name": "상위"}
    ).json()["id"]

    nested = client.post(
        f"/api/v1/wiki/channels/{channel_id}/folders",
        json={"name": "하위", "parent_folder_id": parent},
    )

    assert nested.status_code == 422
    # 저장 모델에도 상위 폴더 자리가 없다 — depth 1은 구조의 약속이다.
    assert "parent_id" not in ChannelFolder.__table__.columns
    assert "parent_folder_id" not in ChannelFolder.__table__.columns


def test_folder_of_other_channel_is_not_found(
    client: TestClient, member: User
) -> None:
    """경로의 채널과 폴더가 어긋나면 404다 — 남의 폴더를 지울 수 없다."""
    first = client.post(
        "/api/v1/wiki/channels", json={"name": f"A-{uuid.uuid4().hex[:8]}"}
    ).json()["id"]
    second = client.post(
        "/api/v1/wiki/channels", json={"name": f"B-{uuid.uuid4().hex[:8]}"}
    ).json()["id"]
    folder_id = client.post(
        f"/api/v1/wiki/channels/{second}/folders", json={"name": "요구사항"}
    ).json()["id"]

    mismatched = client.delete(
        f"/api/v1/wiki/channels/{first}/folders/{folder_id}"
    )

    assert mismatched.status_code == 404
    assert mismatched.json()["detail"]["code"] == "FOLDER_NOT_FOUND"


def test_folder_with_documents_cannot_be_deleted(
    client: TestClient,
    db: Session,
    member: User,
    workspace_ids: tuple[int, int],
) -> None:
    """문서가 든 폴더 삭제는 409다 — RESTRICT가 500으로 새지 않는다."""
    workspace_id, _ = workspace_ids
    channel_id = client.post(
        "/api/v1/wiki/channels", json={"name": f"보관-{uuid.uuid4().hex[:8]}"}
    ).json()["id"]
    folder_id = client.post(
        f"/api/v1/wiki/channels/{channel_id}/folders", json={"name": "요구사항"}
    ).json()["id"]
    _make_artifact(
        db,
        workspace_id=workspace_id,
        channel_id=uuid.UUID(channel_id),
        folder_id=uuid.UUID(folder_id),
    )
    db.commit()

    denied = client.delete(
        f"/api/v1/wiki/channels/{channel_id}/folders/{folder_id}"
    )

    assert denied.status_code == 409
    assert denied.json()["detail"]["code"] == "FOLDER_NOT_EMPTY"
    # 폴더는 그대로 남는다 — 거부된 삭제가 절반만 반영되지 않는다.
    assert (
        db.scalar(
            select(ChannelFolder).where(
                ChannelFolder.id == uuid.UUID(folder_id)
            )
        )
        is not None
    )


def test_duplicate_folder_name_conflicts(
    client: TestClient, member: User
) -> None:
    """한 채널 안에서 폴더 이름은 겹칠 수 없다."""
    channel_id = client.post(
        "/api/v1/wiki/channels", json={"name": f"F-{uuid.uuid4().hex[:8]}"}
    ).json()["id"]
    client.post(
        f"/api/v1/wiki/channels/{channel_id}/folders", json={"name": "요구사항"}
    )

    dup = client.post(
        f"/api/v1/wiki/channels/{channel_id}/folders", json={"name": "요구사항"}
    )

    assert dup.status_code == 409
    assert dup.json()["detail"]["code"] == "FOLDER_NAME_TAKEN"


# ======================= 조회·경계 =======================


def test_channel_list_carries_folders_and_document_count(
    client: TestClient, db: Session, member: User, workspace_ids: tuple[int, int]
) -> None:
    """목록은 폴더·문서 수·관리자 여부를 함께 싣는다."""
    workspace_id, _ = workspace_ids
    name = f"목록-{uuid.uuid4().hex[:8]}"
    channel_id = client.post(
        "/api/v1/wiki/channels", json={"name": name}
    ).json()["id"]
    client.post(
        f"/api/v1/wiki/channels/{channel_id}/folders", json={"name": "요구사항"}
    )
    _make_artifact(
        db, workspace_id=workspace_id, channel_id=uuid.UUID(channel_id)
    )
    db.commit()

    listed = client.get("/api/v1/wiki/channels")

    assert listed.status_code == 200
    mine = [
        item for item in listed.json()["channels"] if item["id"] == channel_id
    ]
    assert len(mine) == 1
    assert mine[0]["name"] == name
    assert mine[0]["is_admin"] is True
    assert mine[0]["document_count"] == 1
    assert [folder["name"] for folder in mine[0]["folders"]] == ["요구사항"]


def test_channel_of_other_workspace_is_not_found(
    client: TestClient, db: Session, member: User, workspace_ids: tuple[int, int]
) -> None:
    """다른 workspace의 채널은 없는 것으로 답한다."""
    _, other_workspace_id = workspace_ids
    outsider = _make_user(
        db, email=f"outsider-{uuid.uuid4().hex[:8]}@example.com"
    )
    foreign = _make_channel(
        db, workspace_id=other_workspace_id, created_by=outsider.id
    )
    db.flush()

    response = client.patch(
        f"/api/v1/wiki/channels/{foreign}", json={"name": "탈취"}
    )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "CHANNEL_NOT_FOUND"


def test_non_member_cannot_reach_the_surface(
    client: TestClient, db: Session, as_user: Callable[[User], None]
) -> None:
    """어느 workspace에도 속하지 않으면 표면에 서지 못한다."""
    stranger = _make_user(
        db, email=f"stranger-{uuid.uuid4().hex[:8]}@example.com"
    )
    as_user(stranger)

    response = client.get("/api/v1/wiki/channels")

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "NOT_MEMBER"


def test_channels_require_authentication(client: TestClient) -> None:
    """쿠키가 없으면 401이고 오류 모양은 다른 응답과 같다."""
    response = client.get("/api/v1/wiki/channels")

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "UNAUTHENTICATED"
