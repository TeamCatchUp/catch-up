"""이름 벡터 캐시를 실 PostgreSQL로 확인한다.

담고 찾는 일이 맞물려야 캐시가 값을 하므로 왕복을 실 DB로 본다. UNIQUE
충돌을 무시하는 저장도 가짜 저장소로는 제약 문구가 틀려도 드러나지 않아
여기서 확인한다.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy import Engine
from sqlalchemy import create_engine
from sqlalchemy import delete
from sqlalchemy import inspect
from sqlalchemy import select
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

from catchup.configs.config import settings
from catchup.db.models import KnowledgeNameEmbedding
from catchup.db.models import Workspace
from catchup.knowledge_maintenance.adapters.postgres.name_embedding_cache import (
    SqlAlchemyNameEmbeddingCache,
)

MODEL_ID = "test-embedding-model"
OTHER_MODEL_ID = "test-embedding-model-v2"


@pytest.fixture(scope="module")
def engine() -> Iterator[Engine]:
    engine = create_engine(settings.sqlalchemy_database_url)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except OperationalError:
        engine.dispose()
        pytest.skip("PostgreSQL이 없어 통합 테스트를 건너뛴다.")

    if not inspect(engine).has_table(KnowledgeNameEmbedding.__tablename__):
        engine.dispose()
        pytest.skip(
            "이름 벡터 캐시 표가 없다. alembic upgrade head가 필요하다."
        )

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
def cache(
    engine: Engine, workspace_id: int
) -> Iterator[SqlAlchemyNameEmbeddingCache]:
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    yield SqlAlchemyNameEmbeddingCache(session_factory)

    with session_factory() as session:
        session.execute(
            delete(KnowledgeNameEmbedding).where(
                KnowledgeNameEmbedding.workspace_id == workspace_id,
                KnowledgeNameEmbedding.model_id.in_(
                    (MODEL_ID, OTHER_MODEL_ID)
                ),
            )
        )
        session.commit()


def test_stored_vector_comes_back(
    cache: SqlAlchemyNameEmbeddingCache, workspace_id: int
) -> None:
    """담아 둔 벡터를 이름으로 그대로 찾아온다."""
    cache.store(
        workspace_id=workspace_id,
        model_id=MODEL_ID,
        vectors={"slack": (1.0, 0.5), "지라": (0.0, 1.0)},
    )

    found = cache.lookup(
        workspace_id=workspace_id,
        model_id=MODEL_ID,
        normalized_names=("slack", "지라"),
    )

    assert found == {"slack": (1.0, 0.5), "지라": (0.0, 1.0)}


def test_missing_name_is_absent_from_the_result(
    cache: SqlAlchemyNameEmbeddingCache, workspace_id: int
) -> None:
    """담기지 않은 이름은 키 자체가 없다."""
    cache.store(
        workspace_id=workspace_id,
        model_id=MODEL_ID,
        vectors={"slack": (1.0, 0.5)},
    )

    found = cache.lookup(
        workspace_id=workspace_id,
        model_id=MODEL_ID,
        normalized_names=("slack", "노션"),
    )

    assert set(found) == {"slack"}


def test_other_model_does_not_see_the_vector(
    cache: SqlAlchemyNameEmbeddingCache, workspace_id: int
) -> None:
    """모델이 다르면 같은 이름이어도 담긴 값을 찾지 못한다."""
    cache.store(
        workspace_id=workspace_id,
        model_id=MODEL_ID,
        vectors={"slack": (1.0, 0.5)},
    )

    found = cache.lookup(
        workspace_id=workspace_id,
        model_id=OTHER_MODEL_ID,
        normalized_names=("slack",),
    )

    assert found == {}


def test_storing_the_same_name_twice_is_harmless(
    cache: SqlAlchemyNameEmbeddingCache, workspace_id: int
) -> None:
    """같은 키를 다시 담아도 실패하지 않고 먼저 담긴 값이 남는다."""
    cache.store(
        workspace_id=workspace_id,
        model_id=MODEL_ID,
        vectors={"slack": (1.0, 0.5)},
    )
    cache.store(
        workspace_id=workspace_id,
        model_id=MODEL_ID,
        vectors={"slack": (9.0, 9.0), "노션": (0.0, 1.0)},
    )

    found = cache.lookup(
        workspace_id=workspace_id,
        model_id=MODEL_ID,
        normalized_names=("slack", "노션"),
    )

    assert found == {"slack": (1.0, 0.5), "노션": (0.0, 1.0)}


def test_empty_input_touches_nothing(
    cache: SqlAlchemyNameEmbeddingCache, workspace_id: int
) -> None:
    """찾을 이름도 담을 벡터도 없으면 아무 일도 하지 않는다."""
    cache.store(workspace_id=workspace_id, model_id=MODEL_ID, vectors={})

    assert (
        cache.lookup(
            workspace_id=workspace_id,
            model_id=MODEL_ID,
            normalized_names=(),
        )
        == {}
    )
