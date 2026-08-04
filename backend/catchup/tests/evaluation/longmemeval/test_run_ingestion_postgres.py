"""수집 러너의 workspace 소유 검증을 실 PostgreSQL로 확인한다.

fake는 `ON CONFLICT DO NOTHING`과 varchar(50) 절단을 흉내 낼 뿐이다.
실제로 그 두 규칙이 함께 걸렸을 때 소유 검증이 서는지는 진짜 테이블에
넣어 봐야 드러난다. 서브셋 크기를 바꿔 같은 번호가 다른 문항에 재배정된
상황이 여기서 재현하려는 것이다.

LLM은 부르지 않는다.
"""

from __future__ import annotations

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
from catchup.db.models import Workspace
from catchup.evaluation.longmemeval.run_ingestion import ensure_workspace
from catchup.evaluation.longmemeval.workspace_manifest import workspace_name

BENCH_WORKSPACE_ID = 919_999
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

    if not inspect(engine).has_table(Workspace.__tablename__):
        engine.dispose()
        pytest.skip("workspaces 테이블이 없다. alembic upgrade head가 필요하다.")

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


def test_reassigned_workspace_is_refused(
    session_factory: Callable[[], Session],
    template_workspace_id: int,
) -> None:
    """다른 문항이 이미 쓰는 번호면 실 DB에서도 적재 전에 멈춘다."""
    first = "08f4fc43"
    second = "031748ae"

    with session_factory() as session:
        ensure_workspace(
            session,
            workspace_id=BENCH_WORKSPACE_ID,
            name=workspace_name(first),
            template_workspace_id=template_workspace_id,
        )

        with pytest.raises(SystemExit) as excinfo:
            ensure_workspace(
                session,
                workspace_id=BENCH_WORKSPACE_ID,
                name=workspace_name(second),
                template_workspace_id=template_workspace_id,
            )

        message = str(excinfo.value)
        assert workspace_name(first) in message
        assert workspace_name(second) in message

        # 거부하면서 이름을 덮어쓰지도 않았는지 본다. 덮어쓰면 다음
        # 실행이 소유 검증을 통과해 오염이 그대로 살아난다.
        stored = session.execute(
            text("SELECT name FROM workspaces WHERE id = :id"),
            {"id": BENCH_WORKSPACE_ID},
        ).scalar()
        assert stored == workspace_name(first)


def test_same_question_reuses_the_workspace(
    session_factory: Callable[[], Session],
    template_workspace_id: int,
) -> None:
    """같은 문항의 재실행은 같은 행을 그대로 쓴다."""
    question_id = "08f4fc43"

    with session_factory() as session:
        for _ in range(2):
            ensure_workspace(
                session,
                workspace_id=BENCH_WORKSPACE_ID,
                name=workspace_name(question_id),
                template_workspace_id=template_workspace_id,
            )

        count = session.execute(
            text("SELECT count(*) FROM workspaces WHERE id = :id"),
            {"id": BENCH_WORKSPACE_ID},
        ).scalar()
        assert count == 1
