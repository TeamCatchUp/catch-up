from __future__ import annotations

import uuid
from collections.abc import Callable
from collections.abc import Iterator
from datetime import datetime
from datetime import timedelta
from datetime import timezone

import pytest
from sqlalchemy import Engine
from sqlalchemy import create_engine
from sqlalchemy import inspect
from sqlalchemy import select
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker

from catchup.configs.config import settings
from catchup.db.models import KnowledgePipelineOutbox as OutboxRow
from catchup.db.models import Workspace
from catchup.knowledge_maintenance.adapters.postgres.unit_of_work import (
    KnowledgeMaintenanceUnitOfWork,
)
from catchup.knowledge_maintenance.contracts.source_change import SourceChangeEnvelope
from catchup.knowledge_maintenance.domain.observation import NormalizedObservation
from catchup.knowledge_maintenance.domain.observation import ObservationKind
from catchup.knowledge_maintenance.domain.observation import content_hash
from catchup.knowledge_maintenance.domain.pipeline_event import RETRY_LIMITS
from catchup.knowledge_maintenance.domain.pipeline_event import FailureKind
from catchup.knowledge_maintenance.domain.pipeline_event import PipelineAggregateType
from catchup.knowledge_maintenance.domain.pipeline_event import PipelineEventStatus
from catchup.knowledge_maintenance.domain.pipeline_event import PipelineEventType
from catchup.knowledge_maintenance.domain.pipeline_event import next_attempt_at
from catchup.knowledge_maintenance.domain.pipeline_event import resolve_failure
from catchup.knowledge_maintenance.domain.source_version import SourceVersion
from catchup.knowledge_maintenance.services.ingest_and_normalize import (
    ingest_and_normalize,
)

# outbox의 available_at이 DB 서버 시각으로 들어가므로 테스트도 실제 시계를
# 기준으로 삼는다. 고정 과거 시각을 쓰면 방금 넣은 일이 아직 안 왔다고 판정된다.
NOW = datetime.now(timezone.utc)
SOON = NOW + timedelta(minutes=5)
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

    if not inspect(engine).has_table(OutboxRow.__tablename__):
        engine.dispose()
        pytest.skip("outbox 테이블이 없다. alembic upgrade head가 필요하다.")

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


def _envelope(workspace_id: int) -> SourceChangeEnvelope:
    document_id = f"CAM-{uuid.uuid4().hex[:8]}"
    return SourceChangeEnvelope.model_validate(
        {
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
            "title": None,
            "canonical_url": None,
            "content": '{"detail": {}}',
            "content_type": "application/vnd.channel-talk.user-chat+json",
            "source_updated_at": NOW,
            "observed_at": NOW,
            "idempotency_key": f"test:{document_id}",
            "metadata": {},
        }
    )


def _claim(
    session_factory: Callable[[], Session],
    workspace_id: int,
    *,
    now: datetime = SOON,
) -> tuple:
    with KnowledgeMaintenanceUnitOfWork(session_factory) as reader:
        return reader.pipeline_events.claim_pending(
            workspace_id=workspace_id,
            event_type=PipelineEventType.OBSERVATION_READY,
            now=now,
        )


