"""어휘 수렴 발행이 seed 설치와 겹칠 때를 실 PostgreSQL로 확인한다.

수렴 러너는 기준 사전을 읽고 트랜잭션을 닫은 뒤 LLM을 부른다. 그 사이에
온보딩이 같은 계보에 seed를 발행할 수 있다. 대역 저장소로는 잠금도
커밋 순서도 재현되지 않으므로 실 DB로만 확인된다.
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
from sqlalchemy.exc import IntegrityError
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
from catchup.knowledge_maintenance.contracts.extraction import ExtractionVocabulary
from catchup.knowledge_maintenance.contracts.extraction import PredicateEntry
from catchup.knowledge_maintenance.domain.preset_catalog import _VOC_SEED
from catchup.knowledge_maintenance.services.converge_vocabulary import (
    ConvergenceGuardResult,
)
from catchup.knowledge_maintenance.services.converge_vocabulary import (
    publish_converged_vocabulary,
)
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
def workspace_id(engine: Engine) -> int:
    """실 DB에 있는 workspace 하나를 빌린다.

    workspace를 새로 만들려면 company까지 함께 만들어야 하고, 그것은 이
    테스트가 검증하려는 것과 무관한 사전 준비다. 계보는 매번 새로 만든
    `ontology_id`로 갈라 둔다.
    """
    with engine.connect() as connection:
        found = connection.execute(
            select(Workspace.id).order_by(Workspace.id).limit(1)
        ).scalar_one_or_none()

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


def _guarded() -> ConvergenceGuardResult:
    """predicate 하나가 통과한 가드 결과를 만든다. LLM은 부르지 않는다."""
    return ConvergenceGuardResult(
        predicate_entries=(
            PredicateEntry(
                name="release_channel",
                definition="배포 채널을 담는다.",
                value_type="text",
            ),
        ),
        relation_entries=(),
        absorptions=(),
        rejections=(),
        covered_names=("release_channel",),
    )


def test_pg_seed가_먼저_발행되면_빈_기준_수렴은_거부된다(
    session_factory: Callable[[], Session],
    workspace_id: int,
) -> None:
    """러너가 기준을 읽은 뒤 온보딩이 v1을 발행한 상황을 재현한다.

    빈 기준 위에 그대로 쌓으면 새 최신본에 seed 항목이 하나도 없다.
    """
    ontology_id = f"catchup.test-converge-{uuid.uuid4()}"

    # 세션 A: 계보가 없을 때 기준 사전을 읽고 트랜잭션을 닫는다.
    with KnowledgeMaintenanceUnitOfWork(session_factory) as reader:
        versions = reader.ontology.list_versions(
            workspace_id=workspace_id,
            ontology_id=ontology_id,
        )
    assert versions == ()
    current = ExtractionVocabulary()

    # 세션 B: 그 사이 온보딩이 seed를 v1으로 발행한다.
    with KnowledgeMaintenanceUnitOfWork(session_factory) as uow:
        seeded = install_seed_vocabulary(
            uow,
            workspace_id=workspace_id,
            seed=_VOC_SEED,
            ontology_id=ontology_id,
        )
        uow.commit()
    assert seeded == "v1"

    # 세션 A가 낡은 기준으로 발행을 시도한다.
    with pytest.raises(RuntimeError, match="발행본이 없었는데"):
        publish_converged_vocabulary(
            _guarded(),
            workspace_id=workspace_id,
            ontology_id=ontology_id,
            current=current,
            uow=KnowledgeMaintenanceUnitOfWork(session_factory),
        )

    with KnowledgeMaintenanceUnitOfWork(session_factory) as reader:
        after = reader.ontology.list_versions(
            workspace_id=workspace_id,
            ontology_id=ontology_id,
        )
        latest = reader.ontology.get(
            workspace_id=workspace_id,
            ontology_id=ontology_id,
            version="v1",
        )

    assert after == ("v1",)
    assert latest is not None
    assert {entry.name for entry in latest.entity_type_entries} == {
        entry.name for entry in _VOC_SEED.entity_type_entries
    }


def test_pg_잠금이_겹친_수렴_발행은_seed를_잃지_않는다(
    engine: Engine,
    workspace_id: int,
) -> None:
    """seed 설치가 잠금을 쥔 채 수렴 발행이 들어와도 seed가 남는다.

    커밋이 실제로 겹쳐야 하는 상황이라 되감는 연결을 쓰지 못한다. 그래서
    연결을 따로 열고 커밋한 뒤 남은 행을 직접 지운다.
    """
    ontology_id = f"catchup.test-converge-{uuid.uuid4()}"

    seed_holds_lock = threading.Event()
    release_seed = threading.Event()
    failures: list[BaseException] = []
    publish_error: list[BaseException] = []

    def install() -> None:
        factory = sessionmaker(bind=engine, expire_on_commit=False)
        try:
            with KnowledgeMaintenanceUnitOfWork(factory) as uow:
                install_seed_vocabulary(
                    uow,
                    workspace_id=workspace_id,
                    seed=_VOC_SEED,
                    ontology_id=ontology_id,
                )
                seed_holds_lock.set()
                release_seed.wait(timeout=10)
                uow.commit()
        except BaseException as error:  # noqa: BLE001
            # 스레드 안에서 터진 것을 본문으로 날라야 원인이 드러난다.
            failures.append(error)
            seed_holds_lock.set()

    def publish() -> None:
        factory = sessionmaker(bind=engine, expire_on_commit=False)
        try:
            publish_converged_vocabulary(
                _guarded(),
                workspace_id=workspace_id,
                ontology_id=ontology_id,
                current=ExtractionVocabulary(),
                uow=KnowledgeMaintenanceUnitOfWork(factory),
            )
        except BaseException as error:  # noqa: BLE001
            publish_error.append(error)

    installer = threading.Thread(target=install)
    publisher = threading.Thread(target=publish)

    try:
        installer.start()
        assert seed_holds_lock.wait(timeout=10)
        publisher.start()
        # 발행 쪽이 잠금 앞에서 실제로 멈출 틈을 준다. 이 틈이 없으면
        # seed 쪽이 먼저 커밋해 버려 경합이 재현되지 않는다.
        time.sleep(0.5)
        release_seed.set()
        installer.join(timeout=15)
        publisher.join(timeout=15)

        assert not installer.is_alive()
        assert not publisher.is_alive()
        assert failures == []
        # 잠금이 없으면 둘 다 v1을 세어 버전 UNIQUE 제약에 걸린다.
        assert not any(
            isinstance(error, IntegrityError) for error in publish_error
        )
        # 발행 쪽은 잠금이 풀린 뒤에야 v1을 보므로, 성공하거나 낡은
        # 기준으로 거부되거나 둘 중 하나다.
        assert all(
            isinstance(error, RuntimeError) for error in publish_error
        )

        with sessionmaker(bind=engine)() as session:
            repository = SqlAlchemyOntologyRepository(session)
            versions = repository.list_versions(
                workspace_id=workspace_id,
                ontology_id=ontology_id,
            )
            latest = repository.get(
                workspace_id=workspace_id,
                ontology_id=ontology_id,
                version=max(versions),
            )

        seed_names = {entry.name for entry in _VOC_SEED.entity_type_entries}
        assert seed_names <= {
            entry.name for entry in latest.entity_type_entries
        }
    finally:
        release_seed.set()
        installer.join(timeout=15)
        publisher.join(timeout=15)
        with engine.begin() as cleanup:
            cleanup.execute(
                delete(KnowledgeOntologySnapshot).where(
                    KnowledgeOntologySnapshot.ontology_id == ontology_id
                )
            )
