"""정의 스키마 마이그레이션의 왕복을 실 PostgreSQL로 확인한다.

downgrade는 옛 전역 UNIQUE(workspace, kind, subject)를 되돌린다. 정의
기능을 정상적으로 쓴 DB에는 채널이 다른 두 정의가 같은 대상을 각각
문서화한 행이 있어, 그대로 두면 UNIQUE 생성이 중복으로 막힌다. downgrade는
그런 데이터를 지우지 않고 거부한다(fail-closed) — 정리는 사람의 명시적
행위다.

거부 범위는 이 마이그레이션이 만든 자리 전부다. 정의 기반 문서뿐 아니라,
문서가 아직 0건인 정의 행과 채널에 저장된 목적·문체 설정도 각각 단독으로
거부 사유가 된다. 셋을 따로 세우고 거부가 걸리는지, 그리고 전부 정리한
깨끗한 상태에서는 왕복이 도는지를 본다.

이 테스트는 공유 DB를 건드리지 않는다. 모듈 픽스처가 폐기 가능한 임시
DB를 직접 만들고(`catchup_migration_test_*`), 거기에 alembic upgrade head를
돌린 뒤 왕복을 확인하고, 끝나면 그 DB를 통째로 DROP한다. 스키마를
되돌렸다 올리는 파괴적 동작이므로 다른 테스트와 DB 자체를 분리한다.
"""

from __future__ import annotations

import pathlib
import uuid
from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from sqlalchemy import Engine
from sqlalchemy import create_engine
from sqlalchemy import inspect
from sqlalchemy import text
from sqlalchemy.engine import URL
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from alembic import command
from alembic import config as alembic_config
from catchup.configs.config import settings
from catchup.db.models import ArtifactDefinition
from catchup.db.models import Channel
from catchup.db.models import Company
from catchup.db.models import KnowledgeArtifact
from catchup.db.models import KnowledgeNode as NodeRow
from catchup.db.models import User
from catchup.db.models import UserStatus
from catchup.db.models import Workspace

# 정의 테이블이 생기기 직전 판이다. downgrade가 멈춰야 할 지점.
PREVIOUS_REVISION = "c6643084f8b9"

ARTIFACT_KIND = "entity_summary"

SELECTION_SPEC = {
    "entity_filter": {"entity_types": ["feature_request"]},
    "relation_paths": [],
    "predicate_sections": None,
}

BACKEND_ROOT = pathlib.Path(__file__).resolve().parents[3]
ALEMBIC_INI = BACKEND_ROOT / "alembic.ini"


def _temp_database_name() -> str:
    """충돌하지 않는 임시 DB 이름을 만든다."""
    return f"catchup_migration_test_{uuid.uuid4().hex[:8]}"


def _with_database(url: URL, database: str) -> URL:
    """같은 서버의 다른 DB를 가리키는 URL을 만든다."""
    return url.set(database=database)


@contextmanager
def _alembic_pointed_at(database: str) -> Iterator[alembic_config.Config]:
    """alembic이 임시 DB를 보도록 settings를 잠시 바꾼다.

    alembic/env.py는 alembic.ini의 sqlalchemy.url을 무조건
    `settings.sqlalchemy_database_url`로 덮어쓴다. 그래서
    `config.set_main_option`으로는 주입이 되지 않고, settings 쪽
    DB 이름을 바꾸는 것이 실제로 작동하는 유일한 주입 지점이다.
    env.py는 이미 로딩된 settings 싱글턴을 그대로 읽으므로 이 교체가
    그대로 반영된다.
    """
    original = settings.DB_DATABASE
    settings.DB_DATABASE = database
    try:
        yield alembic_config.Config(str(ALEMBIC_INI))
    finally:
        settings.DB_DATABASE = original


