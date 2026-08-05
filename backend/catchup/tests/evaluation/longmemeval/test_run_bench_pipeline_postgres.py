"""추출 완료 판정이 실 PostgreSQL의 큐 상태를 제대로 읽는지 확인한다.

fake는 상태별 건수를 그냥 돌려줄 뿐이다. 실제로 `failed`로 접힌 행이
`pending`·`processing`만 세는 조회에서 빠진다는 것은 진짜 테이블에 넣어
봐야 드러난다. 그 누락이 있으면 claim이 통째로 빠진 workspace가 정상
완료로 기록된다.

LLM은 부르지 않는다.
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
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker

from catchup.configs.config import settings
from catchup.db.models import KnowledgePipelineOutbox as OutboxRow
from catchup.db.models import Workspace
from catchup.evaluation.longmemeval.run_bench_pipeline import count_observation_backlog
from catchup.evaluation.longmemeval.run_ingestion import ensure_workspace
from catchup.evaluation.longmemeval.workspace_manifest import workspace_name
from catchup.knowledge_maintenance.domain.pipeline_event import PipelineAggregateType
from catchup.knowledge_maintenance.domain.pipeline_event import PipelineEventStatus
from catchup.knowledge_maintenance.domain.pipeline_event import PipelineEventType

BENCH_WORKSPACE_ID = 919_995
"""테스트 전용 번호다. 실제 벤치 대역(910000~)과 겹치지 않게 멀리 둔다."""


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
def template_workspace_id(engine: Engine) -> int:
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


def _event(session: Session, *, status: PipelineEventStatus) -> None:
    """정해진 상태의 observation 이벤트 하나를 큐에 넣는다."""
    session.add(
        OutboxRow(
            workspace_id=BENCH_WORKSPACE_ID,
            event_type=PipelineEventType.OBSERVATION_READY.value,
            aggregate_type=PipelineAggregateType.OBSERVATION.value,
            aggregate_id=uuid.uuid4(),
            status=status.value,
        )
    )
    session.flush()


def test_failed_events_are_counted_apart_from_the_queue(
    session_factory: Callable[[], Session],
    template_workspace_id: int,
) -> None:
    """재시도를 소진해 접힌 이벤트를 완료 판정이 놓치지 않는다."""
    with session_factory() as session:
        ensure_workspace(
            session,
            workspace_id=BENCH_WORKSPACE_ID,
            name=workspace_name("bench-backlog"),
            template_workspace_id=template_workspace_id,
        )
        _event(session, status=PipelineEventStatus.PROCESSED)
        _event(session, status=PipelineEventStatus.FAILED)

        backlog = count_observation_backlog(
            session,
            workspace_id=BENCH_WORKSPACE_ID,
        )

    # 큐는 비었다. 이것만 보면 "다 처리했다"로 읽힌다.
    assert backlog.unfinished == 0
    assert backlog.failed == 1
    assert backlog.total == 1


def test_pending_and_processing_are_both_unfinished(
    session_factory: Callable[[], Session],
    template_workspace_id: int,
) -> None:
    """큐에 남은 두 상태를 함께 세고 processed는 세지 않는다."""
    with session_factory() as session:
        ensure_workspace(
            session,
            workspace_id=BENCH_WORKSPACE_ID,
            name=workspace_name("bench-backlog"),
            template_workspace_id=template_workspace_id,
        )
        _event(session, status=PipelineEventStatus.PENDING)
        _event(session, status=PipelineEventStatus.PROCESSING)
        _event(session, status=PipelineEventStatus.PROCESSED)

        backlog = count_observation_backlog(
            session,
            workspace_id=BENCH_WORKSPACE_ID,
        )

    assert backlog.unfinished == 2
    assert backlog.failed == 0
