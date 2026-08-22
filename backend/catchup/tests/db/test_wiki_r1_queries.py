"""문서 목록·담당자·채널 목적·즐겨찾기 쿼리를 실 PostgreSQL로 확인한다.

상태 파생(계류 제안 수와 최신 판)은 상관 서브쿼리와 join으로 계산하므로
대역으로는 재현되지 않는다. 그래서 실 연결을 빌려 테스트마다 되감는다.

workspace는 테스트 안에서 새로 만든다. 이미 들어 있는 문서가 목록 전체 수에
섞이면 total 값을 확인할 수 없기 때문이다.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from collections.abc import Iterator
from datetime import UTC
from datetime import datetime
from datetime import timedelta

import pytest
from sqlalchemy import Connection
from sqlalchemy import Engine
from sqlalchemy import create_engine
from sqlalchemy import inspect
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker

from catchup.configs.config import settings
from catchup.db import wiki as wiki_queries
from catchup.db.models import Channel
from catchup.db.models import ChannelFolder
from catchup.db.models import Company
from catchup.db.models import CompanySize
from catchup.db.models import KnowledgeArtifact
from catchup.db.models import KnowledgeArtifactChangeProposal
from catchup.db.models import KnowledgeArtifactRevision
from catchup.db.models import KnowledgeNode
from catchup.db.models import User
from catchup.db.models import UserStatus
from catchup.db.models import UserWorkspace
from catchup.db.models import WikiArtifactFavorite
from catchup.db.models import Workspace

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

    if not inspect(engine).has_table(WikiArtifactFavorite.__tablename__):
        engine.dispose()
        pytest.skip("즐겨찾기 테이블이 없다. alembic upgrade head가 필요하다.")

    yield engine
    engine.dispose()


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
def workspace_id(db: Session) -> int:
    """이 테스트만 쓰는 빈 workspace를 만든다."""
    company = Company(name=f"co-{uuid.uuid4().hex[:8]}", size=CompanySize.SMALL)
    db.add(company)
    db.flush()
    workspace = Workspace(name=f"ws-{uuid.uuid4().hex[:8]}", company_id=company.id)
    db.add(workspace)
    db.flush()
    return workspace.id


# ======================= 데이터 헬퍼 =======================


def _user(db: Session, email: str) -> User:
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


def _channel(db: Session, workspace_id: int, created_by: int) -> Channel:
    """테스트용 채널 하나를 만든다."""
    channel = wiki_queries.add_channel(
        db,
        workspace_id=workspace_id,
        name=f"voc-{uuid.uuid4().hex[:8]}",
        created_by=created_by,
    )
    db.flush()
    return channel


def _folder(db: Session, channel: Channel, name: str) -> ChannelFolder:
    """채널 아래 폴더 하나를 만든다."""
    folder = wiki_queries.add_folder(
        db,
        workspace_id=channel.workspace_id,
        channel_id=channel.id,
        name=name,
        created_by=channel.created_by,
    )
    db.flush()
    return folder


def _entity_node(db: Session, workspace_id: int, name: str) -> uuid.UUID:
    """canonical entity 노드를 하나 만든다."""
    node = KnowledgeNode(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        node_kind="entity",
        entity_type="feature",
        canonical_key=f"test:feature:{uuid.uuid4().hex}",
        display_name=name,
    )
    db.add(node)
    db.flush()
    return node.id


def _artifact(
    db: Session,
    workspace_id: int,
    channel: Channel,
    kind: str,
    title: str,
    folder: ChannelFolder | None = None,
) -> KnowledgeArtifact:
    """문서 한 편을 만든다. 대상 노드는 문서마다 새로 만든다."""
    artifact = KnowledgeArtifact(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        kind=kind,
        channel_id=channel.id,
        folder_id=None if folder is None else folder.id,
        subject_node_id=_entity_node(db, workspace_id, title),
        title=title,
    )
    db.add(artifact)
    db.flush()
    return artifact


def _proposal(
    db: Session,
    artifact: KnowledgeArtifact,
    status: str,
    reviewer: str = "test:reviewer",
) -> KnowledgeArtifactChangeProposal:
    """문서 변경안 한 건을 만든다."""
    decided = status in ("approved", "rejected")
    proposal = KnowledgeArtifactChangeProposal(
        id=uuid.uuid4(),
        workspace_id=artifact.workspace_id,
        artifact_id=artifact.id,
        blocks=[],
        status=status,
        content_hash=uuid.uuid4().hex,
        idempotency_key=uuid.uuid4().hex,
        # 승인·반려에는 결정자와 시각이 반드시 남아야 한다는 DB 제약이 있다.
        reviewer=reviewer if decided else None,
        reviewed_at=datetime.now(UTC) if decided else None,
        rejection_reason="사유" if status == "rejected" else None,
    )
    db.add(proposal)
    db.flush()
    return proposal


def _revision(
    db: Session,
    artifact: KnowledgeArtifact,
    number: int,
    reviewer: str = "test:reviewer",
) -> KnowledgeArtifactRevision:
    """문서 한 판을 만든다. 판은 승인된 제안에서 나오므로 제안을 먼저 만든다."""
    proposal = _proposal(db, artifact, "approved", reviewer=reviewer)
    revision = KnowledgeArtifactRevision(
        id=uuid.uuid4(),
        workspace_id=artifact.workspace_id,
        artifact_id=artifact.id,
        revision_number=number,
        blocks=[],
        source_proposal_id=proposal.id,
    )
    db.add(revision)
    db.flush()
    return revision


# ======================= 테스트 =======================


def test_list_owners_by_artifact_joins_user_display(db, workspace_id) -> None:
    """담당자를 사용자 이름·사진과 함께 문서별로 묶어 준다."""
    user = _user(db, "owner@x.com")
    user.picture = "https://img/x.png"
    channel = _channel(db, workspace_id, created_by=user.id)
    art = _artifact(db, workspace_id, channel, "feature_request_status", "결제")
    wiki_queries.add_artifact_owner(
        db, artifact_id=art.id, user_id=user.id, granted_by=user.id
    )
    db.flush()

    rows = wiki_queries.list_owners_by_artifact(db, artifact_ids=[art.id])

    assert rows == {
        art.id: [wiki_queries.OwnerRow(art.id, user.id, user.name, "https://img/x.png")]
    }


def test_list_artifacts_status_is_derived(db, workspace_id) -> None:
    """계류 제안이 있으면 pending_review, 없고 발행판 있으면 published, 둘 다 없으면 no_revision이다."""
    user = _user(db, "a@x.com")
    channel = _channel(db, workspace_id, created_by=user.id)
    pending = _artifact(db, workspace_id, channel, "feature_request_status", "A")
    _proposal(db, pending, "pending")
    _revision(db, pending, 1)
    published = _artifact(db, workspace_id, channel, "feature_request_status", "B")
    _revision(db, published, 1)
    _revision(db, published, 2)
    bare = _artifact(db, workspace_id, channel, "faq_answer", "C")
    db.flush()

    rows, total = wiki_queries.list_artifacts(db, workspace_id=workspace_id)
    by_title = {row.title: row for row in rows}

    assert total == 3
    assert bare.id in {row.artifact_id for row in rows}
    assert wiki_queries.artifact_status(by_title["A"]) == "pending_review"
    assert by_title["A"].pending_proposal_count == 1
    assert wiki_queries.artifact_status(by_title["B"]) == "published"
    assert by_title["B"].latest_revision_number == 2
    assert wiki_queries.artifact_status(by_title["C"]) == "no_revision"
    assert by_title["C"].latest_revision_id is None


def test_list_artifacts_filters(db, workspace_id) -> None:
    """채널·폴더·kind·상태·담당자·생성일 필터가 각각 작동하고 total은 필터 뒤 수다."""
    user = _user(db, "f@x.com")
    channel = _channel(db, workspace_id, created_by=user.id)
    other_channel = _channel(db, workspace_id, created_by=user.id)
    folder = _folder(db, channel, "결제")
    in_folder = _artifact(
        db, workspace_id, channel, "feature_request_status", "A", folder=folder
    )
    _revision(db, in_folder, 1)
    faq = _artifact(db, workspace_id, channel, "faq_answer", "B")
    _proposal(db, faq, "pending")
    elsewhere = _artifact(
        db, workspace_id, other_channel, "feature_request_status", "C"
    )
    wiki_queries.add_artifact_owner(
        db, artifact_id=elsewhere.id, user_id=user.id, granted_by=user.id
    )
    db.flush()

    _, all_total = wiki_queries.list_artifacts(db, workspace_id=workspace_id)
    assert all_total == 3

    rows, total = wiki_queries.list_artifacts(
        db, workspace_id=workspace_id, channel_id=channel.id
    )
    assert total == 2
    assert {row.title for row in rows} == {"A", "B"}

    rows, total = wiki_queries.list_artifacts(
        db, workspace_id=workspace_id, folder_id=folder.id
    )
    assert total == 1
    assert rows[0].artifact_id == in_folder.id
    assert rows[0].folder_id == folder.id

    rows, total = wiki_queries.list_artifacts(
        db, workspace_id=workspace_id, kind="faq_answer"
    )
    assert total == 1
    assert rows[0].artifact_id == faq.id

    rows, total = wiki_queries.list_artifacts(
        db, workspace_id=workspace_id, status="published"
    )
    assert total == 1
    assert rows[0].artifact_id == in_folder.id

    rows, total = wiki_queries.list_artifacts(
        db, workspace_id=workspace_id, status="no_revision"
    )
    assert total == 1
    assert rows[0].artifact_id == elsewhere.id

    rows, total = wiki_queries.list_artifacts(
        db, workspace_id=workspace_id, owner_user_ids=[user.id]
    )
    assert total == 1
    assert rows[0].artifact_id == elsewhere.id

    _, total = wiki_queries.list_artifacts(
        db,
        workspace_id=workspace_id,
        created_after=datetime.now(UTC) + timedelta(days=1),
    )
    assert total == 0

    _, total = wiki_queries.list_artifacts(
        db,
        workspace_id=workspace_id,
        created_before=datetime.now(UTC) - timedelta(days=1),
    )
    assert total == 0


def test_list_artifacts_paginates(db, workspace_id) -> None:
    """limit·offset으로 잘라도 total은 필터 뒤 전체 수 그대로다."""
    user = _user(db, "p@x.com")
    channel = _channel(db, workspace_id, created_by=user.id)
    for title in ("A", "B", "C"):
        _artifact(db, workspace_id, channel, "faq_answer", title)
    db.flush()

    first, total = wiki_queries.list_artifacts(db, workspace_id=workspace_id, limit=2)
    second, _ = wiki_queries.list_artifacts(
        db, workspace_id=workspace_id, limit=2, offset=2
    )

    assert total == 3
    assert len(first) == 2
    assert len(second) == 1
    assert {row.artifact_id for row in first} & {
        row.artifact_id for row in second
    } == set()


def test_favorites_roundtrip(db, workspace_id) -> None:
    """add는 처음만 True, 두 번째는 False. remove는 있을 때만 True. 목록은 최근 순."""
    user = _user(db, "fav@x.com")
    channel = _channel(db, workspace_id, created_by=user.id)
    first = _artifact(db, workspace_id, channel, "faq_answer", "A")
    second = _artifact(db, workspace_id, channel, "faq_answer", "B")
    db.flush()

    assert (
        wiki_queries.add_favorite(
            db,
            user_id=user.id,
            artifact_id=first.id,
            workspace_id=workspace_id,
        )
        is True
    )
    db.flush()
    assert (
        wiki_queries.add_favorite(
            db,
            user_id=user.id,
            artifact_id=first.id,
            workspace_id=workspace_id,
        )
        is False
    )
    db.flush()
    assert wiki_queries.is_favorite(db, user_id=user.id, artifact_id=first.id)
    assert not wiki_queries.is_favorite(db, user_id=user.id, artifact_id=second.id)

    later = datetime.now(UTC) + timedelta(minutes=5)
    db.add(
        WikiArtifactFavorite(
            user_id=user.id,
            artifact_id=second.id,
            workspace_id=workspace_id,
            created_at=later,
        )
    )
    db.flush()

    assert wiki_queries.list_favorite_artifact_ids(
        db, user_id=user.id, workspace_id=workspace_id
    ) == {first.id, second.id}
    favorites = wiki_queries.list_favorites(
        db, user_id=user.id, workspace_id=workspace_id
    )
    assert [artifact.id for artifact, _ in favorites] == [second.id, first.id]

    assert (
        wiki_queries.remove_favorite(db, user_id=user.id, artifact_id=first.id) is True
    )
    db.flush()
    assert (
        wiki_queries.remove_favorite(db, user_id=user.id, artifact_id=first.id) is False
    )


def test_channel_purposes_keep_position(db, workspace_id) -> None:
    """저장한 순서대로 돌려준다."""
    user = _user(db, "purpose@x.com")
    channel = _channel(db, workspace_id, created_by=user.id)
    other = _channel(db, workspace_id, created_by=user.id)
    wiki_queries.add_channel_purposes(
        db,
        channel_id=channel.id,
        purpose_presets=["voc.top_requests", "voc.bug_watch", "voc.faq"],
    )
    wiki_queries.add_channel_purposes(
        db, channel_id=other.id, purpose_presets=["voc.faq"]
    )
    db.flush()

    assert wiki_queries.list_channel_purposes(db, channel_id=channel.id) == [
        "voc.top_requests",
        "voc.bug_watch",
        "voc.faq",
    ]
    assert wiki_queries.list_channel_purposes_by_workspace(db, workspace_id) == {
        channel.id: ["voc.top_requests", "voc.bug_watch", "voc.faq"],
        other.id: ["voc.faq"],
    }


def test_set_artifact_folder_and_locations(db, workspace_id) -> None:
    """폴더를 바꾸면 get_artifact_locations가 새 (channel_id, folder_id)를 준다."""
    user = _user(db, "loc@x.com")
    channel = _channel(db, workspace_id, created_by=user.id)
    folder = _folder(db, channel, "결제")
    artifact = _artifact(db, workspace_id, channel, "faq_answer", "A")
    db.flush()

    assert wiki_queries.get_artifact_locations(db, artifact_ids=[artifact.id]) == {
        artifact.id: (channel.id, None)
    }

    wiki_queries.set_artifact_folder(db, artifact=artifact, folder_id=folder.id)
    db.flush()

    assert wiki_queries.get_artifact_locations(db, artifact_ids=[artifact.id]) == {
        artifact.id: (channel.id, folder.id)
    }

    wiki_queries.set_artifact_folder(db, artifact=artifact, folder_id=None)
    db.flush()

    assert wiki_queries.get_artifact_locations(db, artifact_ids=[artifact.id]) == {
        artifact.id: (channel.id, None)
    }


def test_list_artifact_ids_by_channel_and_owner(db, workspace_id) -> None:
    """채널별·담당자별 문서 id 목록을 workspace 안에서만 읽는다."""
    user = _user(db, "ids@x.com")
    other_user = _user(db, "ids2@x.com")
    channel = _channel(db, workspace_id, created_by=user.id)
    other_channel = _channel(db, workspace_id, created_by=user.id)
    mine = _artifact(db, workspace_id, channel, "faq_answer", "A")
    theirs = _artifact(db, workspace_id, other_channel, "faq_answer", "B")
    wiki_queries.add_artifact_owner(
        db, artifact_id=mine.id, user_id=user.id, granted_by=user.id
    )
    wiki_queries.add_artifact_owner(
        db, artifact_id=theirs.id, user_id=other_user.id, granted_by=user.id
    )
    db.flush()

    assert wiki_queries.list_artifact_ids_by_channel(
        db, workspace_id=workspace_id, channel_id=channel.id
    ) == [mine.id]
    assert wiki_queries.list_artifact_ids_by_owner(
        db, workspace_id=workspace_id, user_id=other_user.id
    ) == [theirs.id]


def test_get_folder_by_name(db, workspace_id) -> None:
    """같은 채널 안에서 이름으로 폴더를 찾고, 없으면 None이다."""
    user = _user(db, "folder@x.com")
    channel = _channel(db, workspace_id, created_by=user.id)
    other = _channel(db, workspace_id, created_by=user.id)
    folder = _folder(db, channel, "결제")
    _folder(db, other, "결제")
    db.flush()

    found = wiki_queries.get_folder_by_name(db, channel_id=channel.id, name="결제")
    assert found is not None
    assert found.id == folder.id
    assert (
        wiki_queries.get_folder_by_name(db, channel_id=channel.id, name="배송") is None
    )


def test_definitions_carry_folder_and_purpose(db, workspace_id) -> None:
    """정의에 폴더와 목적을 함께 저장하고 workspace 단위로 채널별로 묶어 읽는다."""
    user = _user(db, "def@x.com")
    channel = _channel(db, workspace_id, created_by=user.id)
    other = _channel(db, workspace_id, created_by=user.id)
    folder = _folder(db, channel, "결제")
    definition = wiki_queries.add_artifact_definition(
        db,
        workspace_id=workspace_id,
        channel_id=channel.id,
        kind="feature_request_status",
        selection_spec={"entity": {}},
        created_by=user.id,
        folder_id=folder.id,
        purpose="결제 요청 현황을 모은다",
    )
    wiki_queries.add_artifact_definition(
        db,
        workspace_id=workspace_id,
        channel_id=other.id,
        kind="faq_answer",
        selection_spec={"entity": {}},
        created_by=user.id,
    )
    db.flush()
    db.expire(definition)

    assert definition.folder_id == folder.id
    assert definition.purpose == "결제 요청 현황을 모은다"

    by_channel = wiki_queries.list_definitions_by_workspace(db, workspace_id)

    assert set(by_channel) == {channel.id, other.id}
    assert [row.kind for row in by_channel[channel.id]] == ["feature_request_status"]
    assert [row.kind for row in by_channel[other.id]] == ["faq_answer"]


# ======================= 대시보드 목록 =======================


def _artifact_at(
    db: Session,
    workspace_id: int,
    channel: Channel,
    title: str,
    created_at: datetime,
) -> KnowledgeArtifact:
    """생성 시각을 직접 지정한 문서 한 편을 만든다.

    created_at의 server_default가 now()라, 한 트랜잭션 안에서 만든 문서는
    시각이 전부 같아진다. 정렬을 확인하려면 시각을 직접 넣어야 한다.
    """
    artifact = _artifact(db, workspace_id, channel, "faq_answer", title)
    artifact.created_at = created_at
    db.flush()
    return artifact


def _proposal_at(
    db: Session,
    artifact: KnowledgeArtifact,
    status: str,
    created_at: datetime,
) -> KnowledgeArtifactChangeProposal:
    """도착 시각을 직접 지정한 변경안 한 건을 만든다."""
    proposal = _proposal(db, artifact, status)
    proposal.created_at = created_at
    db.flush()
    return proposal


def _revision_at(
    db: Session,
    artifact: KnowledgeArtifact,
    number: int,
    created_at: datetime,
) -> KnowledgeArtifactRevision:
    """발행 시각을 직접 지정한 판 하나를 만든다.

    판을 만들면 출처가 되는 승인 제안도 함께 생긴다. 그 제안의 시각도 같이
    맞춰야 "발행이 마지막 활동"인 상황을 만들 수 있다.
    """
    revision = _revision(db, artifact, number)
    revision.created_at = created_at
    proposal = db.get(KnowledgeArtifactChangeProposal, revision.source_proposal_id)
    assert proposal is not None
    proposal.created_at = created_at
    db.flush()
    return revision


def test_list_artifacts_unassigned_filter(db, workspace_id) -> None:
    """unassigned는 담당자 행이 하나도 없는 문서만 남긴다."""
    user = _user(db, "unassigned@x.com")
    channel = _channel(db, workspace_id, created_by=user.id)
    assigned = _artifact(db, workspace_id, channel, "faq_answer", "담당 있음")
    orphan = _artifact(db, workspace_id, channel, "faq_answer", "담당 없음")
    wiki_queries.add_artifact_owner(
        db, artifact_id=assigned.id, user_id=user.id, granted_by=user.id
    )
    db.flush()

    rows, total = wiki_queries.list_artifacts(
        db, workspace_id=workspace_id, unassigned=True
    )

    assert total == 1
    assert rows[0].artifact_id == orphan.id


def test_list_artifacts_owner_filter_is_or_over_users(db, workspace_id) -> None:
    """owner_user_ids는 그중 한 명이라도 담당자인 문서를 모두 남긴다."""
    first = _user(db, "owner-or-1@x.com")
    second = _user(db, "owner-or-2@x.com")
    channel = _channel(db, workspace_id, created_by=first.id)
    mine = _artifact(db, workspace_id, channel, "faq_answer", "내 담당")
    yours = _artifact(db, workspace_id, channel, "faq_answer", "네 담당")
    _artifact(db, workspace_id, channel, "faq_answer", "담당 없음")
    wiki_queries.add_artifact_owner(
        db, artifact_id=mine.id, user_id=first.id, granted_by=first.id
    )
    wiki_queries.add_artifact_owner(
        db, artifact_id=yours.id, user_id=second.id, granted_by=first.id
    )
    db.flush()

    rows, total = wiki_queries.list_artifacts(
        db, workspace_id=workspace_id, owner_user_ids=[first.id, second.id]
    )

    assert total == 2
    assert {row.artifact_id for row in rows} == {mine.id, yours.id}


def test_list_artifacts_owner_filter_does_not_duplicate_rows(
    db, workspace_id
) -> None:
    """담당자가 여럿인 문서도 한 줄로만 실리고 total과 줄 수가 어긋나지 않는다."""
    first = _user(db, "owner-dup-1@x.com")
    second = _user(db, "owner-dup-2@x.com")
    channel = _channel(db, workspace_id, created_by=first.id)
    shared = _artifact(db, workspace_id, channel, "faq_answer", "공동 담당")
    wiki_queries.add_artifact_owner(
        db, artifact_id=shared.id, user_id=first.id, granted_by=first.id
    )
    wiki_queries.add_artifact_owner(
        db, artifact_id=shared.id, user_id=second.id, granted_by=first.id
    )
    db.flush()

    rows, total = wiki_queries.list_artifacts(
        db, workspace_id=workspace_id, owner_user_ids=[first.id, second.id]
    )

    assert total == 1
    assert len(rows) == 1
    assert rows[0].artifact_id == shared.id


def test_list_artifacts_empty_owner_filter_keeps_all(db, workspace_id) -> None:
    """owner_user_ids가 비어 있으면 담당자 조건을 걸지 않은 것과 같다."""
    user = _user(db, "owner-empty@x.com")
    channel = _channel(db, workspace_id, created_by=user.id)
    _artifact(db, workspace_id, channel, "faq_answer", "아무거나")
    db.flush()

    _, total = wiki_queries.list_artifacts(
        db, workspace_id=workspace_id, owner_user_ids=[]
    )

    assert total == 1


def test_list_artifacts_searches_title(db, workspace_id) -> None:
    """q는 제목 부분일치로 거르고, 와일드카드 문자는 글자 그대로 본다."""
    user = _user(db, "search@x.com")
    channel = _channel(db, workspace_id, created_by=user.id)
    for title in ("결제 오류", "배송 지연", "50% 할인", "5012 정산", "a_b", "axb"):
        _artifact(db, workspace_id, channel, "faq_answer", title)
    db.flush()

    rows, total = wiki_queries.list_artifacts(db, workspace_id=workspace_id, q="오류")
    assert total == 1
    assert rows[0].title == "결제 오류"

    _, blank_total = wiki_queries.list_artifacts(db, workspace_id=workspace_id, q="   ")
    assert blank_total == 6

    rows, total = wiki_queries.list_artifacts(db, workspace_id=workspace_id, q="50%")
    assert total == 1
    assert rows[0].title == "50% 할인"

    rows, total = wiki_queries.list_artifacts(db, workspace_id=workspace_id, q="a_b")
    assert total == 1
    assert rows[0].title == "a_b"


def test_list_artifacts_sorts_by_activity_or_creation(db, workspace_id) -> None:
    """정렬 키와 방향을 고를 수 있고, 기본값은 마지막 활동 내림차순이다."""
    user = _user(db, "sort@x.com")
    channel = _channel(db, workspace_id, created_by=user.id)
    base = datetime(2026, 1, 1, tzinfo=UTC)
    old = _artifact_at(db, workspace_id, channel, "old", base)
    mid = _artifact_at(db, workspace_id, channel, "mid", base + timedelta(days=1))
    new = _artifact_at(db, workspace_id, channel, "new", base + timedelta(days=2))
    # 가장 먼저 만들어진 문서에 가장 늦은 활동을 붙인다. 두 정렬 키가
    # 서로 다른 순서를 내야 무엇으로 정렬했는지 구분된다.
    _proposal_at(db, old, "pending", base + timedelta(days=3))

    def titles(**kwargs: object) -> list[str]:
        rows, _ = wiki_queries.list_artifacts(db, workspace_id=workspace_id, **kwargs)
        return [row.title for row in rows]

    assert titles() == ["old", "new", "mid"]
    assert titles(sort="last_activity", order="desc") == ["old", "new", "mid"]
    assert titles(sort="last_activity", order="asc") == ["mid", "new", "old"]
    assert titles(sort="created_at", order="asc") == ["old", "mid", "new"]
    assert titles(sort="created_at", order="desc") == ["new", "mid", "old"]
    assert {old.id, mid.id, new.id} == {
        row.artifact_id
        for row in wiki_queries.list_artifacts(db, workspace_id=workspace_id)[0]
    }


def test_list_artifacts_last_activity_at(db, workspace_id) -> None:
    """마지막 활동 시각은 발행·제안 중 늦은 쪽이고, 둘 다 없으면 생성 시각이다."""
    user = _user(db, "activity@x.com")
    channel = _channel(db, workspace_id, created_by=user.id)
    base = datetime(2026, 2, 1, tzinfo=UTC)
    quiet = _artifact_at(db, workspace_id, channel, "조용함", base)
    published = _artifact_at(db, workspace_id, channel, "발행됨", base)
    _revision_at(db, published, 1, base + timedelta(days=5))
    proposed = _artifact_at(db, workspace_id, channel, "제안됨", base)
    _revision_at(db, proposed, 1, base + timedelta(days=5))
    # 반려된 제안도 활동이다. 도착 자체가 문서가 움직인 사실이라
    # status로 가리지 않는다.
    _proposal_at(db, proposed, "rejected", base + timedelta(days=9))

    rows, _ = wiki_queries.list_artifacts(db, workspace_id=workspace_id)
    activity = {row.title: row.last_activity_at for row in rows}

    assert activity["조용함"] == base
    assert activity["발행됨"] == base + timedelta(days=5)
    assert activity["제안됨"] == base + timedelta(days=9)


def test_list_artifacts_carries_latest_revision_approval(db, workspace_id) -> None:
    """목록 줄에 최신 발행판을 승인한 사람과 승인 시각이 실린다.

    판을 여러 번 발행한 문서는 번호가 가장 큰 판의 승인 기록만 실어야 한다.
    발행판이 없는 문서는 승인 기록도 없으므로 둘 다 None이다.
    """
    user = _user(db, "approval@x.com")
    channel = _channel(db, workspace_id, created_by=user.id)
    published = _artifact(db, workspace_id, channel, "faq_answer", "발행됨")
    _revision(db, published, 1, reviewer="user:11")
    latest = _revision(db, published, 2, reviewer="user:22")
    bare = _artifact(db, workspace_id, channel, "faq_answer", "판없음")
    db.flush()

    rows, _ = wiki_queries.list_artifacts(db, workspace_id=workspace_id)
    by_title = {row.title: row for row in rows}

    assert by_title["발행됨"].last_edit_reviewer == "user:22"
    assert by_title["발행됨"].last_edit_reviewed_at is not None
    assert by_title["판없음"].last_edit_reviewer is None
    assert by_title["판없음"].last_edit_reviewed_at is None
    assert bare.id in {row.artifact_id for row in rows}
    assert latest.revision_number == 2


def test_get_revision_approval_reads_source_proposal(db, workspace_id) -> None:
    """판 하나의 승인자와 승인 시각을 그 판을 만든 변경안에서 읽는다."""
    user = _user(db, "revapproval@x.com")
    channel = _channel(db, workspace_id, created_by=user.id)
    artifact = _artifact(db, workspace_id, channel, "faq_answer", "발행됨")
    revision = _revision(db, artifact, 1, reviewer="user:33")
    db.flush()

    approval = wiki_queries.get_revision_approval(db, revision_id=revision.id)

    assert approval is not None
    assert approval.reviewer == "user:33"
    assert approval.reviewed_at is not None


def test_list_users_for_display_skips_unknown_ids(db, workspace_id) -> None:
    """사용자 id로 이름·사진을 한 번에 읽고, 없는 id는 결과에서 빠진다."""
    user = _user(db, "display@x.com")
    user.picture = "https://img/display.png"
    db.flush()

    found = wiki_queries.list_users_for_display(db, user_ids=[user.id, -1])

    assert set(found) == {user.id}
    assert found[user.id].display_name == user.name
    assert found[user.id].profile_image_url == "https://img/display.png"


def _member(
    db: Session,
    *,
    workspace_id: int,
    email: str,
    name: str,
    status: UserStatus = UserStatus.ACTIVE,
) -> User:
    """이름과 상태를 지정한 workspace 구성원 한 명을 만든다."""
    user = User(
        email=email,
        name=name,
        picture=f"https://example.com/{name}.png",
        provider="keycloak",
        status=status,
    )
    db.add(user)
    db.flush()
    db.add(UserWorkspace(user_id=user.id, workspace_id=workspace_id))
    db.flush()
    return user


def test_list_workspace_members_returns_active_members_only(db, workspace_id) -> None:
    """활성 구성원만 이름 순으로 돌려주고, 다른 workspace는 섞이지 않는다."""
    company = Company(name=f"co-{uuid.uuid4().hex[:8]}", size=CompanySize.SMALL)
    db.add(company)
    db.flush()
    other = Workspace(name=f"ws-{uuid.uuid4().hex[:8]}", company_id=company.id)
    db.add(other)
    db.flush()
    second = _member(db, workspace_id=workspace_id, email="n@x.com", name="나")
    first = _member(db, workspace_id=workspace_id, email="g@x.com", name="가")
    _member(
        db,
        workspace_id=workspace_id,
        email="off@x.com",
        name="다",
        status=UserStatus.INACTIVE,
    )
    _member(db, workspace_id=other.id, email="other@x.com", name="라")

    rows = wiki_queries.list_workspace_members(db, workspace_id=workspace_id)

    assert [row.user_id for row in rows] == [first.id, second.id]
    assert [row.display_name for row in rows] == ["가", "나"]
    assert rows[0].profile_image_url == first.picture
