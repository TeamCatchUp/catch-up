from __future__ import annotations

import uuid
from collections.abc import Callable
from collections.abc import Iterator
from datetime import datetime
from datetime import timezone

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
from catchup.db.models import Observation as ObservationRow
from catchup.db.models import Workspace
from catchup.knowledge_maintenance.adapters.postgres.unit_of_work import (
    KnowledgeMaintenanceUnitOfWork,
)
from catchup.knowledge_maintenance.domain.observation import MetadataEntity
from catchup.knowledge_maintenance.domain.observation import NormalizedObservation
from catchup.knowledge_maintenance.domain.observation import ObservationKind
from catchup.knowledge_maintenance.domain.observation import content_hash
from catchup.knowledge_maintenance.domain.source_version import ChangeKind
from catchup.knowledge_maintenance.domain.source_version import SourceIdentity
from catchup.knowledge_maintenance.domain.source_version import SourceVersion
from catchup.knowledge_maintenance.services.normalize_source_version import (
    NormalizationResult,
)
from catchup.knowledge_maintenance.services.normalize_source_version import (
    normalize_source_version,
)

NOW = datetime(2026, 7, 28, 9, 0, tzinfo=timezone.utc)
OCCURRED_AT = datetime(2026, 6, 9, 9, 0, tzinfo=timezone.utc)
SOURCE_TYPE = "test-knowledge-maintenance"
NORMALIZED_CONTENT = "고객: 결제 기능은 언제 나오나요?\n상담원: 9월 예정입니다."


@pytest.fixture(scope="module")
def engine() -> Iterator[Engine]:
    """로컬 PostgreSQL에 연결한다."""
    engine = create_engine(settings.sqlalchemy_database_url)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except OperationalError:
        engine.dispose()
        pytest.skip("PostgreSQL이 없어 통합 테스트를 건너뛴다.")

    inspector = inspect(engine)
    if not inspector.has_table(ObservationRow.__tablename__):
        engine.dispose()
        pytest.skip("observations 테이블이 없다. alembic upgrade head가 필요하다.")

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
    """테스트가 끝나면 전부 되돌아가는 session 팩토리를 만든다."""
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
) -> Callable[[], KnowledgeMaintenanceUnitOfWork]:
    return lambda: KnowledgeMaintenanceUnitOfWork(session_factory)


class _StubNormalizer:
    """정해진 결과만 돌려주는 normalizer다."""

    def __init__(
        self,
        *,
        normalizer_id: str = "test.normalizer",
        normalizer_version: str = "1",
        observation: NormalizedObservation | None = None,
    ) -> None:
        self.normalizer_id = normalizer_id
        self.normalizer_version = normalizer_version
        self.calls = 0
        self._observation = observation

    def normalize(self, source_version: SourceVersion) -> NormalizedObservation:
        self.calls += 1
        if self._observation is not None:
            return self._observation
        return _observation(
            normalizer_id=self.normalizer_id,
            normalizer_version=self.normalizer_version,
        )


def _observation(**overrides: object) -> NormalizedObservation:
    values: dict[str, object] = {
        "normalizer_id": "test.normalizer",
        "normalizer_version": "1",
        "observation_kind": ObservationKind.DOCUMENT,
        "content": NORMALIZED_CONTENT,
        "content_hash": content_hash(NORMALIZED_CONTENT),
        "source_attributes": {
            "state": "closed",
            "tags": ["요금", "도입"],
            "message_counts": {"total": 4, "private": 0},
        },
        "metadata_entities": (
            MetadataEntity(
                entity_type="channel_talk_user",
                external_key="user-abc",
                display_name="사용자 008",
                attributes={"user_type": "user"},
            ),
            MetadataEntity(
                entity_type="channel_talk_manager",
                external_key="manager-xyz",
                display_name="캐치업 팀",
                attributes={"is_assignee": True},
            ),
        ),
        "occurred_at": OCCURRED_AT,
    }
    values.update(overrides)
    return NormalizedObservation(**values)  # type: ignore[arg-type]


