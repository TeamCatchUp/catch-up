"""검색 projection의 PGVector 어댑터를 실 DB로 확인한다.

rebuild는 "같은 workspace의 llm_wiki 문서를 전량 지우고 새로 넣는" 한
번의 교체다. 이 성질은 실제 행이 지워졌는지로만 드러나므로 fake 대신
실 PostgreSQL에 넣어 본다. 남의 source·남의 workspace 행을 건드리지
않는지도 같은 자리에서 본다.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from langchain_core.embeddings import Embeddings
from sqlalchemy import Engine
from sqlalchemy import create_engine
from sqlalchemy import inspect
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from catchup.configs.config import settings
from catchup.knowledge_maintenance.adapters.search.pgvector_projection import (
    PgVectorArtifactSearchProjection,
)
from catchup.knowledge_maintenance.domain.search_projection import ProjectionDocument
from catchup.knowledge_maintenance.ports.search_projection import (
    ArtifactSearchProjectionPort,
)

COLLECTION_NAME = "test_llm_wiki_projection"
EMBEDDING_TABLE = "langchain_pg_embedding"


def _embedding_dimensions(engine: Engine) -> int:
    """langchain_pg_embedding.embedding의 고정 차원을 읽는다.

    차원 무지정(`vector`)이면 4를 쓴다 — 어떤 길이든 들어가므로
    테스트를 가볍게 유지한다.
    """
    with engine.connect() as connection:
        formatted = connection.execute(
            text(
                "SELECT format_type(atttypid, atttypmod) "
                "FROM pg_attribute "
                "WHERE attrelid = 'langchain_pg_embedding'::regclass "
                "AND attname = 'embedding'"
            )
        ).scalar()

    if formatted and "(" in formatted:
        return int(formatted.split("(")[1].rstrip(")"))
    return 4


class FixedEmbeddings(Embeddings):
    """고정 벡터를 돌려주는 테스트용 임베더다."""

    def __init__(self, dimensions: int) -> None:
        self._dimensions = dimensions

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[0.1] * self._dimensions for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        return [0.1] * self._dimensions


@pytest.fixture(scope="module")
def engine() -> Iterator[Engine]:
    engine = create_engine(settings.sqlalchemy_database_url)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except OperationalError:
        engine.dispose()
        pytest.skip("PostgreSQL이 없어 통합 테스트를 건너뛴다.")

    if not inspect(engine).has_table(EMBEDDING_TABLE):
        engine.dispose()
        pytest.skip("langchain_pg_embedding 테이블이 없어 건너뛴다.")

    yield engine
    engine.dispose()


@pytest.fixture
def adapter(engine: Engine) -> Iterator[PgVectorArtifactSearchProjection]:
    built = PgVectorArtifactSearchProjection(
        engine=engine,
        embeddings=FixedEmbeddings(_embedding_dimensions(engine)),
        collection_name=COLLECTION_NAME,
    )
    yield built
    _drop_test_collection(engine)


def _drop_test_collection(engine: Engine) -> None:
    """테스트 전용 collection과 그 행들을 지운다."""
    with engine.begin() as connection:
        connection.execute(
            text(
                "DELETE FROM langchain_pg_embedding WHERE collection_id IN "
                "(SELECT uuid FROM langchain_pg_collection WHERE name = :name)"
            ),
            {"name": COLLECTION_NAME},
        )
        connection.execute(
            text("DELETE FROM langchain_pg_collection WHERE name = :name"),
            {"name": COLLECTION_NAME},
        )


def _rows(engine: Engine) -> list[tuple[str, str, str]]:
    """테스트 collection에 남은 (id, source, scope_id)를 읽는다."""
    with engine.connect() as connection:
        return [
            (row[0], row[1], row[2])
            for row in connection.execute(
                text(
                    "SELECT e.id, e.cmetadata->>'source', "
                    "e.cmetadata->>'scope_id' "
                    "FROM langchain_pg_embedding e "
                    "JOIN langchain_pg_collection c "
                    "ON c.uuid = e.collection_id "
                    "WHERE c.name = :name ORDER BY e.id"
                ),
                {"name": COLLECTION_NAME},
            ).all()
        ]


def _document(document_id: str, workspace_id: int) -> ProjectionDocument:
    return ProjectionDocument(
        document_id=document_id,
        content=f"본문 {document_id}",
        metadata={
            "source": "llm_wiki",
            "entity_type": "artifact_revision",
            "scope_id": str(workspace_id),
            "title": "제목",
        },
    )


def _foreign_document(
    document_id: str, source: str, workspace_id: int
) -> ProjectionDocument:
    return ProjectionDocument(
        document_id=document_id,
        content=f"본문 {document_id}",
        metadata={
            "source": source,
            "entity_type": "message",
            "scope_id": str(workspace_id),
        },
    )


def test_adapter_satisfies_port(
    adapter: PgVectorArtifactSearchProjection,
) -> None:
    """어댑터가 포트 시그니처를 만족하는지 정적으로 묶어 둔다."""
    port: ArtifactSearchProjectionPort = adapter

    assert port is adapter


def test_rebuild_replaces_workspace_documents(
    adapter: PgVectorArtifactSearchProjection, engine: Engine
) -> None:
    first = adapter.rebuild(workspace_id=1, documents=[_document("doc-a", 1)])

    assert first.deleted == 0
    assert first.inserted == 1

    second = adapter.rebuild(workspace_id=1, documents=[_document("doc-b", 1)])

    assert second.deleted == 1
    assert second.inserted == 1
    assert [row[0] for row in _rows(engine)] == ["doc-b"]


def test_rebuild_keeps_other_source_and_workspace(
    adapter: PgVectorArtifactSearchProjection, engine: Engine
) -> None:
    adapter.rebuild(
        workspace_id=1,
        documents=[
            _document("doc-a", 1),
            _foreign_document("slack-a", "slack", 1),
            _document("other-ws", 2),
        ],
    )

    result = adapter.rebuild(workspace_id=1, documents=[_document("doc-b", 1)])

    assert result.deleted == 1
    assert _rows(engine) == [
        ("doc-b", "llm_wiki", "1"),
        ("other-ws", "llm_wiki", "2"),
        ("slack-a", "slack", "1"),
    ]


def test_rebuild_with_no_documents_only_deletes(
    adapter: PgVectorArtifactSearchProjection, engine: Engine
) -> None:
    adapter.rebuild(workspace_id=1, documents=[_document("doc-a", 1)])

    result = adapter.rebuild(workspace_id=1, documents=[])

    assert result.deleted == 1
    assert result.inserted == 0
    assert _rows(engine) == []
