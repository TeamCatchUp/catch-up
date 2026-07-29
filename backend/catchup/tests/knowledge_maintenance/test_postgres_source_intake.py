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
from catchup.db.models import KnowledgeNode as KnowledgeNodeRow
from catchup.db.models import Observation as ObservationRow
from catchup.db.models import SourceVersion as SourceVersionRow
from catchup.db.models import Workspace
from catchup.knowledge_maintenance.adapters.postgres.unit_of_work import (
    KnowledgeMaintenanceUnitOfWork,
)
from catchup.knowledge_maintenance.contracts.source_change import SourceChangeEnvelope
from catchup.knowledge_maintenance.domain.knowledge_node import NodeKind
from catchup.knowledge_maintenance.domain.observation import NormalizedObservation
from catchup.knowledge_maintenance.domain.observation import ObservationKind
from catchup.knowledge_maintenance.domain.observation import content_hash
from catchup.knowledge_maintenance.domain.source_version import SourceVersion
from catchup.knowledge_maintenance.services.ingest_and_normalize import (
    ingest_and_normalize,
)
from catchup.knowledge_maintenance.services.ingest_source_version import IngestionResult
from catchup.knowledge_maintenance.services.normalize_source_version import (
    NormalizationResult,
)

NOW = datetime(2026, 7, 28, 9, 0, tzinfo=timezone.utc)
SOURCE_TYPE = "test-knowledge-maintenance"
NORMALIZED_CONTENT = "고객: 결제 기능은 언제 나오나요?"


@pytest.fixture(scope="module")
def engine() -> Iterator[Engine]:
    engine = create_engine(settings.sqlalchemy_database_url)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except OperationalError:
        engine.dispose()
        pytest.skip("PostgreSQL이 없어 통합 테스트를 건너뛴다.")

    if not inspect(engine).has_table(ObservationRow.__tablename__):
        engine.dispose()
        pytest.skip("observations 테이블이 없다. alembic upgrade head가 필요하다.")

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


@pytest.fixture
def uow_factory(
    session_factory: Callable[[], Session],
) -> Callable[[], KnowledgeMaintenanceUnitOfWork]:
    return lambda: KnowledgeMaintenanceUnitOfWork(session_factory)


class _StubNormalizer:
    normalizer_id = "test.normalizer"
    normalizer_version = "1"

    def normalize(self, source_version: SourceVersion) -> NormalizedObservation:
        return NormalizedObservation(
            normalizer_id=self.normalizer_id,
            normalizer_version=self.normalizer_version,
            observation_kind=ObservationKind.DOCUMENT,
            content=NORMALIZED_CONTENT,
            content_hash=content_hash(NORMALIZED_CONTENT),
        )


class _BrokenNormalizer:
    """정규화가 실패하는 상황을 만든다."""

    normalizer_id = "test.broken"
    normalizer_version = "1"

    def normalize(self, source_version: SourceVersion) -> NormalizedObservation:
        raise ValueError("이 원문은 정규화할 수 없다")


def _envelope(workspace_id: int, **overrides: object) -> SourceChangeEnvelope:
    document_id = f"CAM-{uuid.uuid4().hex[:8]}"
    values: dict[str, object] = {
        "schema_version": 1,
        "event_id": f"event-{document_id}",
        "workspace_id": workspace_id,
        "source_type": SOURCE_TYPE,
        "source_identity": {
            "entity_type": "user_chat",
            "scope_id": "ch-test",
            "target_id": "ch-test",
            "external_document_id": document_id,
        },
        "change_kind": "created",
        "source_version_key": "1",
        "title": "결제 기능 문의",
        "canonical_url": None,
        "content": '{"detail": {}}',
        "content_type": "application/vnd.channel-talk.user-chat+json",
        "source_updated_at": NOW,
        "observed_at": NOW,
        "idempotency_key": f"test:{document_id}",
        "metadata": {},
    }
    values.update(overrides)
    return SourceChangeEnvelope.model_validate(values)


def _counts(
    session_factory: Callable[[], Session],
    workspace_id: int,
    document_id: str,
) -> dict[str, int]:
    """한 원문이 남긴 행을 종류별로 센다."""
    with KnowledgeMaintenanceUnitOfWork(session_factory) as uow:
        session = uow.source_versions._session  # noqa: SLF001
        source_versions = session.scalars(
            select(SourceVersionRow.id).where(
                SourceVersionRow.workspace_id == workspace_id,
                SourceVersionRow.external_document_id == document_id,
            )
        ).all()
        observations = 0
        nodes = 0
        if source_versions:
            observations = session.scalar(
                select(func.count())
                .select_from(ObservationRow)
                .where(ObservationRow.source_version_id.in_(source_versions))
            )
            nodes = session.scalar(
                select(func.count())
                .select_from(KnowledgeNodeRow)
                .where(
                    KnowledgeNodeRow.workspace_id == workspace_id,
                    KnowledgeNodeRow.resource_id.in_(
                        [str(item) for item in source_versions]
                    ),
                )
            )
    return {
        "source_versions": len(source_versions),
        "observations": observations,
        "source_version_nodes": nodes,
    }


