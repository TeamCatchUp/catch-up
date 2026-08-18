"""preset 온보딩 API가 네 가지를 한 트랜잭션으로 만드는지 확인한다.

채널·관리자·정의·어휘가 한 번에 생겨야 온보딩이 끝난 자리가 곧바로
쓸 수 있는 상태가 된다. 하나라도 따로 커밋되면 관리자가 없는 채널이나
정의 없는 채널이 남으므로, 실 PostgreSQL로 경계를 함께 본다.

workspace는 테스트 안에서 새로 만든다. 개발 DB의 기존 workspace를 빌리면
거기 이미 발행된 어휘가 seed와 겹쳐 첫 온보딩이 발행을 건너뛰고, 어휘
계보가 공유 상태에 따라 달라진다. 계보가 빈 자리에서 시작하므로 첫
발행은 항상 "v1"이다.
"""

from __future__ import annotations

import re
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
from sqlalchemy.exc import IntegrityError
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker

from catchup.configs.config import settings
from catchup.db import wiki as wiki_queries
from catchup.db.dependencies import get_db
from catchup.db.models import Channel
from catchup.db.models import ChannelFolder
from catchup.db.models import User
from catchup.db.models import UserStatus
from catchup.db.models import UserWorkspace
from catchup.db.models import Workspace
from catchup.knowledge_maintenance.adapters.llm.structured_extractor import CONTRACT_ID
from catchup.knowledge_maintenance.adapters.postgres.session_bound import (
    SessionBoundOntologyUnitOfWork,
)
from catchup.knowledge_maintenance.domain.artifact_definition import (
    deserialize_selection_spec,
)
from catchup.server.knowledge_review.dependencies import get_reviewer_user
from catchup.server.wiki.api import router

