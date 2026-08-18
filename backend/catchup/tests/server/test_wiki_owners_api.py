"""담당자 지정·해제 API의 인가·멱등·오류 계약을 확인한다.

권한 판정은 실 PostgreSQL로 본다. 소속(user_workspaces)·채널 관리자
(channel_admins)·담당자(artifact_owners)가 모두 DB 사실이고, 판정이
"어느 행이 있느냐"로만 갈리기 때문이다. 인증만 dependency_overrides로
우회한다.

지정과 해제는 자격이 다르다는 것이 이 파일의 요점이다 — 지정은 관리자와
담당자 둘 다, 해제는 관리자만이다. 담당자 본인이 해제하지 못한다는 사실을
따로 못박는다. 순수 판정은 test_wiki_roles.py가 보므로, 여기서는 그
판정이 실제 행과 HTTP 응답으로 이어지는지를 본다.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from collections.abc import Iterator
from unittest.mock import patch

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

from catchup.audit.actions import KnowledgeReviewAction
from catchup.configs.config import settings
from catchup.db.dependencies import get_db
from catchup.db.models import ArtifactOwner
from catchup.db.models import Channel
from catchup.db.models import ChannelAdmin
from catchup.db.models import KnowledgeArtifact
from catchup.db.models import KnowledgeNode
from catchup.db.models import User
from catchup.db.models import UserRole
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

    if not inspect(engine).has_table(ArtifactOwner.__tablename__):
        engine.dispose()
        pytest.skip("역할 테이블이 없다. alembic upgrade head가 필요하다.")

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
def db(connection: Connection) -> Iterator[Session]:
    """같은 트랜잭션 위에 세션을 연다.

    핸들러가 db.commit()을 부르므로 savepoint로 참여시킨다.
    """
    session = sessionmaker(
        bind=connection,
        join_transaction_mode="create_savepoint",
        expire_on_commit=False,
    )()

    yield session

    session.close()


def _make_user(
    db: Session, *, prefix: str, role: UserRole = UserRole.USER
) -> User:
    """테스트용 사용자 한 명을 만든다."""
    user = User(
        email=f"{prefix}-{uuid.uuid4().hex[:8]}@example.com",
        name=f"구성원-{prefix}",
        picture=f"https://example.com/{prefix}.png",
        provider="keycloak",
        status=UserStatus.ACTIVE,
        role=role,
    )
    db.add(user)
    db.flush()
    return user


def _join(db: Session, *, user: User, workspace_id: int) -> None:
    """사용자를 workspace 구성원으로 넣는다."""
    db.add(UserWorkspace(user_id=user.id, workspace_id=workspace_id))
    db.flush()


def _make_channel(
    db: Session, *, workspace_id: int, created_by: int
) -> uuid.UUID:
    """채널 하나를 만든다. 관리자는 세우지 않는다."""
    channel_id = uuid.uuid4()
    db.add(
        Channel(
            id=channel_id,
            workspace_id=workspace_id,
            name=f"채널-{uuid.uuid4().hex[:8]}",
            created_by=created_by,
        )
    )
    db.flush()
    return channel_id


def _make_artifact(
    db: Session, *, workspace_id: int, channel_id: uuid.UUID | None
) -> uuid.UUID:
    """그 채널에 놓인 문서 한 편을 만든다. channel_id가 None이면 미분류다."""
    node_id = uuid.uuid4()
    db.add(
        KnowledgeNode(
            id=node_id,
            workspace_id=workspace_id,
            node_kind="entity",
            entity_type="feature",
            canonical_key=f"test:owners:{uuid.uuid4().hex}",
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
    """인증만 우회한다. 소속·역할 검사는 실 DB로 그대로 돈다."""

    def register(user: User) -> None:
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[get_reviewer_user] = lambda: user

    return register


@pytest.fixture
def workspace_id(workspace_ids: tuple[int, int]) -> int:
    return workspace_ids[0]


@pytest.fixture
def admin_user(db: Session, workspace_id: int) -> User:
    """채널 관리자 한 명을 세운다."""
    user = _make_user(db, prefix="admin")
    _join(db, user=user, workspace_id=workspace_id)
    return user


@pytest.fixture
def channel_id(db: Session, workspace_id: int, admin_user: User) -> uuid.UUID:
    """관리자가 admin_user 한 명인 채널을 만든다."""
    created = _make_channel(
        db, workspace_id=workspace_id, created_by=admin_user.id
    )
    db.add(ChannelAdmin(channel_id=created, user_id=admin_user.id))
    db.flush()
    return created


@pytest.fixture
def owner_user(
    db: Session, workspace_id: int, artifact_id: uuid.UUID
) -> User:
    """그 문서의 담당자 한 명을 세운다. 관리자는 아니다."""
    user = _make_user(db, prefix="owner")
    _join(db, user=user, workspace_id=workspace_id)
    db.add(ArtifactOwner(artifact_id=artifact_id, user_id=user.id))
    db.flush()
    return user


@pytest.fixture
def artifact_id(
    db: Session, workspace_id: int, channel_id: uuid.UUID
) -> uuid.UUID:
    """그 채널에 놓인 문서 한 편을 만든다."""
    return _make_artifact(
        db, workspace_id=workspace_id, channel_id=channel_id
    )


@pytest.fixture
def member_b(db: Session, workspace_id: int) -> User:
    """역할이 없는 같은 workspace 구성원 한 명을 세운다."""
    user = _make_user(db, prefix="member-b")
    _join(db, user=user, workspace_id=workspace_id)
    return user


@pytest.fixture
def outsider(db: Session) -> User:
    """어느 workspace에도 속하지 않은 사용자 한 명을 세운다."""
    return _make_user(db, prefix="outsider")


def _owner_path(artifact_id: uuid.UUID, user: User) -> str:
    return f"/api/v1/wiki/artifacts/{artifact_id}/owners/{user.id}"


def _owner_payload(user: User) -> dict[str, object]:
    """담당자 한 명이 응답에 실릴 모양을 만든다."""
    return {
        "user_id": user.id,
        "display_name": user.name,
        "profile_image_url": user.picture,
    }


def _owners_of(response_body: dict[str, object]) -> list[dict[str, object]]:
    """응답의 담당자 목록을 user_id 순으로 세운다."""
    owners = response_body["owners"]
    assert isinstance(owners, list)
    return sorted(owners, key=lambda owner: owner["user_id"])


# ======================= 브리프 케이스 =======================


def test_owner_assigns_co_owner(
    client: TestClient,
    as_user: Callable[[User], None],
    owner_user: User,
    artifact_id: uuid.UUID,
    member_b: User,
) -> None:
    """담당자는 공동 담당자를 붙일 수 있다."""
    as_user(owner_user)

    response = client.put(_owner_path(artifact_id, member_b))

    assert response.status_code == 201
    assert _owners_of(response.json()) == sorted(
        [_owner_payload(owner_user), _owner_payload(member_b)],
        key=lambda owner: owner["user_id"],
    )


def test_owner_cannot_remove_owner(
    client: TestClient,
    as_user: Callable[[User], None],
    db: Session,
    owner_user: User,
    artifact_id: uuid.UUID,
    member_b: User,
) -> None:
    """해제는 관리자만이다 — 담당자 본인이라도 거부된다."""
    db.add(ArtifactOwner(artifact_id=artifact_id, user_id=member_b.id))
    db.flush()
    as_user(owner_user)

    denied = client.delete(_owner_path(artifact_id, member_b))

    assert denied.status_code == 403
    assert denied.json()["detail"]["code"] == "NOT_OWNER_MANAGER"
    # 거부된 해제가 절반만 반영되지 않는다.
    assert db.get(ArtifactOwner, (artifact_id, member_b.id)) is not None


def test_channel_admin_removes_owner(
    client: TestClient,
    as_user: Callable[[User], None],
    db: Session,
    admin_user: User,
    artifact_id: uuid.UUID,
    member_b: User,
) -> None:
    """채널 관리자는 담당자를 뗀다."""
    db.add(ArtifactOwner(artifact_id=artifact_id, user_id=member_b.id))
    db.flush()
    as_user(admin_user)

    response = client.delete(_owner_path(artifact_id, member_b))

    assert response.status_code == 204
    assert db.get(ArtifactOwner, (artifact_id, member_b.id)) is None


def test_removing_owner_emits_audit_event(
    client: TestClient,
    as_user: Callable[[User], None],
    db: Session,
    admin_user: User,
    artifact_id: uuid.UUID,
    member_b: User,
) -> None:
    """명단이 줄어든 사실이 감사 스트림에 남는다.

    거부만 남으면 "책임자가 사라진 일"은 어디에도 기록되지 않는다.
    행위자와 뗀 대상이 따로 실려야 나중에 되짚을 수 있다.
    """
    db.add(ArtifactOwner(artifact_id=artifact_id, user_id=member_b.id))
    db.flush()
    as_user(admin_user)

    with patch("catchup.server.wiki.api.emit_audit_event") as emit:
        response = client.delete(_owner_path(artifact_id, member_b))

    assert response.status_code == 204
    emit.assert_called_once()
    metadata = emit.call_args.kwargs["metadata"]
    assert (
        emit.call_args.kwargs["action"]
        == KnowledgeReviewAction.OWNER_REMOVE
    )
    assert metadata.artifact_id == str(artifact_id)
    assert metadata.target_user_id == member_b.id
    assert metadata.user_id == admin_user.id


def test_removing_non_owner_emits_no_audit_event(
    client: TestClient,
    as_user: Callable[[User], None],
    admin_user: User,
    artifact_id: uuid.UUID,
    member_b: User,
) -> None:
    """담당자가 아니었으면 명단이 줄지 않아 감사 이벤트도 없다."""
    as_user(admin_user)

    with patch("catchup.server.wiki.api.emit_audit_event") as emit:
        response = client.delete(_owner_path(artifact_id, member_b))

    assert response.status_code == 204
    emit.assert_not_called()


def test_assigning_non_member_rejected(
    client: TestClient,
    as_user: Callable[[User], None],
    owner_user: User,
    artifact_id: uuid.UUID,
    outsider: User,
) -> None:
    """소속 밖 사용자를 담당자로 세우려 하면 400이다."""
    as_user(owner_user)

    denied = client.put(_owner_path(artifact_id, outsider))

    assert denied.status_code == 400
    assert denied.json()["detail"]["code"] == "USER_NOT_MEMBER"


# ======================= 멱등·경계 =======================


def test_assigning_twice_is_idempotent(
    client: TestClient,
    as_user: Callable[[User], None],
    owner_user: User,
    artifact_id: uuid.UUID,
    member_b: User,
) -> None:
    """이미 담당자면 200으로 답한다 — 두 번째 요청이 실패하지 않는다."""
    as_user(owner_user)
    path = _owner_path(artifact_id, member_b)
    assert client.put(path).status_code == 201

    again = client.put(path)

    assert again.status_code == 200
    assert _owners_of(again.json()) == sorted(
        [_owner_payload(owner_user), _owner_payload(member_b)],
        key=lambda owner: owner["user_id"],
    )


def test_admin_assigns_owner_even_when_owners_exist(
    client: TestClient,
    as_user: Callable[[User], None],
    admin_user: User,
    owner_user: User,
    artifact_id: uuid.UUID,
    member_b: User,
) -> None:
    """지정은 관리자 폴백이 아니다 — 담당자가 있어도 관리자가 선다.

    검수(can_decide_artifact)와 갈리는 지점이라 HTTP로도 못박는다.
    """
    as_user(admin_user)

    response = client.put(_owner_path(artifact_id, member_b))

    assert response.status_code == 201


def test_member_without_roles_cannot_assign(
    client: TestClient,
    as_user: Callable[[User], None],
    owner_user: User,
    artifact_id: uuid.UUID,
    member_b: User,
) -> None:
    """역할이 없는 구성원은 담당자를 지정하지 못한다."""
    as_user(member_b)

    denied = client.put(_owner_path(artifact_id, member_b))

    assert denied.status_code == 403
    assert denied.json()["detail"]["code"] == "NOT_OWNER_MANAGER"


def test_unassigned_artifact_falls_back_to_global_admin(
    client: TestClient,
    as_user: Callable[[User], None],
    db: Session,
    workspace_id: int,
    member_b: User,
) -> None:
    """미분류 문서의 담당자 관리는 전역 ADMIN이 맡는다."""
    unassigned = _make_artifact(
        db, workspace_id=workspace_id, channel_id=None
    )
    global_admin = _make_user(db, prefix="global", role=UserRole.ADMIN)
    _join(db, user=global_admin, workspace_id=workspace_id)
    as_user(global_admin)

    response = client.put(_owner_path(unassigned, member_b))

    assert response.status_code == 201


def test_artifact_of_other_workspace_is_not_found(
    client: TestClient,
    as_user: Callable[[User], None],
    db: Session,
    workspace_ids: tuple[int, int],
    member_b: User,
) -> None:
    """다른 workspace의 문서는 없는 것으로 답한다 — 403으로 가르지 않는다."""
    _, other_workspace_id = workspace_ids
    foreign = _make_artifact(
        db, workspace_id=other_workspace_id, channel_id=None
    )
    as_user(member_b)

    response = client.put(_owner_path(foreign, member_b))

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "ARTIFACT_NOT_FOUND"


def test_owners_require_authentication(client: TestClient) -> None:
    """쿠키가 없으면 401이고 오류 모양은 다른 응답과 같다."""
    response = client.put(f"/api/v1/wiki/artifacts/{uuid.uuid4()}/owners/1")

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "UNAUTHENTICATED"
