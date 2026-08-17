"""observation.ready 행이 없는 Observation을 outbox에 다시 큐잉한다.

리셋이 outbox를 비우면 남은 observation이 재추출 대상에서 빠지므로 다시
큐잉한다. 추출 러너는 outbox에 남은 일감만 읽기 때문에, 행이 사라진
Observation은 DB에 그대로 있어도 아무도 집어 가지 않는다.

유일 제약 `(event_type, aggregate_type, aggregate_id)`를 그대로 쓰므로 여러
번 돌려도 결과가 같다. 이미 있는 행은 상태와 무관하게 건드리지 않는다.

개발 DB 전용 운영 도구다.

실행:
    uv run python -m catchup.evaluation.reseed_pipeline_outbox \
        --workspace-id 1 [--dry-run]
"""

from __future__ import annotations

import argparse

import structlog
from sqlalchemy import create_engine
from sqlalchemy import func
from sqlalchemy import literal
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql.elements import ColumnElement

from catchup.configs.config import settings
from catchup.db.models import KnowledgePipelineOutbox
from catchup.db.models import Observation
from catchup.knowledge_maintenance.domain.pipeline_event import PipelineAggregateType
from catchup.knowledge_maintenance.domain.pipeline_event import PipelineEventStatus
from catchup.knowledge_maintenance.domain.pipeline_event import PipelineEventType

logger = structlog.get_logger(__name__)


def _not_queued() -> ColumnElement[bool]:
    """outbox에 자기 행이 아직 없다는 조건이다."""
    already_queued = select(KnowledgePipelineOutbox.id).where(
        KnowledgePipelineOutbox.event_type == PipelineEventType.OBSERVATION_READY.value,
        KnowledgePipelineOutbox.aggregate_type
        == PipelineAggregateType.OBSERVATION.value,
        KnowledgePipelineOutbox.aggregate_id == Observation.id,
    )
    return ~already_queued.exists()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace-id", type=int, default=1)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="건수만 세고 아무것도 넣지 않는다.",
    )
    args = parser.parse_args()

    engine = create_engine(settings.sqlalchemy_database_url)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    # 어느 갈래로 빠져나가든 연결 풀을 닫는다. 중간에 예외가 나면
    # 프로세스가 열린 연결을 쥔 채로 끝난다.
    try:
        with session_factory() as session:
            if args.dry_run:
                count = session.execute(
                    select(func.count())
                    .select_from(Observation)
                    .where(Observation.workspace_id == args.workspace_id)
                    .where(_not_queued())
                ).scalar_one()
                logger.info(
                    "reseed_outbox_dry_run",
                    workspace_id=args.workspace_id,
                    missing=count,
                )
                print(f"reseed_outbox_dry_run missing={count}")
                return

            source = (
                select(
                    Observation.workspace_id,
                    literal(PipelineEventType.OBSERVATION_READY.value),
                    literal(PipelineAggregateType.OBSERVATION.value),
                    Observation.id,
                    literal(PipelineEventStatus.PENDING.value),
                )
                .where(Observation.workspace_id == args.workspace_id)
                .where(_not_queued())
            )
            statement = (
                pg_insert(KnowledgePipelineOutbox)
                .from_select(
                    [
                        "workspace_id",
                        "event_type",
                        "aggregate_type",
                        "aggregate_id",
                        "status",
                    ],
                    source,
                )
                .on_conflict_do_nothing(
                    index_elements=["event_type", "aggregate_type", "aggregate_id"],
                )
            )
            inserted = session.execute(statement).rowcount
            session.commit()

        logger.info(
            "reseed_outbox_done",
            workspace_id=args.workspace_id,
            inserted=inserted,
        )
        print(f"reseed_outbox_done inserted={inserted}")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
