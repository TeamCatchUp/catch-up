"""seed 어휘 발행을 실 PostgreSQL 저장소로 확인한다.

어휘 스냅샷은 두 JSON 컬럼에 나눠 담기고 읽을 때 다시 조립된다. 대역
저장소는 넣은 객체를 그대로 돌려주므로 그 인코딩이 틀려도 드러나지
않는다. entry가 왕복을 지나 살아남는지는 실 DB로만 확인된다.
"""

from __future__ import annotations

import threading
import time
import uuid
from collections.abc import Callable
from collections.abc import Iterator

import pytest
from sqlalchemy import Connection
from sqlalchemy import Engine
from sqlalchemy import create_engine
from sqlalchemy import delete
from sqlalchemy import inspect
from sqlalchemy import select
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker

from catchup.configs.config import settings
from catchup.db.models import KnowledgeOntologySnapshot
from catchup.db.models import Workspace
from catchup.knowledge_maintenance.adapters.postgres.repositories import (
    SqlAlchemyOntologyRepository,
)
from catchup.knowledge_maintenance.adapters.postgres.unit_of_work import (
    KnowledgeMaintenanceUnitOfWork,
)
from catchup.knowledge_maintenance.contracts.extraction import EntityTypeEntry
from catchup.knowledge_maintenance.contracts.extraction import ExtractionVocabulary
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

    실 UnitOfWork에 물릴 수 있어야 한다. 별도 연결을 쓰면 커밋하지 않은
    테스트 데이터가 UoW 쪽에서 보이지 않는다.
    """
    return sessionmaker(
        bind=connection,
        join_transaction_mode="create_savepoint",
        expire_on_commit=False,
    )


def test_pg_publishes_and_reuses(
    session_factory: Callable[[], Session],
    workspace_ids: tuple[int, int],
) -> None:
    """실 저장소로 v1 발행 후 재실행이 무발행인지 본다."""
    workspace_id, _ = workspace_ids
    ontology_id = f"catchup.test-seed-{uuid.uuid4()}"

    with KnowledgeMaintenanceUnitOfWork(session_factory) as uow:
        first = install_seed_vocabulary(
            uow,
            workspace_id=workspace_id,
            seed=_VOC_SEED,
            ontology_id=ontology_id,
        )
        uow.commit()
    assert first == "v1"

    with KnowledgeMaintenanceUnitOfWork(session_factory) as uow:
        second = install_seed_vocabulary(
            uow,
            workspace_id=workspace_id,
            seed=_VOC_SEED,
            ontology_id=ontology_id,
        )
        uow.commit()
    assert second is None


def test_pg_roundtrip_keeps_entity_type_entries(
    session_factory: Callable[[], Session],
    workspace_ids: tuple[int, int],
) -> None:
    """entity type 엔트리가 저장·복원을 지나 그대로 살아남는다."""
    workspace_id, _ = workspace_ids
    ontology_id = f"catchup.test-seed-{uuid.uuid4()}"

    with KnowledgeMaintenanceUnitOfWork(session_factory) as uow:
        install_seed_vocabulary(
            uow,
            workspace_id=workspace_id,
            seed=_VOC_SEED,
            ontology_id=ontology_id,
        )
        uow.commit()
        stored = uow.ontology.get(
            workspace_id=workspace_id,
            ontology_id=ontology_id,
            version="v1",
        )

    assert stored.entity_type_entry("customer").identity_scope == "anchored"
    assert stored.predicate_entry("request_status").enum_values[0] == "proposed"


def test_pg_second_workspace_starts_its_own_lineage(
    session_factory: Callable[[], Session],
    workspace_ids: tuple[int, int],
) -> None:
    """workspace가 다르면 계보도 따로 v1부터 시작한다."""
    first_workspace, second_workspace = workspace_ids
    ontology_id = f"catchup.test-seed-{uuid.uuid4()}"

    with KnowledgeMaintenanceUnitOfWork(session_factory) as uow:
        install_seed_vocabulary(
            uow,
            workspace_id=first_workspace,
            seed=_VOC_SEED,
            ontology_id=ontology_id,
        )
        other = install_seed_vocabulary(
            uow,
            workspace_id=second_workspace,
            seed=_VOC_SEED,
            ontology_id=ontology_id,
        )
        uow.commit()

    assert other == "v1"


def _seed_with_entity_type(name: str) -> ExtractionVocabulary:
    """entity 종류 하나만 담은 seed를 만든다."""
    return ExtractionVocabulary(
        entity_type_entries=(
            EntityTypeEntry(
                name=name,
                definition=f"{name} 동시 발행 확인용 종류다.",
                identity_scope="standalone",
            ),
        )
    )


def test_pg_concurrent_publishers_serialize_into_two_versions(
    engine: Engine,
    workspace_ids: tuple[int, int],
) -> None:
    """같은 계보에 동시에 들어온 두 발행이 v1·v2로 줄 서서 끝난다.

    커밋이 실제로 겹쳐야 하는 상황이라 되감는 연결을 쓰지 못한다. 그래서
    연결을 따로 열고 커밋한 뒤 남은 행을 직접 지운다.
    """
    workspace_id, _ = workspace_ids
    ontology_id = f"catchup.test-seed-{uuid.uuid4()}"

    first_holds_lock = threading.Event()
    release_first = threading.Event()
    versions: dict[str, str | None] = {}
    failures: list[BaseException] = []

    def publish(
        label: str,
        seed: ExtractionVocabulary,
        *,
        wait: bool,
    ) -> None:
        factory = sessionmaker(bind=engine, expire_on_commit=False)
        try:
            with KnowledgeMaintenanceUnitOfWork(factory) as uow:
                versions[label] = install_seed_vocabulary(
                    uow,
                    workspace_id=workspace_id,
                    seed=seed,
                    ontology_id=ontology_id,
                )
                if wait:
                    first_holds_lock.set()
                    release_first.wait(timeout=10)
                uow.commit()
        except BaseException as error:  # noqa: BLE001
            # 스레드 안에서 터진 것을 본문으로 날라야 원인이 드러난다.
            failures.append(error)
            first_holds_lock.set()

    first = threading.Thread(
        target=publish,
        args=("first", _seed_with_entity_type("alpha_topic")),
        kwargs={"wait": True},
    )
    second = threading.Thread(
        target=publish,
        args=("second", _seed_with_entity_type("beta_topic")),
        kwargs={"wait": False},
    )

    try:
        first.start()
        assert first_holds_lock.wait(timeout=10)
        second.start()
        # 두 번째가 잠금 앞에서 실제로 멈출 틈을 준다. 이 틈이 없으면
        # 첫 번째가 먼저 커밋해 버려 경합이 재현되지 않는다.
        time.sleep(0.5)
        release_first.set()
        first.join(timeout=15)
        second.join(timeout=15)

        assert not first.is_alive()
        assert not second.is_alive()
        assert failures == []
        assert sorted(versions.values()) == ["v1", "v2"]

        with sessionmaker(bind=engine)() as session:
            latest = SqlAlchemyOntologyRepository(session).get(
                workspace_id=workspace_id,
                ontology_id=ontology_id,
                version="v2",
            )
        names = {entry.name for entry in latest.entity_type_entries}
        assert names == {"alpha_topic", "beta_topic"}
    finally:
        release_first.set()
        first.join(timeout=15)
        second.join(timeout=15)
        with engine.begin() as cleanup:
            cleanup.execute(
                delete(KnowledgeOntologySnapshot).where(
                    KnowledgeOntologySnapshot.ontology_id == ontology_id
                )
            )
