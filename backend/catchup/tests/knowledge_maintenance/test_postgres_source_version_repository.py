from __future__ import annotations

import uuid
from collections.abc import Callable
from collections.abc import Iterator
from datetime import datetime
from datetime import timezone

import pytest
from sqlalchemy import Engine
from sqlalchemy import create_engine
from sqlalchemy import func
from sqlalchemy import inspect
from sqlalchemy import select
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker

from catchup.configs.config import settings
from catchup.db.models import SourceVersion as SourceVersionRow
from catchup.db.models import Workspace
from catchup.knowledge_maintenance.adapters.postgres.unit_of_work import (
    SqlAlchemySourceVersionUnitOfWork,
)
from catchup.knowledge_maintenance.contracts.source_change import SourceChangeEnvelope
from catchup.knowledge_maintenance.domain.source_version import ChangeKind
from catchup.knowledge_maintenance.domain.source_version import SourceIdentity
from catchup.knowledge_maintenance.domain.source_version import SourceVersion
from catchup.knowledge_maintenance.services.ingest_source_version import IngestionResult
from catchup.knowledge_maintenance.services.ingest_source_version import (
    SourceVersionPayloadConflict,
)
from catchup.knowledge_maintenance.services.ingest_source_version import (
    ingest_source_change,
)

NOW = datetime(2026, 7, 28, 9, 0, tzinfo=timezone.utc)
# source_versions.workspace_id는 workspaces를 참조하므로 실재하는 workspace를
# 빌려 쓰고, 실제로 쌓이는 데이터와는 source_type으로 갈라 둔다.
SOURCE_TYPE = "test-knowledge-maintenance"
IDEMPOTENCY_KEY = "test-source:CAM-180:38"


@pytest.fixture(scope="module")
def engine() -> Iterator[Engine]:
    """로컬 PostgreSQL에 연결한다.

    테이블은 마이그레이션이 만든 것을 쓴다. 테스트가 직접 만들면
    autogenerate가 변경을 잡지 못하고 upgrade도 충돌한다.
    """
    engine = create_engine(settings.sqlalchemy_database_url)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except OperationalError:
        engine.dispose()
        pytest.skip("PostgreSQL이 없어 통합 테스트를 건너뛴다.")

    inspector = inspect(engine)
    if not inspector.has_table(SourceVersionRow.__tablename__):
        engine.dispose()
        pytest.skip("source_versions 테이블이 없다. alembic upgrade head가 필요하다.")

    yield engine
    engine.dispose()


@pytest.fixture(scope="module")
def workspace_id(engine: Engine) -> int:
    """foreign key를 만족할 실재 workspace를 하나 고른다."""
    with engine.connect() as connection:
        found = connection.execute(
            select(Workspace.id).order_by(Workspace.id).limit(1)
        ).scalar()

    if found is None:
        pytest.skip("workspace가 없어 통합 테스트를 건너뛴다.")
    return found


@pytest.fixture
def session_factory(engine: Engine) -> Iterator[Callable[[], Session]]:
    """테스트가 끝나면 전부 되돌아가는 session 팩토리를 만든다.

    바깥 transaction 안에 session을 묶어, commit은 savepoint로만
    반영되고 실제 데이터는 남지 않는다.
    """
    connection = engine.connect()
    transaction = connection.begin()

    yield sessionmaker(
        bind=connection,
        join_transaction_mode="create_savepoint",
        expire_on_commit=False,
    )

    transaction.rollback()
    connection.close()


@pytest.fixture
def uow_factory(
    session_factory: Callable[[], Session],
) -> Callable[[], SqlAlchemySourceVersionUnitOfWork]:
    """같은 transaction을 공유하는 UnitOfWork 팩토리를 만든다."""
    return lambda: SqlAlchemySourceVersionUnitOfWork(session_factory)


def _source_version(workspace_id: int, **overrides: object) -> SourceVersion:
    values: dict[str, object] = {
        "id": uuid.UUID("00000000-0000-0000-0000-000000000001"),
        "workspace_id": workspace_id,
        "source_type": SOURCE_TYPE,
        "source_identity": SourceIdentity(
            entity_type="issue",
            scope_id="team-catchup",
            target_id="CAM",
            external_document_id="CAM-180",
        ),
        "change_kind": ChangeKind.UPDATED,
        "source_version_key": "38",
        "title": "결제 기능 출시 일정",
        "canonical_url": "https://jira.example.com/browse/CAM-180",
        "content": "결제 기능은 9월 출시 예정이다.",
        "content_type": "text/markdown",
        "content_hash": "a" * 64,
        "source_updated_at": NOW,
        "observed_at": NOW,
        "idempotency_key": IDEMPOTENCY_KEY,
        "payload_hash": "b" * 64,
        "metadata": {"labels": ["billing"]},
        "created_at": NOW,
    }
    values.update(overrides)
    return SourceVersion(**values)  # type: ignore[arg-type]


def _envelope(workspace_id: int, **overrides: object) -> SourceChangeEnvelope:
    values: dict[str, object] = {
        "schema_version": 1,
        "event_id": "event-1",
        "workspace_id": workspace_id,
        "source_type": SOURCE_TYPE,
        "source_identity": {
            "entity_type": "issue",
            "scope_id": "team-catchup",
            "target_id": "CAM",
            "external_document_id": "CAM-180",
        },
        "change_kind": "updated",
        "source_version_key": "38",
        "title": "결제 기능 출시 일정",
        "canonical_url": "https://jira.example.com/browse/CAM-180",
        "content": "결제 기능은 9월 출시 예정이다.",
        "content_type": "text/markdown",
        "source_updated_at": NOW,
        "observed_at": NOW,
        "idempotency_key": IDEMPOTENCY_KEY,
        "metadata": {},
    }
    values.update(overrides)
    return SourceChangeEnvelope.model_validate(values)


