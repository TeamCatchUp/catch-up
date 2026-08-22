"""문서 목록 조회와 폴더 이동 endpoint를 실 PostgreSQL로 확인한다.

목록 한 줄은 상태·담당자·즐겨찾기를 함께 싣는다. 셋을 따로 물어보게 하면
화면이 한 줄을 그리는 데 세 번을 왕복하고, 그 사이에 값이 갈린다.

폴더 이동은 같은 채널 안에서만 성립한다. 다른 채널의 폴더(422)와 없는
폴더(404)를 코드로 가르는 것이 이 파일이 지키는 계약이다.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from collections.abc import Iterator
from datetime import datetime
from datetime import timedelta
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
from catchup.db.models import ArtifactOwner
from catchup.db.models import Channel
from catchup.db.models import ChannelAdmin
from catchup.db.models import ChannelFolder
from catchup.db.models import KnowledgeArtifact
from catchup.db.models import KnowledgeArtifactChangeProposal
from catchup.db.models import KnowledgeArtifactRevision
from catchup.db.models import KnowledgeNode
from catchup.db.models import User
from catchup.db.models import UserRole
from catchup.db.models import UserStatus
from catchup.db.models import UserWorkspace
from catchup.db.models import WikiArtifactFavorite
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
        name=f"목록-{uuid.uuid4().hex[:8]}",
        company_id=company_id,
    )
    db.add(workspace)
    db.flush()
    return workspace.id


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


# ======================= 문서·채널 헬퍼 =======================


def _make_channel(
    db: Session, *, workspace_id: int, admin: User
) -> uuid.UUID:
    """채널 하나를 만든다. admin을 그 채널의 관리자로 세운다."""
    channel_id = uuid.uuid4()
    db.add(
        Channel(
            id=channel_id,
            workspace_id=workspace_id,
            name=f"채널-{uuid.uuid4().hex[:8]}",
            created_by=admin.id,
        )
    )
    db.add(ChannelAdmin(channel_id=channel_id, user_id=admin.id))
    db.flush()
    return channel_id


def _make_folder(
    db: Session, *, workspace_id: int, channel_id: uuid.UUID
) -> uuid.UUID:
    """그 채널 아래 폴더 하나를 만든다."""
    folder_id = uuid.uuid4()
    db.add(
        ChannelFolder(
            id=folder_id,
            workspace_id=workspace_id,
            channel_id=channel_id,
            name=f"폴더-{uuid.uuid4().hex[:8]}",
        )
    )
    db.flush()
    return folder_id


def _make_artifact(
    db: Session,
    *,
    workspace_id: int,
    title: str,
    channel_id: uuid.UUID | None = None,
    kind: str = "entity_summary",
) -> uuid.UUID:
    """문서 한 편을 만든다. 주제 노드도 같이 만든다."""
    node_id = uuid.uuid4()
    db.add(
        KnowledgeNode(
            id=node_id,
            workspace_id=workspace_id,
            node_kind="entity",
            entity_type="feature",
            canonical_key=f"test:list:{uuid.uuid4().hex}",
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
            kind=kind,
            channel_id=channel_id,
            subject_node_id=node_id,
            title=title,
        )
    )
    db.flush()
    return artifact_id


def _add_pending_proposal(
    db: Session, *, workspace_id: int, artifact_id: uuid.UUID
) -> None:
    """그 문서에 계류 중인 변경안 한 건을 심는다."""
    db.add(
        KnowledgeArtifactChangeProposal(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            artifact_id=artifact_id,
            blocks=[],
            status="pending",
            content_hash=uuid.uuid4().hex,
            idempotency_key=uuid.uuid4().hex,
        )
    )
    db.flush()


def _publish(
    db: Session,
    *,
    workspace_id: int,
    artifact_id: uuid.UUID,
    reviewer: str = "test",
    reviewed_at: datetime = datetime(2026, 8, 15, tzinfo=timezone.utc),
    revision_number: int = 1,
) -> uuid.UUID:
    """그 문서를 한 판 발행해 판 id를 돌려준다."""
    proposal_id = uuid.uuid4()
    db.add(
        KnowledgeArtifactChangeProposal(
            id=proposal_id,
            workspace_id=workspace_id,
            artifact_id=artifact_id,
            blocks=[],
            status="approved",
            content_hash=uuid.uuid4().hex,
            idempotency_key=uuid.uuid4().hex,
            reviewer=reviewer,
            reviewed_at=reviewed_at,
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
            blocks=[],
            source_proposal_id=proposal_id,
        )
    )
    db.flush()
    return revision_id


@pytest.fixture
def two_artifacts(
    db: Session, workspace_id: int, member: User
) -> tuple[uuid.UUID, uuid.UUID]:
    """계류 제안이 붙은 A와 발행된 B를 만든다. A에 담당자, B에 즐겨찾기."""
    a_id = _make_artifact(db, workspace_id=workspace_id, title="A")
    b_id = _make_artifact(db, workspace_id=workspace_id, title="B")
    _add_pending_proposal(db, workspace_id=workspace_id, artifact_id=a_id)
    _publish(db, workspace_id=workspace_id, artifact_id=b_id)
    db.add(ArtifactOwner(artifact_id=a_id, user_id=member.id))
    db.add(
        WikiArtifactFavorite(
            user_id=member.id, artifact_id=b_id, workspace_id=workspace_id
        )
    )
    db.flush()
    return a_id, b_id


# ======================= 목록 =======================


def test_list_artifacts_returns_status_owners_favorite(
    client, member, db, workspace_id, two_artifacts
):
    """목록 한 줄에 상태·최신 판·담당자·즐겨찾기가 함께 실린다."""
    response = client.get("/api/v1/wiki/artifacts")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert body["limit"] == 50
    assert body["offset"] == 0
    items = {item["title"]: item for item in body["items"]}
    assert items["A"]["status"] == "pending_review"
    assert items["A"]["pending_proposal_count"] == 1
    assert items["A"]["latest_revision"] is None
    assert items["B"]["status"] == "published"
    assert items["B"]["latest_revision"]["revision_number"] == 1
    assert items["A"]["owners"][0]["display_name"] == member.name
    assert items["B"]["owners"] == []
    assert items["B"]["is_favorite"] is True
    assert items["A"]["is_favorite"] is False


def test_list_artifacts_shows_last_editor(client, member, db, workspace_id):
    """최신 발행판을 승인한 사람과 그 시각이 목록 줄에 실린다.

    승인자는 사람이 읽을 이름과 사진까지 함께 실어야 한다. 화면이 id만
    받으면 줄마다 사용자 조회를 한 번씩 더 해야 한다.
    """
    artifact_id = _make_artifact(db, workspace_id=workspace_id, title="편집됨")
    _publish(
        db,
        workspace_id=workspace_id,
        artifact_id=artifact_id,
        reviewer=f"user:{member.id}",
        reviewed_at=datetime(2026, 8, 20, tzinfo=timezone.utc),
    )

    body = client.get("/api/v1/wiki/artifacts").json()
    item = {row["title"]: row for row in body["items"]}["편집됨"]

    assert item["last_edited_by"]["user_id"] == member.id
    assert item["last_edited_by"]["display_name"] == member.name
    assert item["last_edited_at"].startswith("2026-08-20")


def test_list_artifacts_without_revision_has_no_last_editor(
    client, member, db, workspace_id
):
    """발행판이 없는 문서는 최종 편집자도 시각도 없다."""
    _make_artifact(db, workspace_id=workspace_id, title="판없음")

    body = client.get("/api/v1/wiki/artifacts").json()
    item = {row["title"]: row for row in body["items"]}["판없음"]

    assert item["last_edited_by"] is None
    assert item["last_edited_at"] is None


def test_list_artifacts_debug_reviewer_has_no_last_editor(
    client, member, db, workspace_id
):
    """승인자가 사용자로 이어지지 않으면 사람은 비우고 시각만 싣는다."""
    artifact_id = _make_artifact(db, workspace_id=workspace_id, title="디버그")
    _publish(
        db,
        workspace_id=workspace_id,
        artifact_id=artifact_id,
        reviewer="debug:test-user",
    )

    body = client.get("/api/v1/wiki/artifacts").json()
    item = {row["title"]: row for row in body["items"]}["디버그"]

    assert item["last_edited_by"] is None
    assert item["last_edited_at"].startswith("2026-08-15")


def test_list_artifacts_last_editor_follows_newest_revision(
    client, member, db, workspace_id
):
    """다시 발행하면 최종 편집자가 새 판의 승인자로 바뀐다."""
    other = _make_user(db, prefix="editor")
    _join(db, user=other, workspace_id=workspace_id)
    artifact_id = _make_artifact(db, workspace_id=workspace_id, title="재발행")
    _publish(
        db,
        workspace_id=workspace_id,
        artifact_id=artifact_id,
        reviewer=f"user:{member.id}",
    )
    _publish(
        db,
        workspace_id=workspace_id,
        artifact_id=artifact_id,
        reviewer=f"user:{other.id}",
        reviewed_at=datetime(2026, 8, 21, tzinfo=timezone.utc),
        revision_number=2,
    )

    body = client.get("/api/v1/wiki/artifacts").json()
    item = {row["title"]: row for row in body["items"]}["재발행"]

    assert item["last_edited_by"]["user_id"] == other.id
    assert item["last_edited_at"].startswith("2026-08-21")


def test_list_artifacts_status_filter_and_pagination(
    client, member, db, workspace_id, two_artifacts
):
    """상태 필터는 전체 수까지 좁히고, limit·offset은 한 쪽만 돌려준다."""
    filtered = client.get("/api/v1/wiki/artifacts?status=published")

    assert filtered.status_code == 200
    assert filtered.json()["total"] == 1
    assert filtered.json()["items"][0]["title"] == "B"

    paged = client.get("/api/v1/wiki/artifacts?limit=1&offset=1")

    assert paged.status_code == 200
    assert paged.json()["total"] == 2
    assert len(paged.json()["items"]) == 1


def test_list_artifacts_rejects_unknown_status(client, member):
    """모르는 상태 값은 422다."""
    response = client.get("/api/v1/wiki/artifacts?status=whatever")

    assert response.status_code == 422


def test_list_artifacts_hides_other_workspace(
    client, member, db, workspace_id, company_id
):
    """다른 workspace의 문서는 목록에 실리지 않는다."""
    other = Workspace(name=f"남의-{uuid.uuid4().hex[:8]}", company_id=company_id)
    db.add(other)
    db.flush()
    _make_artifact(db, workspace_id=other.id, title="남의 문서")

    response = client.get("/api/v1/wiki/artifacts")

    assert response.json()["total"] == 0


# ======================= 폴더 이동 =======================


@pytest.fixture
def channel_id(db: Session, workspace_id: int, member: User) -> uuid.UUID:
    """member가 관리자인 채널 하나를 만든다."""
    return _make_channel(db, workspace_id=workspace_id, admin=member)


def test_move_artifact_to_folder_and_back(
    client, member, db, workspace_id, channel_id
):
    """관리자는 문서를 같은 채널의 폴더로 옮기고 다시 루트로 올린다."""
    artifact_id = _make_artifact(
        db, workspace_id=workspace_id, title="옮길 문서", channel_id=channel_id
    )
    folder_id = _make_folder(
        db, workspace_id=workspace_id, channel_id=channel_id
    )

    moved = client.patch(
        f"/api/v1/wiki/artifacts/{artifact_id}",
        json={"folder_id": str(folder_id)},
    )

    assert moved.status_code == 200
    assert moved.json()["folder_id"] == str(folder_id)
    assert moved.json()["channel_id"] == str(channel_id)

    back = client.patch(
        f"/api/v1/wiki/artifacts/{artifact_id}", json={"folder_id": None}
    )

    assert back.status_code == 200
    assert back.json()["folder_id"] is None


def test_move_artifact_without_folder_id_key_is_422(
    client, member, db, workspace_id, channel_id
):
    """folder_id 키를 빠뜨린 요청은 루트 이동으로 읽지 않고 거절한다.

    값이 null인 것과 키가 없는 것은 다른 뜻이다. 키가 없으면 무엇을 원하는지
    적히지 않은 요청이므로, 기본값으로 채워 문서를 옮기지 않는다.
    """
    artifact_id = _make_artifact(
        db,
        workspace_id=workspace_id,
        title="빈 요청 문서",
        channel_id=channel_id,
    )

    response = client.patch(f"/api/v1/wiki/artifacts/{artifact_id}", json={})

    assert response.status_code == 422


def test_move_artifact_to_other_channel_folder_is_mismatch(
    client, member, db, workspace_id, channel_id
):
    """다른 채널의 폴더로 옮기려 하면 422다."""
    artifact_id = _make_artifact(
        db, workspace_id=workspace_id, title="옮길 문서", channel_id=channel_id
    )
    other_channel = _make_channel(
        db, workspace_id=workspace_id, admin=member
    )
    other_folder = _make_folder(
        db, workspace_id=workspace_id, channel_id=other_channel
    )

    response = client.patch(
        f"/api/v1/wiki/artifacts/{artifact_id}",
        json={"folder_id": str(other_folder)},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "FOLDER_CHANNEL_MISMATCH"


def test_move_artifact_to_unknown_folder_is_not_found(
    client, member, db, workspace_id, channel_id
):
    """없는 폴더로 옮기려 하면 404다."""
    artifact_id = _make_artifact(
        db, workspace_id=workspace_id, title="옮길 문서", channel_id=channel_id
    )

    response = client.patch(
        f"/api/v1/wiki/artifacts/{artifact_id}",
        json={"folder_id": str(uuid.uuid4())},
    )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "FOLDER_NOT_FOUND"


def test_move_unclassified_artifact_into_folder_is_mismatch(
    client, member, db, workspace_id, channel_id, as_user
):
    """채널에 놓이지 않은 문서는 폴더에 넣을 수 없다.

    미분류 문서의 관리자는 전역 ADMIN이라, 그 자격을 가진 사람으로 선다.
    """
    artifact_id = _make_artifact(
        db, workspace_id=workspace_id, title="미분류 문서"
    )
    folder_id = _make_folder(
        db, workspace_id=workspace_id, channel_id=channel_id
    )
    global_admin = _make_user(db, prefix="global", role=UserRole.ADMIN)
    _join(db, user=global_admin, workspace_id=workspace_id)
    as_user(global_admin)

    response = client.patch(
        f"/api/v1/wiki/artifacts/{artifact_id}",
        json={"folder_id": str(folder_id)},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "FOLDER_CHANNEL_MISMATCH"


def test_move_artifact_without_role_is_forbidden(
    client, db, workspace_id, channel_id, as_user: Callable[[User], None]
):
    """관리자도 담당자도 아닌 구성원은 문서를 옮기지 못한다."""
    artifact_id = _make_artifact(
        db, workspace_id=workspace_id, title="옮길 문서", channel_id=channel_id
    )
    folder_id = _make_folder(
        db, workspace_id=workspace_id, channel_id=channel_id
    )
    stranger = _make_user(db, prefix="stranger")
    _join(db, user=stranger, workspace_id=workspace_id)
    as_user(stranger)

    response = client.patch(
        f"/api/v1/wiki/artifacts/{artifact_id}",
        json={"folder_id": str(folder_id)},
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "NOT_DOCUMENT_REVIEWER"


def test_move_artifact_by_owner_is_allowed(
    client, db, workspace_id, channel_id, as_user: Callable[[User], None]
):
    """담당자는 자기 문서를 옮길 수 있다."""
    artifact_id = _make_artifact(
        db, workspace_id=workspace_id, title="옮길 문서", channel_id=channel_id
    )
    folder_id = _make_folder(
        db, workspace_id=workspace_id, channel_id=channel_id
    )
    owner = _make_user(db, prefix="owner")
    _join(db, user=owner, workspace_id=workspace_id)
    db.add(ArtifactOwner(artifact_id=artifact_id, user_id=owner.id))
    db.flush()
    as_user(owner)

    response = client.patch(
        f"/api/v1/wiki/artifacts/{artifact_id}",
        json={"folder_id": str(folder_id)},
    )

    assert response.status_code == 200
    assert response.json()["folder_id"] == str(folder_id)


def test_move_artifact_rejects_unknown_body_key(
    client, member, db, workspace_id, channel_id
):
    """모르는 필드를 실은 요청은 422다."""
    artifact_id = _make_artifact(
        db, workspace_id=workspace_id, title="옮길 문서", channel_id=channel_id
    )

    response = client.patch(
        f"/api/v1/wiki/artifacts/{artifact_id}",
        json={"folder_id": None, "channel_id": str(channel_id)},
    )

    assert response.status_code == 422


def test_move_unknown_artifact_is_four_hundred_four(client, member):
    """없는 문서를 옮기려 하면 404다."""
    response = client.patch(
        f"/api/v1/wiki/artifacts/{uuid.uuid4()}", json={"folder_id": None}
    )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "ARTIFACT_NOT_FOUND"


# ======================= 대시보드 필터·정렬 =======================


def _titles(response) -> list[str]:
    """응답에 실린 문서 제목을 순서 그대로 뽑는다."""
    return [item["title"] for item in response.json()["items"]]


def test_list_artifacts_unassigned_filter(
    client, member, db, workspace_id, two_artifacts
):
    """unassigned=true는 담당자가 아무도 없는 문서만 남긴다."""
    response = client.get("/api/v1/wiki/artifacts?unassigned=true")

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert _titles(response) == ["B"]


def test_list_artifacts_rejects_unassigned_with_owner(
    client, member, db, workspace_id, two_artifacts
):
    """담당자 지정 필터와 미지정 필터를 함께 주면 422다.

    둘은 서로 반대라 겹치는 결과가 없다. 빈 목록을 돌려주면 소비자는
    자기 요청이 잘못된 것인지 정말 문서가 없는 것인지 가릴 수 없다.
    """
    response = client.get(
        f"/api/v1/wiki/artifacts?unassigned=true&owner_user_id={member.id}"
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "CONFLICTING_OWNER_FILTERS"


def test_list_artifacts_owner_filter_accepts_single_value(
    client, member, db, workspace_id, two_artifacts
):
    """owner_user_id를 하나만 주면 그 사람이 담당자인 문서만 남는다."""
    response = client.get(
        f"/api/v1/wiki/artifacts?owner_user_id={member.id}"
    )

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert _titles(response) == ["A"]


def test_list_artifacts_owner_filter_accepts_multiple_values(
    client, member, db, workspace_id, two_artifacts
):
    """owner_user_id를 여러 번 주면 그중 한 명이라도 담당자인 문서를 모두 남긴다."""
    other = _make_user(db, prefix="other")
    _join(db, user=other, workspace_id=workspace_id)
    c_id = _make_artifact(db, workspace_id=workspace_id, title="C")
    db.add(ArtifactOwner(artifact_id=c_id, user_id=other.id))
    db.flush()

    response = client.get(
        "/api/v1/wiki/artifacts"
        f"?owner_user_id={member.id}&owner_user_id={other.id}"
    )

    assert response.status_code == 200
    assert response.json()["total"] == 2
    assert sorted(_titles(response)) == ["A", "C"]


def test_list_artifacts_owner_filter_counts_shared_artifact_once(
    client, member, db, workspace_id, two_artifacts
):
    """담당자가 둘인 문서도 한 줄로만 실리고 total도 그 수와 맞는다."""
    other = _make_user(db, prefix="second-owner")
    _join(db, user=other, workspace_id=workspace_id)
    a_id, _ = two_artifacts
    db.add(ArtifactOwner(artifact_id=a_id, user_id=other.id))
    db.flush()

    response = client.get(
        "/api/v1/wiki/artifacts"
        f"?owner_user_id={member.id}&owner_user_id={other.id}"
    )

    assert response.status_code == 200
    body = response.json()
    assert _titles(response) == ["A"]
    assert body["total"] == 1
    assert len(body["items"]) == 1


def test_list_artifacts_rejects_unassigned_with_multiple_owners(
    client, member, db, workspace_id, two_artifacts
):
    """담당자를 여러 명 주면서 미지정 필터까지 켜도 422다."""
    other = _make_user(db, prefix="conflict-owner")
    _join(db, user=other, workspace_id=workspace_id)

    response = client.get(
        "/api/v1/wiki/artifacts?unassigned=true"
        f"&owner_user_id={member.id}&owner_user_id={other.id}"
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "CONFLICTING_OWNER_FILTERS"


def test_list_artifacts_searches_title(
    client, member, db, workspace_id, two_artifacts
):
    """q는 제목 부분일치로 거르고, 공백뿐이면 거르지 않는다."""
    _make_artifact(db, workspace_id=workspace_id, title="결제 오류")
    db.flush()

    hit = client.get("/api/v1/wiki/artifacts?q=오류")

    assert hit.status_code == 200
    assert _titles(hit) == ["결제 오류"]

    blank = client.get("/api/v1/wiki/artifacts?q=%20%20")

    assert blank.json()["total"] == 3


def test_list_artifacts_sorts_by_created_at_ascending(
    client, member, db, workspace_id
):
    """sort·order를 주면 그 키와 방향으로 정렬한다."""
    base = datetime(2026, 3, 1, tzinfo=timezone.utc)
    for index, title in enumerate(("첫째", "둘째", "셋째")):
        artifact_id = _make_artifact(
            db, workspace_id=workspace_id, title=title
        )
        db.get(KnowledgeArtifact, artifact_id).created_at = base + timedelta(
            days=index
        )
    db.flush()

    response = client.get("/api/v1/wiki/artifacts?sort=created_at&order=asc")

    assert response.status_code == 200
    assert _titles(response) == ["첫째", "둘째", "셋째"]


def test_list_artifacts_rejects_unknown_sort(client, member):
    """모르는 정렬 키는 422다."""
    response = client.get("/api/v1/wiki/artifacts?sort=title")

    assert response.status_code == 422


def test_list_artifacts_carries_last_activity_at(
    client, member, db, workspace_id
):
    """마지막 활동 시각은 항상 실리고, 활동이 없으면 생성 시각과 같다."""
    base = datetime(2026, 4, 1, tzinfo=timezone.utc)
    quiet_id = _make_artifact(db, workspace_id=workspace_id, title="조용함")
    db.get(KnowledgeArtifact, quiet_id).created_at = base
    busy_id = _make_artifact(db, workspace_id=workspace_id, title="바쁨")
    db.get(KnowledgeArtifact, busy_id).created_at = base
    _add_pending_proposal(db, workspace_id=workspace_id, artifact_id=busy_id)
    db.flush()

    response = client.get("/api/v1/wiki/artifacts")

    assert response.status_code == 200
    items = {item["title"]: item for item in response.json()["items"]}
    assert items["조용함"]["last_activity_at"] == items["조용함"]["created_at"]
    assert items["바쁨"]["last_activity_at"] > items["바쁨"]["created_at"]
    # 활동이 늦은 문서가 기본 정렬에서 앞선다.
    assert _titles(response) == ["바쁨", "조용함"]