def _persisted_source_version(
    workspace_id: int,
    session_factory: Callable[[], Session],
    **overrides: object,
) -> SourceVersion:
    """Observation이 참조할 원문을 실제로 저장한다."""
    document_id = f"CAM-{uuid.uuid4().hex[:8]}"
    values: dict[str, object] = {
        "id": uuid.uuid4(),
        "workspace_id": workspace_id,
        "source_type": SOURCE_TYPE,
        "source_identity": SourceIdentity(
            entity_type="user_chat",
            scope_id="ch-test",
            target_id="ch-test",
            external_document_id=document_id,
        ),
        "change_kind": ChangeKind.CREATED,
        "source_version_key": "1",
        "title": None,
        "canonical_url": None,
        "content": '{"detail": {}}',
        "content_type": "application/vnd.channel-talk.user-chat+json",
        "content_hash": "a" * 64,
        "source_updated_at": NOW,
        "observed_at": NOW,
        "idempotency_key": f"test:{document_id}",
        "payload_hash": "b" * 64,
        "metadata": {},
        "created_at": NOW,
    }
    values.update(overrides)
    source_version = SourceVersion(**values)  # type: ignore[arg-type]

    uow = KnowledgeMaintenanceUnitOfWork(session_factory)
    with uow:
        uow.source_versions.add(source_version)
        uow.commit()
    return source_version


def test_observation_survives_a_round_trip(
    workspace_id: int,
    session_factory: Callable[[], Session],
) -> None:
    """저장했다 읽으면 정규화 결과가 그대로 돌아온다."""
    source_version = _persisted_source_version(workspace_id, session_factory)

    uow = KnowledgeMaintenanceUnitOfWork(session_factory)
    with uow:
        stored = uow.observations.add(
            workspace_id=workspace_id,
            source_version_id=source_version.id,
            observation=_observation(),
        )
        uow.commit()

    with KnowledgeMaintenanceUnitOfWork(session_factory) as reader:
        found = reader.observations.get_by_normalizer(
            workspace_id=workspace_id,
            source_version_id=source_version.id,
            normalizer_id="test.normalizer",
            normalizer_version="1",
        )

    assert found is not None
    assert found.id == stored.id
    assert found.source_version_id == source_version.id
    assert found.observation.content == NORMALIZED_CONTENT
    assert found.observation.occurred_at == OCCURRED_AT
    assert found.observation.source_attributes["tags"] == ["요금", "도입"]
    assert found.observation.source_attributes["message_counts"]["total"] == 4


def test_metadata_entities_survive_a_round_trip(
    workspace_id: int,
    session_factory: Callable[[], Session],
) -> None:
    """JSONB로 오간 Entity 후보가 도메인 타입으로 되돌아온다."""
    source_version = _persisted_source_version(workspace_id, session_factory)

    uow = KnowledgeMaintenanceUnitOfWork(session_factory)
    with uow:
        uow.observations.add(
            workspace_id=workspace_id,
            source_version_id=source_version.id,
            observation=_observation(),
        )
        uow.commit()

    with KnowledgeMaintenanceUnitOfWork(session_factory) as reader:
        found = reader.observations.get_by_normalizer(
            workspace_id=workspace_id,
            source_version_id=source_version.id,
            normalizer_id="test.normalizer",
            normalizer_version="1",
        )

    entities = found.observation.metadata_entities
    assert len(entities) == 2
    assert entities[0].entity_type == "channel_talk_user"
    assert entities[0].external_key == "user-abc"
    assert entities[0].display_name == "사용자 008"
    assert entities[1].attributes["is_assignee"] is True


def test_tombstone_is_stored_without_content(
    workspace_id: int,
    session_factory: Callable[[], Session],
) -> None:
    """삭제 표식은 본문 없이 남고 CHECK 제약을 통과한다."""
    source_version = _persisted_source_version(
        workspace_id,
        session_factory,
        change_kind=ChangeKind.DELETED,
        content=None,
        content_type=None,
        content_hash=None,
    )

    uow = KnowledgeMaintenanceUnitOfWork(session_factory)
    with uow:
        stored = uow.observations.add(
            workspace_id=workspace_id,
            source_version_id=source_version.id,
            observation=_observation(
                observation_kind=ObservationKind.TOMBSTONE,
                content=None,
                content_hash=None,
                metadata_entities=(),
            ),
        )
        uow.commit()

    assert stored.observation.observation_kind == ObservationKind.TOMBSTONE
    assert stored.observation.content is None