def test_intake_enqueues_the_next_step(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """Observation을 확정하는 transaction에서 지시도 함께 적힌다."""
    result = ingest_and_normalize(
        _envelope(workspace_id),
        normalizer=_StubNormalizer(),
        uow=uow_factory(),
    )

    events = _claim(session_factory, workspace_id)
    targets = {event.aggregate_id for event in events}

    assert result.observation_id in targets


def test_the_same_target_is_queued_once(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """같은 대상에 같은 지시가 두 번 쌓이지 않는다."""
    envelope = _envelope(workspace_id)
    normalizer = _StubNormalizer()

    result = ingest_and_normalize(envelope, normalizer=normalizer, uow=uow_factory())
    ingest_and_normalize(envelope, normalizer=normalizer, uow=uow_factory())

    events = _claim(session_factory, workspace_id)
    matching = [
        event for event in events if event.aggregate_id == result.observation_id
    ]
    assert len(matching) == 1


def test_a_contract_violation_gets_a_few_more_tries(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """계약 위반은 흔들림일 수 있으므로 곧바로 접지 않는다.

    같은 입력에 같은 프롬프트로 다시 돌려 성공한 사례가 실측으로 있다.
    한 번에 접으면 멀쩡한 문서를 영영 버린다.
    """
    result = ingest_and_normalize(
        _envelope(workspace_id),
        normalizer=_StubNormalizer(),
        uow=uow_factory(),
    )
    event = next(
        item
        for item in _claim(session_factory, workspace_id)
        if item.aggregate_id == result.observation_id
    )

    with KnowledgeMaintenanceUnitOfWork(session_factory) as uow:
        settled = uow.pipeline_events.mark_failed(
            event_id=event.id,
            kind=FailureKind.CONTRACT_VIOLATION,
            error="계약 위반",
            now=NOW,
        )
        uow.commit()

    assert settled.status is PipelineEventStatus.PENDING
    assert settled.attempts == 1

    # 다만 API 오류보다 적게 봐준다. 프롬프트가 잘못됐다면 곧 포기해야 한다.
    with KnowledgeMaintenanceUnitOfWork(session_factory) as uow:
        settled = uow.pipeline_events.mark_failed(
            event_id=event.id,
            kind=FailureKind.CONTRACT_VIOLATION,
            error="계약 위반",
            now=NOW,
        )
        uow.commit()

    assert settled.attempts == RETRY_LIMITS[FailureKind.CONTRACT_VIOLATION]
    assert settled.status is PipelineEventStatus.FAILED

    remaining = {
        item.aggregate_id
        for item in _claim(session_factory, workspace_id, now=NOW + timedelta(days=7))
    }
    assert result.observation_id not in remaining


def test_a_transient_failure_comes_back_after_a_backoff(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """일시적 실패는 물러났다가 시각이 되면 다시 나타난다."""
    result = ingest_and_normalize(
        _envelope(workspace_id),
        normalizer=_StubNormalizer(),
        uow=uow_factory(),
    )
    event = next(
        item
        for item in _claim(session_factory, workspace_id)
        if item.aggregate_id == result.observation_id
    )

    with KnowledgeMaintenanceUnitOfWork(session_factory) as uow:
        settled = uow.pipeline_events.mark_failed(
            event_id=event.id,
            kind=FailureKind.API_ERROR,
            error="ThrottlingException",
            now=NOW,
        )
        uow.commit()

    assert settled.status is PipelineEventStatus.PENDING
    assert settled.available_at > NOW

    # 아직 시각이 안 됐으면 보이지 않는다.
    not_yet = {
        item.aggregate_id
        for item in _claim(session_factory, workspace_id, now=NOW)
    }
    assert result.observation_id not in not_yet

    later = {
        item.aggregate_id
        for item in _claim(session_factory, workspace_id, now=NOW + timedelta(hours=1))
    }
    assert result.observation_id in later


def test_a_transient_failure_gives_up_eventually(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """무한히 재시도하지 않는다. 진짜 문제가 실패 목록에 드러나야 한다."""
    result = ingest_and_normalize(
        _envelope(workspace_id),
        normalizer=_StubNormalizer(),
        uow=uow_factory(),
    )
    event = next(
        item
        for item in _claim(session_factory, workspace_id)
        if item.aggregate_id == result.observation_id
    )

    settled = None
    for _ in range(RETRY_LIMITS[FailureKind.API_ERROR]):
        with KnowledgeMaintenanceUnitOfWork(session_factory) as uow:
            settled = uow.pipeline_events.mark_failed(
                event_id=event.id,
                kind=FailureKind.API_ERROR,
                error="ThrottlingException",
                now=NOW,
            )
            uow.commit()

    assert settled.attempts == RETRY_LIMITS[FailureKind.API_ERROR]
    assert settled.status is PipelineEventStatus.FAILED


def test_processed_events_do_not_come_back(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    result = ingest_and_normalize(
        _envelope(workspace_id),
        normalizer=_StubNormalizer(),
        uow=uow_factory(),
    )
    event = next(
        item
        for item in _claim(session_factory, workspace_id)
        if item.aggregate_id == result.observation_id
    )

    with KnowledgeMaintenanceUnitOfWork(session_factory) as uow:
        uow.pipeline_events.mark_processed(event_id=event.id, now=NOW)
        uow.commit()

    remaining = {
        item.aggregate_id
        for item in _claim(session_factory, workspace_id, now=NOW + timedelta(days=7))
    }
    assert result.observation_id not in remaining


def test_backfill_queues_observations_that_predate_the_queue(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """큐를 도입하기 전에 저장된 Observation이 영영 묻히지 않는다."""
    result = ingest_and_normalize(
        _envelope(workspace_id),
        normalizer=_StubNormalizer(),
        uow=uow_factory(),
    )

    # 지시를 지워 큐 이전 상태를 만든다.
    with KnowledgeMaintenanceUnitOfWork(session_factory) as uow:
        session = uow.pipeline_events._session  # noqa: SLF001
        session.execute(
            text("DELETE FROM knowledge_pipeline_outbox WHERE aggregate_id = :i"),
            {"i": result.observation_id},
        )
        uow.commit()

    assert result.observation_id not in {
        item.aggregate_id for item in _claim(session_factory, workspace_id)
    }

    with KnowledgeMaintenanceUnitOfWork(session_factory) as uow:
        added = uow.pipeline_events.backfill_missing(
            workspace_id=workspace_id,
            event_type=PipelineEventType.OBSERVATION_READY,
        )
        uow.commit()

    assert added >= 1
    assert result.observation_id in {
        item.aggregate_id for item in _claim(session_factory, workspace_id)
    }


def test_backoff_grows_with_attempts() -> None:
    """같은 대상에 재시도가 몰리지 않게 대기를 배로 늘린다."""
    first = next_attempt_at(1, now=NOW) - NOW
    second = next_attempt_at(2, now=NOW) - NOW
    third = next_attempt_at(3, now=NOW) - NOW

    assert second == first * 2
    assert third == second * 2


def test_each_failure_kind_has_its_own_limit() -> None:
    """계약 위반은 적게, API 오류는 많이 봐준다."""
    assert (
        RETRY_LIMITS[FailureKind.CONTRACT_VIOLATION]
        < RETRY_LIMITS[FailureKind.API_ERROR]
    )

    for kind, limit in RETRY_LIMITS.items():
        assert resolve_failure(kind, limit - 1) is PipelineEventStatus.PENDING
        assert resolve_failure(kind, limit) is PipelineEventStatus.FAILED


def test_enqueue_is_idempotent_at_the_repository(
    workspace_id: int,
    session_factory: Callable[[], Session],
) -> None:
    """같은 지시를 두 번 적으려 하면 두 번째는 만들지 않는다."""
    target = uuid.uuid4()

    with KnowledgeMaintenanceUnitOfWork(session_factory) as uow:
        first = uow.pipeline_events.enqueue(
            workspace_id=workspace_id,
            event_type=PipelineEventType.OBSERVATION_READY,
            aggregate_type=PipelineAggregateType.OBSERVATION,
            aggregate_id=target,
        )
        second = uow.pipeline_events.enqueue(
            workspace_id=workspace_id,
            event_type=PipelineEventType.OBSERVATION_READY,
            aggregate_type=PipelineAggregateType.OBSERVATION,
            aggregate_id=target,
        )
        uow.commit()

    assert first is not None
    assert second is None


def test_a_tombstone_does_not_enter_the_extraction_queue(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """삭제 표식은 추출 대상이 아니다.

    본문이 없어 Extractor가 계약 위반을 내고, 재시도 끝에 실패로 남을 뿐
    아무 일도 일어나지 않는다. 삭제는 빈 문서에서 지식을 뽑는 일이 아니라
    기존 근거가 사라졌다는 사건이며, 무효화는 Resolution의 몫이다.
    """

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

    # model_copy는 검증을 하지 않아 enum이 문자열로 남는다. 다시 만든다.
    base = _envelope(workspace_id).model_dump(mode="json")
    base.update(change_kind="deleted", content=None, content_type=None)
    envelope = SourceChangeEnvelope.model_validate(base)

    result = ingest_and_normalize(
        envelope,
        normalizer=_TombstoneNormalizer(),
        uow=uow_factory(),
    )

    # Observation 자체는 남는다. 무효화의 근거가 되어야 하기 때문이다.
    assert result.observation_id is not None

    queued = {item.aggregate_id for item in _claim(session_factory, workspace_id)}
    assert result.observation_id not in queued
