"""이미 열린 세션 위에 얹는 어휘 UnitOfWork 어댑터를 실 PG로 확인한다.

이 어댑터의 존재 이유는 트랜잭션 경계를 호출자에게 넘기는 것이다. 그
성질은 대역 세션으로는 드러나지 않는다 — 커밋하지 않은 쓰기가 같은
트랜잭션 안에서 보이는지, 롤백이 그것을 되돌리는지는 실 DB에서만
확인된다.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from collections.abc import Iterator

import pytest
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
from catchup.db.models import KnowledgeOntologySnapshot
from catchup.db.models import Workspace
from catchup.knowledge_maintenance.adapters.postgres.session_bound import (
    SessionBoundOntologyUnitOfWork,
)
from catchup.knowledge_maintenance.domain.preset_catalog import _VOC_SEED
from catchup.knowledge_maintenance.services.install_seed_vocabulary import (
    install_seed_vocabulary,
)


@pytest.fixture(scope="module")
def engine() -> Iterator[Engine]:
    engine = create_engine(settings.sqlalchemy_database_url)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except OperationalError:
        engine.dispose()
        pytest.skip("PostgreSQL이 없어 통합 테스트를 건너뛴다.")

    if not inspect(engine).has_table(KnowledgeOntologySnapshot.__tablename__):
        engine.dispose()
        pytest.skip("어휘 스냅샷 테이블이 없다. alembic upgrade head가 필요하다.")

    yield engine
    engine.dispose()


@pytest.fixture(scope="module")
def workspace_ids(engine: Engine) -> tuple[int, int]:
    """실 DB에 있는 workspace 두 개를 빌린다.

    workspace를 새로 만들려면 company까지 함께 만들어야 하고, 그것은 이
    테스트가 검증하려는 것과 무관한 사전 준비다.
    """
    with engine.connect() as connection:
        found = (
            connection.execute(select(Workspace.id).order_by(Workspace.id).limit(2))
            .scalars()
            .all()
        )

    if len(found) < 2:
        pytest.skip("workspace가 둘 이상 없어 통합 테스트를 건너뛴다.")
    return found[0], found[1]


@pytest.fixture
def connection(engine: Engine) -> Iterator[Connection]:
    """테스트마다 되감는 연결 하나를 만든다.

    바깥 트랜잭션을 롤백하므로 여기서 발행한 스냅샷 행은 남지 않는다.
    """
    connection = engine.connect()
    transaction = connection.begin()

    yield connection

    transaction.rollback()
    connection.close()


@pytest.fixture
def session_factory(connection: Connection) -> Callable[[], Session]:
    """같은 트랜잭션 위에 세션을 여는 factory를 만든다.

    별도 연결을 쓰면 커밋하지 않은 테스트 데이터가 보이지 않는다.
    """
    return sessionmaker(
        bind=connection,
        join_transaction_mode="create_savepoint",
        expire_on_commit=False,
    )


@pytest.fixture
def db(session_factory: Callable[[], Session]) -> Iterator[Session]:
    """요청 세션 자리에 설 세션 하나를 연다.

    웹 프레임워크가 요청마다 열어 넘기는 세션과 같은 자리다 — 어댑터는
    이 세션을 열지도 닫지도 않는다.
    """
    session = session_factory()
    yield session
    session.close()


def test_writes_land_in_the_callers_transaction(
    db: Session,
    workspace_ids: tuple[int, int],
) -> None:
    """이 어댑터로 쓴 어휘가 호출자 세션의 트랜잭션 안에서 보인다."""
    workspace_id, _ = workspace_ids
    ontology_id = f"catchup.test-bound-{uuid.uuid4()}"
    uow = SessionBoundOntologyUnitOfWork(db)
    install_seed_vocabulary(
        uow,
        workspace_id=workspace_id,
        seed=_VOC_SEED,
        ontology_id=ontology_id,
    )
    found = uow.ontology.get(
        workspace_id=workspace_id,
        ontology_id=ontology_id,
        version="v1",
    )
    assert found is not None


def test_rollback_by_the_caller_undoes_the_publish(
    db: Session,
    workspace_ids: tuple[int, int],
) -> None:
    """호출자가 롤백하면 발행도 함께 사라진다."""
    workspace_id, _ = workspace_ids
    ontology_id = f"catchup.test-bound-{uuid.uuid4()}"
    uow = SessionBoundOntologyUnitOfWork(db)
    install_seed_vocabulary(
        uow,
        workspace_id=workspace_id,
        seed=_VOC_SEED,
        ontology_id=ontology_id,
    )
    db.rollback()
    assert (
        uow.ontology.list_versions(
            workspace_id=workspace_id,
            ontology_id=ontology_id,
        )
        == ()
    )


def test_adapter_has_no_commit() -> None:
    """트랜잭션 경계를 여기서 끊을 수 없음을 표면으로 못박는다."""
    assert not hasattr(SessionBoundOntologyUnitOfWork, "commit")