def test_same_normalizer_cannot_store_twice(
    workspace_id: int,
    session_factory: Callable[[], Session],
) -> None:
    """같은 원문에 같은 계약으로 두 번 남길 수 없다."""
    source_version = _persisted_source_version(workspace_id, session_factory)

    uow = KnowledgeMaintenanceUnitOfWork(session_factory)
    with uow:
        uow.observations.add(
            workspace_id=workspace_id,
            source_version_id=source_version.id,
            observation=_observation(),
        )
        uow.commit()

    with pytest.raises(IntegrityError):
        with KnowledgeMaintenanceUnitOfWork(session_factory) as second:
            second.observations.add(
                workspace_id=workspace_id,
                source_version_id=source_version.id,
                observation=_observation(),
            )
            second.commit()


def test_a_new_normalizer_version_makes_another_observation(
    workspace_id: int,
    session_factory: Callable[[], Session],
) -> None:
    """정규화 규칙이 바뀌면 같은 원문에 Observation이 하나 더 쌓인다.

    SourceVersion과 Observation이 1:N인 이유이며, 재추출 실험이 여기 걸린다.
    """
    source_version = _persisted_source_version(workspace_id, session_factory)

    for version in ("1", "2"):
        with KnowledgeMaintenanceUnitOfWork(session_factory) as uow:
            uow.observations.add(
                workspace_id=workspace_id,
                source_version_id=source_version.id,
                observation=_observation(normalizer_version=version),
            )
            uow.commit()

    with KnowledgeMaintenanceUnitOfWork(session_factory) as reader:
        found = reader.observations.list_for_source_version(
            workspace_id=workspace_id,
            source_version_id=source_version.id,
        )

    assert [item.observation.normalizer_version for item in found] == ["1", "2"]


def test_observation_cannot_point_at_a_missing_source_version(
    workspace_id: int,
    session_factory: Callable[[], Session],
) -> None:
    """없는 원문을 가리키는 Observation은 저장되지 않는다."""
    with pytest.raises(IntegrityError):
        with KnowledgeMaintenanceUnitOfWork(session_factory) as uow:
            uow.observations.add(
                workspace_id=workspace_id,
                source_version_id=uuid.uuid4(),
                observation=_observation(),
            )
            uow.commit()


def test_normalizing_twice_reuses_the_stored_observation(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """재실행이 안전하다. 정규화에는 LLM이 없어 결과가 같기 때문이다."""
    source_version = _persisted_source_version(workspace_id, session_factory)
    normalizer = _StubNormalizer()

    first = normalize_source_version(
        source_version,
        normalizer=normalizer,
        uow=uow_factory(),
    )
    second = normalize_source_version(
        source_version,
        normalizer=normalizer,
        uow=uow_factory(),
    )

    assert first.result == NormalizationResult.CREATED
    assert second.result == NormalizationResult.REUSED
    assert second.observation.id == first.observation.id
    # 두 번째는 정규화를 다시 하지 않는다.
    assert normalizer.calls == 1


def test_a_newer_contract_normalizes_again(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """계약 버전이 올라가면 다시 정규화하고 기존 것을 덮지 않는다."""
    source_version = _persisted_source_version(workspace_id, session_factory)

    first = normalize_source_version(
        source_version,
        normalizer=_StubNormalizer(normalizer_version="1"),
        uow=uow_factory(),
    )
    second = normalize_source_version(
        source_version,
        normalizer=_StubNormalizer(normalizer_version="2"),
        uow=uow_factory(),
    )

    assert second.result == NormalizationResult.CREATED
    assert second.observation.id != first.observation.id

    with KnowledgeMaintenanceUnitOfWork(session_factory) as reader:
        found = reader.observations.list_for_source_version(
            workspace_id=workspace_id,
            source_version_id=source_version.id,
        )
    assert len(found) == 2