@pytest.fixture(scope="module")
def engine() -> Iterator[Engine]:
    """임시 DB를 만들고 head까지 올린 뒤 넘기고, 끝나면 DROP한다."""
    admin_url = make_url(settings.sqlalchemy_database_url)
    admin_engine = create_engine(
        admin_url, isolation_level="AUTOCOMMIT"
    )
    try:
        with admin_engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except OperationalError:
        admin_engine.dispose()
        pytest.skip("PostgreSQL이 없어 통합 테스트를 건너뛴다.")

    database = _temp_database_name()
    try:
        with admin_engine.connect() as connection:
            connection.execute(text(f'CREATE DATABASE "{database}"'))
    except DBAPIError as error:
        admin_engine.dispose()
        pytest.skip(
            "임시 DB를 만들 수 없어 통합 테스트를 건너뛴다"
            f" (CREATE DATABASE 권한 필요): {error}"
        )

    temp_engine: Engine | None = None
    try:
        _install_extensions(_with_database(admin_url, database))
        with _alembic_pointed_at(database) as config:
            command.upgrade(config, "head")
        temp_engine = create_engine(_with_database(admin_url, database))
        yield temp_engine
    finally:
        if temp_engine is not None:
            temp_engine.dispose()
        _drop_database(admin_engine, database)
        admin_engine.dispose()


def _install_extensions(url: URL) -> None:
    """마이그레이션이 전제하는 확장을 임시 DB에 깐다.

    운영 DB에서는 이 확장들이 마이그레이션 밖에서 설치되어 있다.
    빈 DB에는 없으므로 upgrade 전에 직접 깔아 준다.
    """
    engine = create_engine(url, isolation_level="AUTOCOMMIT")
    try:
        with engine.connect() as connection:
            for extension in ("vector", "pg_bigm"):
                connection.execute(
                    text(f"CREATE EXTENSION IF NOT EXISTS {extension}")
                )
    except DBAPIError as error:
        pytest.skip(f"확장을 설치할 수 없어 통합 테스트를 건너뛴다: {error}")
    finally:
        engine.dispose()


def _drop_database(admin_engine: Engine, database: str) -> None:
    """임시 DB를 지운다. FORCE가 없는 판에서는 세션을 끊고 지운다."""
    with admin_engine.connect() as connection:
        try:
            connection.execute(
                text(f'DROP DATABASE IF EXISTS "{database}" WITH (FORCE)')
            )
            return
        except DBAPIError:
            pass
        connection.execute(
            text(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity"
                " WHERE datname = :database AND pid <> pg_backend_pid()"
            ).bindparams(database=database)
        )
        connection.execute(text(f'DROP DATABASE IF EXISTS "{database}"'))


def _seed_tenant(session: Session) -> tuple[int, int]:
    """빈 임시 DB에 회사·워크스페이스·사용자를 심는다."""
    company = Company(name="마이그레이션 테스트")
    session.add(company)
    session.flush()

    workspace = Workspace(name="마이그레이션 워크스페이스", company_id=company.id)
    user = User(
        email=f"migration-{uuid.uuid4().hex[:8]}@example.com",
        name="마이그레이션 사용자",
        provider="google",
        status=UserStatus.ACTIVE,
    )
    session.add_all([workspace, user])
    session.flush()

    return workspace.id, user.id


