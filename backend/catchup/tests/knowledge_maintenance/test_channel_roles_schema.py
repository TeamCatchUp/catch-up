"""채널·역할 스키마 제약을 실 PostgreSQL로 확인한다.

역할 행은 인가 판정의 근거라 중복 관리자·중복 담당자·고아 폴더 같은
훼손을 DB가 막아야 한다. fake는 제약을 흉내내는 쪽이므로 실 DB에 직접
넣어 본다.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from collections.abc import Iterator

import pytest
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
from catchup.db.models import ArtifactOwner
from catchup.db.models import Channel
from catchup.db.models import ChannelAdmin
from catchup.db.models import ChannelFolder
from catchup.db.models import KnowledgeArtifact
from catchup.db.models import KnowledgeNode as NodeRow
from catchup.db.models import User
from catchup.db.models import Workspace
from catchup.tests.knowledge_maintenance.test_artifact_schema import (
    _violated_constraint,
)

ARTIFACT_KIND = "entity_summary"


@pytest.fixture(scope="module")
def engine() -> Iterator[Engine]:
    engine = create_engine(settings.sqlalchemy_database_url)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except OperationalError:
        engine.dispose()
        pytest.skip("PostgreSQL이 없어 통합 테스트를 건너뛴다.")

    if not inspect(engine).has_table(Channel.__tablename__):
        engine.dispose()
        pytest.skip("채널 테이블이 없다. alembic upgrade head가 필요하다.")

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


@pytest.fixture(scope="module")
def user_id(engine: Engine) -> int:
    with engine.connect() as connection:
        found = connection.execute(
            select(User.id).order_by(User.id).limit(1)
        ).scalar()

    if found is None:
        pytest.skip("user가 없어 통합 테스트를 건너뛴다.")
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


def _other_workspace_id(
    session_factory: Callable[[], Session],
    workspace_id: int,
) -> int:
    """비교용 workspace 하나를 새로 마련한다.

    workspace 경계를 넘는 배치를 시험하려면 서로 다른 workspace 둘이
    필요하다. 테스트 트랜잭션 안에서만 살고 끝나면 되돌려진다.
    """
    with session_factory() as session:
        company_id = session.execute(
            select(Workspace.company_id).where(Workspace.id == workspace_id)
        ).scalar_one()
        other = Workspace(
            name=f"ws-{uuid.uuid4().hex[:8]}", company_id=company_id
        )
        session.add(other)
        session.commit()
        return other.id


def _channel(
    session_factory: Callable[[], Session],
    workspace_id: int,
    user_id: int,
    name: str | None = None,
) -> uuid.UUID:
    """채널 한 개를 새로 만든다."""
    channel_id = uuid.uuid4()
    with session_factory() as session:
        session.add(
            Channel(
                id=channel_id,
                workspace_id=workspace_id,
                name=name or f"채널-{uuid.uuid4().hex[:8]}",
                created_by=user_id,
            )
        )
        session.commit()
    return channel_id


def _folder(
    session_factory: Callable[[], Session],
    workspace_id: int,
    channel_id: uuid.UUID,
    name: str | None = None,
) -> uuid.UUID:
    """채널 아래 폴더 한 개를 새로 만든다."""
    folder_id = uuid.uuid4()
    with session_factory() as session:
        session.add(
            ChannelFolder(
                id=folder_id,
                workspace_id=workspace_id,
                channel_id=channel_id,
                name=name or f"폴더-{uuid.uuid4().hex[:8]}",
            )
        )
        session.commit()
    return folder_id


def _artifact(
    session_factory: Callable[[], Session],
    workspace_id: int,
    channel_id: uuid.UUID | None = None,
) -> uuid.UUID:
    """주제 노드까지 갖춘 문서 한 편을 새로 만든다."""
    artifact_id = uuid.uuid4()
    with session_factory() as session:
        node = NodeRow(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            node_kind="entity",
            entity_type="feature",
            canonical_key=f"test:feature:{uuid.uuid4().hex}",
            display_name="결제 기능",
        )
        session.add(node)
        session.flush()
        session.add(
            KnowledgeArtifact(
                id=artifact_id,
                workspace_id=workspace_id,
                kind=ARTIFACT_KIND,
                channel_id=channel_id,
                subject_node_id=node.id,
                title="결제 기능",
            )
        )
        session.commit()
    return artifact_id


def test_channel_name_unique_per_workspace(
    workspace_id: int,
    user_id: int,
    session_factory: Callable[[], Session],
) -> None:
    """같은 workspace에 같은 이름 채널이 둘 생기지 않는다."""
    name = f"채널-{uuid.uuid4().hex[:8]}"
    _channel(session_factory, workspace_id, user_id, name=name)

    with session_factory() as session:
        session.add(
            Channel(
                id=uuid.uuid4(),
                workspace_id=workspace_id,
                name=name,
                created_by=user_id,
            )
        )
        with pytest.raises(IntegrityError) as excinfo:
            session.commit()

    assert _violated_constraint(excinfo) == "uq_channels_workspace_name"


def test_folder_name_unique_per_channel(
    workspace_id: int,
    user_id: int,
    session_factory: Callable[[], Session],
) -> None:
    """같은 채널에 같은 이름 폴더가 둘 생기지 않는다."""
    channel_id = _channel(session_factory, workspace_id, user_id)
    name = f"폴더-{uuid.uuid4().hex[:8]}"
    _folder(session_factory, workspace_id, channel_id, name=name)

    with session_factory() as session:
        session.add(
            ChannelFolder(
                id=uuid.uuid4(),
                workspace_id=workspace_id,
                channel_id=channel_id,
                name=name,
            )
        )
        with pytest.raises(IntegrityError) as excinfo:
            session.commit()

    assert (
        _violated_constraint(excinfo) == "uq_channel_folders_channel_name"
    )


def test_channel_admin_duplicate_rejected(
    workspace_id: int,
    user_id: int,
    session_factory: Callable[[], Session],
) -> None:
    """같은 사람이 같은 채널의 관리자로 두 번 등록되지 않는다."""
    channel_id = _channel(session_factory, workspace_id, user_id)

    with session_factory() as session:
        session.add(ChannelAdmin(channel_id=channel_id, user_id=user_id))
        session.commit()

    with session_factory() as session:
        with pytest.raises(IntegrityError) as excinfo:
            session.execute(
                ChannelAdmin.__table__.insert().values(
                    channel_id=channel_id, user_id=user_id
                )
            )

    assert _violated_constraint(excinfo) == "channel_admins_pkey"


def test_artifact_owner_duplicate_rejected(
    workspace_id: int,
    user_id: int,
    session_factory: Callable[[], Session],
) -> None:
    """같은 사람이 같은 문서의 담당자로 두 번 등록되지 않는다."""
    artifact_id = _artifact(session_factory, workspace_id)

    with session_factory() as session:
        session.add(ArtifactOwner(artifact_id=artifact_id, user_id=user_id))
        session.commit()

    with session_factory() as session:
        with pytest.raises(IntegrityError) as excinfo:
            session.execute(
                ArtifactOwner.__table__.insert().values(
                    artifact_id=artifact_id, user_id=user_id
                )
            )

    assert _violated_constraint(excinfo) == "artifact_owners_pkey"


def test_channel_delete_blocked_while_artifact_refers(
    workspace_id: int,
    user_id: int,
    session_factory: Callable[[], Session],
) -> None:
    """문서가 참조 중인 채널은 지워지지 않는다.

    문서→채널 FK는 RESTRICT라 지우려면 문서를 먼저 옮겨야 한다. 문서가
    조용히 미분류로 떨어지는 대신 삭제 자체가 막히는 쪽이다.
    """
    channel_id = _channel(session_factory, workspace_id, user_id)
    _artifact(session_factory, workspace_id, channel_id=channel_id)

    with session_factory() as session:
        with pytest.raises(IntegrityError) as excinfo:
            session.execute(
                Channel.__table__.delete().where(Channel.id == channel_id)
            )

    assert _violated_constraint(excinfo) == "fk_knowledge_artifacts_channel"


def test_channel_delete_cascades_admins_and_folders(
    workspace_id: int,
    user_id: int,
    session_factory: Callable[[], Session],
) -> None:
    """참조하는 문서가 없으면 채널과 함께 관리자·폴더가 사라진다."""
    channel_id = _channel(session_factory, workspace_id, user_id)
    _folder(session_factory, workspace_id, channel_id)

    with session_factory() as session:
        session.add(ChannelAdmin(channel_id=channel_id, user_id=user_id))
        session.commit()

    with session_factory() as session:
        session.execute(
            Channel.__table__.delete().where(Channel.id == channel_id)
        )
        session.commit()

        admins = session.execute(
            select(ChannelAdmin).where(
                ChannelAdmin.channel_id == channel_id
            )
        ).all()
        folders = session.execute(
            select(ChannelFolder).where(
                ChannelFolder.channel_id == channel_id
            )
        ).all()

    assert admins == []
    assert folders == []


def test_artifact_channel_from_other_workspace_is_blocked(
    workspace_id: int,
    user_id: int,
    session_factory: Callable[[], Session],
) -> None:
    """다른 workspace의 채널에는 문서를 놓을 수 없다."""
    other_workspace_id = _other_workspace_id(session_factory, workspace_id)
    foreign_channel_id = _channel(
        session_factory, other_workspace_id, user_id
    )

    with pytest.raises(IntegrityError) as excinfo:
        _artifact(
            session_factory, workspace_id, channel_id=foreign_channel_id
        )

    assert _violated_constraint(excinfo) == "fk_knowledge_artifacts_channel"


def test_folder_channel_from_other_workspace_is_blocked(
    workspace_id: int,
    user_id: int,
    session_factory: Callable[[], Session],
) -> None:
    """다른 workspace의 채널 아래에는 폴더를 만들 수 없다."""
    other_workspace_id = _other_workspace_id(session_factory, workspace_id)
    foreign_channel_id = _channel(
        session_factory, other_workspace_id, user_id
    )

    with session_factory() as session:
        session.add(
            ChannelFolder(
                id=uuid.uuid4(),
                workspace_id=workspace_id,
                channel_id=foreign_channel_id,
                name=f"폴더-{uuid.uuid4().hex[:8]}",
            )
        )
        with pytest.raises(IntegrityError) as excinfo:
            session.commit()

    assert _violated_constraint(excinfo) == "fk_channel_folders_channel"


def test_wiki_reviewer_grants_table_dropped(engine: Engine) -> None:
    """옛 검수 인가 테이블은 더 이상 남아 있지 않다."""
    assert not inspect(engine).has_table("wiki_reviewer_grants")