def test_intake_stores_everything_in_one_go(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """원문과 Observation과 두 node가 한 번에 확정된다."""
    envelope = _envelope(workspace_id)

    result = ingest_and_normalize(
        envelope,
        normalizer=_StubNormalizer(),
        uow=uow_factory(),
    )

    assert result.ingestion == IngestionResult.CREATED
    assert result.normalization == NormalizationResult.CREATED

    counts = _counts(
        session_factory,
        workspace_id,
        envelope.source_identity.external_document_id,
    )
    assert counts == {
        "source_versions": 1,
        "observations": 1,
        "source_version_nodes": 1,
    }

    with KnowledgeMaintenanceUnitOfWork(session_factory) as reader:
        observation_node = reader.knowledge_nodes.get_for_resource(
            workspace_id=workspace_id,
            node_kind=NodeKind.OBSERVATION,
            resource_id=result.observation_id,
        )
    assert observation_node is not None


def test_a_failed_normalization_rolls_back_the_source_version(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """정규화가 실패하면 원문 저장도 함께 되돌린다.

    이것이 T1을 두는 이유다. 원문만 남으면 그 원문은 아무 추출의 입력도
    되지 못하면서 재수집도 되지 않는다. 전달 키가 이미 쓰였다고 판정되어
    다음 폴링이 duplicate로 넘어가기 때문이다.
    """
    envelope = _envelope(workspace_id)
    document_id = envelope.source_identity.external_document_id

    with pytest.raises(ValueError, match="정규화할 수 없다"):
        ingest_and_normalize(
            envelope,
            normalizer=_BrokenNormalizer(),
            uow=uow_factory(),
        )

    assert _counts(session_factory, workspace_id, document_id) == {
        "source_versions": 0,
        "observations": 0,
        "source_version_nodes": 0,
    }


def test_the_same_envelope_can_be_retried_after_a_failure(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """되돌렸으므로 같은 envelope을 다시 보내면 처음부터 시도한다."""
    envelope = _envelope(workspace_id)

    with pytest.raises(ValueError):
        ingest_and_normalize(
            envelope,
            normalizer=_BrokenNormalizer(),
            uow=uow_factory(),
        )

    result = ingest_and_normalize(
        envelope,
        normalizer=_StubNormalizer(),
        uow=uow_factory(),
    )

    assert result.ingestion == IngestionResult.CREATED
    assert result.normalization == NormalizationResult.CREATED


def test_reintake_reuses_both_records(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """같은 원문을 다시 받아도 행이 늘지 않는다."""
    envelope = _envelope(workspace_id)
    document_id = envelope.source_identity.external_document_id
    normalizer = _StubNormalizer()

    first = ingest_and_normalize(envelope, normalizer=normalizer, uow=uow_factory())
    second = ingest_and_normalize(envelope, normalizer=normalizer, uow=uow_factory())

    assert second.ingestion == IngestionResult.DUPLICATE
    assert second.normalization == NormalizationResult.REUSED
    assert second.source_version_id == first.source_version_id
    assert second.observation_id == first.observation_id

    assert _counts(session_factory, workspace_id, document_id) == {
        "source_versions": 1,
        "observations": 1,
        "source_version_nodes": 1,
    }


def test_a_deleted_envelope_becomes_a_tombstone_in_one_transaction(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """삭제 전달도 같은 경계를 지난다."""

    class _TombstoneNormalizer:
        normalizer_id = "test.tombstone"
        normalizer_version = "1"

        def normalize(
            self,
            source_version: SourceVersion,
        ) -> NormalizedObservation:
            return NormalizedObservation(
                normalizer_id=self.normalizer_id,
                normalizer_version=self.normalizer_version,
                observation_kind=ObservationKind.TOMBSTONE,
                content=None,
                content_hash=None,
            )

    envelope = _envelope(
        workspace_id,
        change_kind="deleted",
        content=None,
        content_type=None,
    )

    result = ingest_and_normalize(
        envelope,
        normalizer=_TombstoneNormalizer(),
        uow=uow_factory(),
    )

    assert result.normalization == NormalizationResult.CREATED
    assert _counts(
        session_factory,
        workspace_id,
        envelope.source_identity.external_document_id,
    ) == {
        "source_versions": 1,
        "observations": 1,
        "source_version_nodes": 1,
    }