def _seed(session: Session, workspace_id: int, user_id: int) -> dict:
    """정의 기반 문서 둘과 정의 없는 문서 하나를 심는다.

    두 문서는 채널이 다른 두 정의 아래 같은 (kind, 대상)을 쓴다. 옛 전역
    UNIQUE로는 담을 수 없는 상태이며, downgrade가 거부해야 할 상태다.
    """
    channel_ids = [uuid.uuid4(), uuid.uuid4()]
    definition_ids = [uuid.uuid4(), uuid.uuid4()]
    subject_node_id = uuid.uuid4()
    legacy_subject_node_id = uuid.uuid4()
    artifact_ids = [uuid.uuid4(), uuid.uuid4()]
    legacy_artifact_id = uuid.uuid4()

    for channel_id in channel_ids:
        session.add(
            Channel(
                id=channel_id,
                workspace_id=workspace_id,
                name=f"채널-{uuid.uuid4().hex[:8]}",
                created_by=user_id,
            )
        )
    for node_id in (subject_node_id, legacy_subject_node_id):
        session.add(
            NodeRow(
                id=node_id,
                workspace_id=workspace_id,
                node_kind="entity",
                entity_type="feature",
                canonical_key=f"migration:feature:{uuid.uuid4().hex}",
                display_name="결제 기능",
            )
        )
    session.flush()

    for definition_id, channel_id in zip(definition_ids, channel_ids):
        session.add(
            ArtifactDefinition(
                id=definition_id,
                workspace_id=workspace_id,
                channel_id=channel_id,
                kind=ARTIFACT_KIND,
                selection_spec=SELECTION_SPEC,
                created_by=user_id,
            )
        )
    session.flush()

    for artifact_id, definition_id, channel_id in zip(
        artifact_ids, definition_ids, channel_ids
    ):
        session.add(
            KnowledgeArtifact(
                id=artifact_id,
                workspace_id=workspace_id,
                kind=ARTIFACT_KIND,
                channel_id=channel_id,
                definition_id=definition_id,
                subject_node_id=subject_node_id,
                title="결제 기능",
            )
        )
    session.add(
        KnowledgeArtifact(
            id=legacy_artifact_id,
            workspace_id=workspace_id,
            kind=ARTIFACT_KIND,
            subject_node_id=legacy_subject_node_id,
            title="정의 이전 문서",
        )
    )
    session.commit()

    return {
        "channel_ids": channel_ids,
        "node_ids": [subject_node_id, legacy_subject_node_id],
        "artifact_ids": artifact_ids,
        "legacy_artifact_id": legacy_artifact_id,
    }


@pytest.fixture(scope="module")
def seeded(engine: Engine) -> dict:
    """임시 DB에 정의 기반 문서 둘과 정의 이전 문서 하나를 한 번만 심는다."""
    with Session(engine) as session:
        workspace_id, user_id = _seed_tenant(session)
        return _seed(session, workspace_id, user_id)


def _temp_database(engine: Engine) -> str:
    """임시 DB를 보고 있는지 확인하고 그 이름을 준다."""
    database = engine.url.database
    assert database is not None
    assert database.startswith("catchup_migration_test_")
    return database


def _alembic_version(engine: Engine) -> str:
    """임시 DB가 지금 어느 리비전에 서 있는지 읽는다."""
    with engine.connect() as connection:
        return connection.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar_one()


def _scalar(engine: Engine, query: str) -> int:
    """단일 값을 세는 질의를 돌린다."""
    with engine.connect() as connection:
        return connection.execute(text(query)).scalar_one()


def _clear(
    engine: Engine,
    *,
    artifacts: bool = False,
    definitions: bool = False,
    channel_settings: bool = False,
) -> None:
    """사람이 손으로 정리하는 행위를 흉내 낸다.

    각 테스트가 자기 전제를 직접 만들게 해서 실행 순서에 기대지 않는다.
    """
    with Session(engine) as session:
        if artifacts:
            session.execute(
                text(
                    "DELETE FROM knowledge_artifacts"
                    " WHERE definition_id IS NOT NULL"
                )
            )
        if definitions:
            session.execute(text("DELETE FROM artifact_definitions"))
        if channel_settings:
            session.execute(
                text(
                    "UPDATE channels SET purpose_preset = NULL,"
                    " purpose_text = NULL, style_preset = NULL,"
                    " style_text = NULL"
                )
            )
        session.commit()


def _surviving_artifact_ids(engine: Engine, seeded: dict) -> set:
    """심은 문서 중 아직 남아 있는 id를 모은다."""
    with engine.connect() as connection:
        return set(
            connection.execute(
                text(
                    "SELECT id FROM knowledge_artifacts"
                    " WHERE id = ANY(:ids)"
                ).bindparams(
                    ids=[
                        *seeded["artifact_ids"],
                        seeded["legacy_artifact_id"],
                    ]
                )
            ).scalars()
        )