_ONBOARDING_PATH = "/api/v1/wiki/channels/onboarding"
_PUBLISHED_VERSION = re.compile(r"^v\d+$")

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
    """이 테스트만 쓰는 새 workspace를 만든다.

    개발 DB의 기존 workspace를 빌리면 그 workspace에 이미 발행된 어휘가
    seed와 겹쳐 첫 온보딩이 발행을 건너뛴다. 어휘 계보가 비어 있는 자리를
    새로 만들어 공유 상태에 기대지 않는다.
    """
    workspace = Workspace(
        name=f"온보딩-{uuid.uuid4().hex[:8]}",
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


def _published_versions(db: Session, workspace_id: int) -> list[str]:
    """이 workspace의 발행 어휘 버전 이름을 읽는다."""
    ontology = SessionBoundOntologyUnitOfWork(db).ontology
    versions = ontology.list_versions(
        workspace_id=workspace_id,
        ontology_id=CONTRACT_ID,
    )
    return [
        version for version in versions if _PUBLISHED_VERSION.match(version)
    ]


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


# ======================= 브리프 케이스 =======================


def test_creates_channel_admin_definition_and_vocabulary(
    client: TestClient,
    member: User,
    db: Session,
    workspace_id: int,
) -> None:
    """네 가지가 한 번에 만들어진다."""
    assert _published_versions(db, workspace_id) == []

    response = client.post(
        _ONBOARDING_PATH,
        json={
            "name": "VOC 현황",
            "domain_preset": "voc",
            "purpose_presets": ["voc.request_status_tracking"],
            "kinds": ["feature_request_status"],
            "style_preset": "style.report_summary",
        },
    )
    assert response.status_code == 201
    body = response.json()
    channel_id = uuid.UUID(body["channel"]["id"])

    channel = db.get(Channel, channel_id)
    assert wiki_queries.list_channel_purposes(db, channel_id=channel_id) == [
        "voc.request_status_tracking"
    ]
    assert channel.style_preset == "style.report_summary"
    assert wiki_queries.list_channel_admin_ids(db, channel_id) == [member.id]

    definitions = wiki_queries.list_definitions_by_channel(
        db, channel_id=channel_id
    )
    assert len(definitions) == 1
    assert deserialize_selection_spec(
        definitions[0].selection_spec
    ).entity_types == ("feature_request",)

    version = body["vocabulary_version"]
    assert _PUBLISHED_VERSION.match(version)
    assert version == "v1"
    assert _published_versions(db, workspace_id) == ["v1"]


def test_name_over_twenty_characters_is_rejected(
    client: TestClient, member: User
) -> None:
    """이름은 20자까지다."""
    response = client.post(
        _ONBOARDING_PATH,
        json={
            "name": "가" * 21,
            "domain_preset": "voc",
            "purpose_presets": ["voc.top_requests"],
            "kinds": ["feature_request_status"],
            "style_preset": "style.report_summary",
        },
    )
    assert response.status_code == 422


def test_unknown_purpose_is_unprocessable(
    client: TestClient, member: User
) -> None:
    """카탈로그에 없는 목적 id는 422다."""
    response = client.post(
        _ONBOARDING_PATH,
        json={
            "name": "잘못된 목적",
            "domain_preset": "voc",
            "purpose_presets": ["voc.churn_signals"],
            "kinds": ["feature_request_status"],
            "style_preset": "style.report_summary",
        },
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "UNKNOWN_PURPOSE"


def test_unknown_domain_is_unprocessable(
    client: TestClient, member: User
) -> None:
    """카탈로그에 없는 도메인 id는 422다."""
    response = client.post(
        _ONBOARDING_PATH,
        json={
            "name": "잘못된 도메인",
            "domain_preset": "nope",
            "purpose_presets": ["voc.top_requests"],
            "kinds": ["feature_request_status"],
            "style_preset": "style.report_summary",
        },
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "UNKNOWN_DOMAIN"


def test_purpose_of_another_domain_is_unprocessable(
    client: TestClient, member: User
) -> None:
    """고른 도메인에 속하지 않는 목적 id는 422다."""
    response = client.post(
        _ONBOARDING_PATH,
        json={
            "name": "도메인 밖 목적",
            "domain_preset": "product",
            "purpose_presets": ["voc.top_requests"],
            "kinds": ["request_priority_board"],
            "style_preset": "style.report_summary",
        },
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "UNKNOWN_PURPOSE"


def test_unknown_style_is_unprocessable(
    client: TestClient, member: User
) -> None:
    """카탈로그에 없는 문체 id는 422다."""
    response = client.post(
        _ONBOARDING_PATH,
        json={
            "name": "잘못된 문체",
            "domain_preset": "voc",
            "purpose_presets": ["voc.top_requests"],
            "kinds": ["feature_request_status"],
            "style_preset": "style.faq",
        },
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "UNKNOWN_STYLE"


def test_kind_from_another_domain_is_unprocessable(
    client: TestClient, member: User
) -> None:
    """고른 도메인에 없는 문서 종류는 422다."""
    response = client.post(
        _ONBOARDING_PATH,
        json={
            "name": "도메인 밖 kind",
            "domain_preset": "voc",
            "purpose_presets": ["voc.top_requests"],
            "kinds": ["request_priority_board"],
            "style_preset": "style.report_summary",
        },
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "UNKNOWN_KIND"


def test_duplicate_channel_name_is_four_hundred_nine(
    client: TestClient,
    member: User,
    db: Session,
    workspace_id: int,
) -> None:
    """같은 workspace에 같은 이름이 있으면 409다."""
    payload = {
        "name": "중복 이름",
        "domain_preset": "voc",
        "purpose_presets": ["voc.top_requests"],
        "kinds": ["feature_request_status"],
        "style_preset": "style.report_summary",
    }
    assert client.post(_ONBOARDING_PATH, json=payload).status_code == 201

    second = client.post(_ONBOARDING_PATH, json=payload)
    assert second.status_code == 409
    assert second.json()["detail"]["code"] == "CHANNEL_NAME_TAKEN"


def test_definition_failure_rolls_back_the_channel(
    client: TestClient,
    member: User,
    db: Session,
    workspace_id: int,
) -> None:
    """정의 INSERT가 실패하면 채널도 남지 않는다."""
    before = len(wiki_queries.list_channels(db, workspace_id))
    with patch(
        "catchup.server.wiki.api.wiki_queries.add_artifact_definition",
        side_effect=IntegrityError("boom", None, Exception()),
    ):
        with pytest.raises(IntegrityError):
            client.post(
                _ONBOARDING_PATH,
                json={
                    "name": "롤백 확인",
                    "domain_preset": "voc",
                    "purpose_presets": ["voc.top_requests"],
                    "kinds": ["feature_request_status"],
                    "style_preset": "style.report_summary",
                },
            )
    db.rollback()
    assert len(wiki_queries.list_channels(db, workspace_id)) == before


def test_second_onboarding_in_the_same_domain_reuses_vocabulary(
    client: TestClient, member: User
) -> None:
    """같은 도메인으로 두 번째 채널을 만들면 어휘를 다시 발행하지 않는다."""
    first = client.post(
        _ONBOARDING_PATH,
        json={
            "name": "첫 위키",
            "domain_preset": "voc",
            "purpose_presets": ["voc.top_requests"],
            "kinds": ["feature_request_status"],
            "style_preset": "style.report_summary",
        },
    )
    second = client.post(
        _ONBOARDING_PATH,
        json={
            "name": "둘째 위키",
            "domain_preset": "voc",
            "purpose_presets": ["voc.complaint_patterns"],
            "kinds": ["complaint_topic_brief"],
            "style_preset": "style.support_guide",
        },
    )
    assert first.json()["vocabulary_version"] == "v1"
    assert second.json()["vocabulary_version"] is None


def test_requires_workspace_membership(
    client: TestClient, outsider: User
) -> None:
    """소속이 없으면 403이다."""
    response = client.post(
        _ONBOARDING_PATH,
        json={
            "name": "남의 workspace",
            "domain_preset": "voc",
            "purpose_presets": ["voc.top_requests"],
            "kinds": ["feature_request_status"],
            "style_preset": "style.report_summary",
        },
    )
    assert response.status_code == 403


def test_onboarding_creates_definition_and_folder_per_kind(
    client: TestClient,
    member: User,
    db: Session,
    workspace_id: int,
) -> None:
    """kind마다 정의 하나와 kind 라벨 이름의 폴더 하나가 생기고 정의가 그 폴더를 가리킨다."""
    response = client.post(
        _ONBOARDING_PATH,
        json={
            "name": "VOC",
            "domain_preset": "voc",
            "purpose_presets": ["voc.top_requests", "voc.faq_consistency"],
            "kinds": ["feature_request_status", "faq_answer"],
            "style_preset": "style.wiki_standard",
        },
    )
    assert response.status_code == 201, response.json()
    body = response.json()
    channel_id = uuid.UUID(body["channel"]["id"])
    assert body["purpose_presets"] == [
        "voc.top_requests",
        "voc.faq_consistency",
    ]
    kinds = {item["kind"]: item for item in body["definitions"]}
    assert set(kinds) == {"feature_request_status", "faq_answer"}
    folders = {
        folder.name: folder
        for folder in wiki_queries.list_folders(db, workspace_id)
        if folder.channel_id == channel_id
    }
    assert set(folders) == {"기능 요청 문서", "자주 묻는 질문 문서"}
    assert kinds["feature_request_status"]["folder_id"] == str(
        folders["기능 요청 문서"].id
    )
    assert kinds["feature_request_status"]["purpose_presets"] == [
        "voc.top_requests"
    ]
    assert kinds["faq_answer"]["purpose_presets"] == ["voc.faq_consistency"]
    assert wiki_queries.list_channel_purposes(db, channel_id=channel_id) == [
        "voc.top_requests",
        "voc.faq_consistency",
    ]


def test_onboarding_rejects_unknown_kind_and_empty_lists(
    client: TestClient, member: User
) -> None:
    """모르는 kind와 빈 목록은 둘 다 422다."""
    unknown_kind = client.post(
        _ONBOARDING_PATH,
        json={
            "name": "x",
            "domain_preset": "voc",
            "purpose_presets": ["voc.top_requests"],
            "kinds": ["nope"],
            "style_preset": "style.wiki_standard",
        },
    )
    assert (
        unknown_kind.status_code,
        unknown_kind.json()["detail"]["code"],
    ) == (422, "UNKNOWN_KIND")

    empty_purposes = client.post(
        _ONBOARDING_PATH,
        json={
            "name": "x",
            "domain_preset": "voc",
            "purpose_presets": [],
            "kinds": ["feature_request_status"],
            "style_preset": "style.wiki_standard",
        },
    )
    assert empty_purposes.status_code == 422


def test_repeated_kind_makes_one_definition(
    client: TestClient,
    member: User,
    db: Session,
    workspace_id: int,
) -> None:
    """같은 kind를 두 번 골라도 정의와 폴더는 하나씩이다."""
    response = client.post(
        _ONBOARDING_PATH,
        json={
            "name": f"중복 kind-{uuid.uuid4().hex[:6]}",
            "domain_preset": "voc",
            "purpose_presets": ["voc.top_requests"],
            "kinds": ["feature_request_status", "feature_request_status"],
            "style_preset": "style.wiki_standard",
        },
    )

    assert response.status_code == 201, response.json()
    channel_id = uuid.UUID(response.json()["channel"]["id"])
    assert len(response.json()["definitions"]) == 1
    assert (
        len(
            [
                folder
                for folder in wiki_queries.list_folders(db, workspace_id)
                if folder.channel_id == channel_id
            ]
        )
        == 1
    )