def _store(
    uow_factory: Callable[[], SqlAlchemySourceVersionUnitOfWork],
    source_version: SourceVersion,
) -> None:
    """SourceVersion 한 건을 커밋한다."""
    with uow_factory() as uow:
        uow.source_versions.add(source_version)
        uow.commit()


def _stored_row_count(
    session_factory: Callable[[], Session],
    workspace_id: int,
) -> int:
    """테스트가 만든 SourceVersion row 수를 센다."""
    with session_factory() as session:
        count = session.scalar(
            select(func.count())
            .select_from(SourceVersionRow)
            .where(
                SourceVersionRow.workspace_id == workspace_id,
                SourceVersionRow.source_type == SOURCE_TYPE,
            )
        )
    return count or 0


def test_stored_source_version_is_read_back_unchanged(
    uow_factory: Callable[[], SqlAlchemySourceVersionUnitOfWork],
    workspace_id: int,
) -> None:
    source_version = _source_version(workspace_id)

    _store(uow_factory, source_version)

    with uow_factory() as uow:
        loaded = uow.source_versions.get_by_idempotency_key(
            workspace_id=workspace_id,
            idempotency_key=IDEMPOTENCY_KEY,
        )

    assert loaded == source_version


def test_same_source_version_is_found_by_another_delivery_key(
    uow_factory: Callable[[], SqlAlchemySourceVersionUnitOfWork],
    workspace_id: int,
) -> None:
    source_version = _source_version(workspace_id)
    _store(uow_factory, source_version)

    with uow_factory() as uow:
        loaded = uow.source_versions.get_by_source_version(
            workspace_id=workspace_id,
            source_type=SOURCE_TYPE,
            source_identity=source_version.source_identity,
            source_version_key="38",
        )

    assert loaded == source_version


def test_latest_for_source_returns_the_newest_source_update(
    uow_factory: Callable[[], SqlAlchemySourceVersionUnitOfWork],
    workspace_id: int,
) -> None:
    older = _source_version(
        workspace_id,
        id=uuid.UUID("00000000-0000-0000-0000-000000000010"),
        source_version_key="37",
        idempotency_key="test-source:CAM-180:37",
        source_updated_at=datetime(2026, 7, 27, 9, 0, tzinfo=timezone.utc),
    )
    newer = _source_version(
        workspace_id,
        id=uuid.UUID("00000000-0000-0000-0000-000000000011"),
        source_version_key="39",
        idempotency_key="test-source:CAM-180:39",
        source_updated_at=datetime(2026, 7, 29, 9, 0, tzinfo=timezone.utc),
    )
    _store(uow_factory, newer)
    _store(uow_factory, older)

    with uow_factory() as uow:
        latest = uow.source_versions.get_latest_for_source(
            workspace_id=workspace_id,
            source_type=SOURCE_TYPE,
            source_identity=newer.source_identity,
        )

    assert latest == newer


def test_source_version_lookup_is_scoped_by_workspace(
    uow_factory: Callable[[], SqlAlchemySourceVersionUnitOfWork],
    workspace_id: int,
) -> None:
    source_version = _source_version(workspace_id)
    _store(uow_factory, source_version)

    with uow_factory() as uow:
        loaded = uow.source_versions.get_by_source_version(
            workspace_id=workspace_id + 10_000,
            source_type=SOURCE_TYPE,
            source_identity=source_version.source_identity,
            source_version_key="38",
        )

    assert loaded is None


def test_ingested_envelope_is_stored_in_postgres(
    uow_factory: Callable[[], SqlAlchemySourceVersionUnitOfWork],
    workspace_id: int,
) -> None:
    result = ingest_source_change(_envelope(workspace_id), uow=uow_factory())

    assert result.result == IngestionResult.CREATED
    with uow_factory() as uow:
        stored = uow.source_versions.get_by_idempotency_key(
            workspace_id=workspace_id,
            idempotency_key=IDEMPOTENCY_KEY,
        )
    assert stored is not None
    assert stored.id == result.source_version_id
    assert stored.content_hash is not None


def test_redelivered_envelope_does_not_store_a_second_row(
    uow_factory: Callable[[], SqlAlchemySourceVersionUnitOfWork],
    session_factory: Callable[[], Session],
    workspace_id: int,
) -> None:
    first = ingest_source_change(_envelope(workspace_id), uow=uow_factory())

    redelivered = _envelope(workspace_id, event_id="event-retry")
    second = ingest_source_change(redelivered, uow=uow_factory())

    assert second.result == IngestionResult.DUPLICATE
    assert second.source_version_id == first.source_version_id
    assert _stored_row_count(session_factory, workspace_id) == 1


def test_reused_delivery_key_with_another_payload_is_rejected(
    uow_factory: Callable[[], SqlAlchemySourceVersionUnitOfWork],
    session_factory: Callable[[], Session],
    workspace_id: int,
) -> None:
    ingest_source_change(_envelope(workspace_id), uow=uow_factory())

    # 전달 키는 그대로인데 원문이 다른 버전을 가리키는 경우다.
    # idempotency 조회가 살아 있어야 UNIQUE 위반 전에 걸러진다.
    conflicting = _envelope(
        workspace_id,
        event_id="event-conflict",
        source_version_key="39",
        content="결제 기능은 10월 출시 예정이다.",
    )

    with pytest.raises(SourceVersionPayloadConflict):
        ingest_source_change(conflicting, uow=uow_factory())

    assert _stored_row_count(session_factory, workspace_id) == 1