def _expect_refusal(engine: Engine) -> str:
    """downgrade가 거부하는지 보고 메시지를 돌려준다.

    스키마·리비전이 그대로인지도 함께 본다. alembic이 마이그레이션을
    트랜잭션으로 감싸므로 거부는 아무것도 commit하지 않아야 한다.
    """
    database = _temp_database(engine)
    with _alembic_pointed_at(database) as config:
        with pytest.raises(RuntimeError) as error:
            command.downgrade(config, PREVIOUS_REVISION)

    assert inspect(engine).has_table(ArtifactDefinition.__tablename__)
    assert _alembic_version(engine) != PREVIOUS_REVISION
    return str(error.value)


def test_downgrade_refuses_definition_backed_documents(
    engine: Engine, seeded: dict
) -> None:
    """정의 기반 문서가 있으면 downgrade가 거부하고 아무것도 바꾸지 않는다."""
    message = _expect_refusal(engine)

    assert "정의 기반 문서 2건" in message
    assert "downgrade를 중단한다" in message
    assert "정리" in message

    assert _surviving_artifact_ids(engine, seeded) == {
        *seeded["artifact_ids"],
        seeded["legacy_artifact_id"],
    }


def test_downgrade_refuses_definitions_without_documents(
    engine: Engine, seeded: dict
) -> None:
    """문서를 아직 안 만든 정의 행만 있어도 거부한다.

    컴파일 러너를 돌리기 전 상태다. 문서만 세면 이 정의가 DROP TABLE과
    함께 조용히 사라진다.
    """
    _clear(engine, artifacts=True)

    message = _expect_refusal(engine)

    assert "아티팩트 정의 2건" in message
    assert "정의 기반 문서" not in message
    assert "downgrade를 중단한다" in message

    assert _scalar(engine, "SELECT count(*) FROM artifact_definitions") == 2


def test_downgrade_refuses_channel_settings(
    engine: Engine, seeded: dict
) -> None:
    """정의가 없어도 채널에 저장된 목적·문체 설정만으로 거부한다.

    설정 컬럼은 downgrade가 DROP COLUMN으로 걷어내므로, 값이 있으면
    사용자 입력이 말없이 사라진다.
    """
    _clear(engine, artifacts=True, definitions=True)
    channel_id = seeded["channel_ids"][0]
    with Session(engine) as session:
        session.execute(
            text(
                "UPDATE channels SET purpose_preset = :preset"
                " WHERE id = :id"
            ).bindparams(preset="voc.faq_consistency", id=channel_id)
        )
        session.commit()

    message = _expect_refusal(engine)

    assert "채널 목적·문체 설정 1건" in message
    assert "아티팩트 정의" not in message
    assert "downgrade를 중단한다" in message

    assert (
        _scalar(
            engine,
            "SELECT count(*) FROM channels WHERE purpose_preset IS NOT NULL",
        )
        == 1
    )


def test_downgrade_succeeds_on_clean_state(
    engine: Engine, seeded: dict
) -> None:
    """문서·정의·채널 설정을 사람이 다 걷어낸 뒤에는 왕복이 끝까지 돈다."""
    database = _temp_database(engine)
    _clear(
        engine, artifacts=True, definitions=True, channel_settings=True
    )

    with _alembic_pointed_at(database) as config:
        command.downgrade(config, PREVIOUS_REVISION)

        assert not inspect(engine).has_table(
            ArtifactDefinition.__tablename__
        )
        # 정의 이전 문서는 정리 대상이 아니므로 그대로 남는다.
        assert _surviving_artifact_ids(engine, seeded) == {
            seeded["legacy_artifact_id"]
        }

        command.upgrade(config, "head")

    assert inspect(engine).has_table(ArtifactDefinition.__tablename__)
