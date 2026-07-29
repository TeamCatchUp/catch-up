"""어휘 사전 entry 계약과 vocabulary 확장을 검증한다."""

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
from catchup.db.models import KnowledgeOntologySnapshot as SnapshotRow
from catchup.db.models import Workspace
from catchup.knowledge_maintenance.adapters.postgres.unit_of_work import (
    KnowledgeMaintenanceUnitOfWork,
)
from catchup.knowledge_maintenance.contracts.extraction import EntityTypeEntry
from catchup.knowledge_maintenance.contracts.extraction import ExtractionVocabulary
from catchup.knowledge_maintenance.contracts.extraction import PredicateEntry
from catchup.knowledge_maintenance.contracts.extraction import RelationTypeEntry
from catchup.knowledge_maintenance.ports.ontology import OntologySnapshotConflict


def _predicate_entry(**overrides) -> PredicateEntry:
    values = {
        "name": "rate_limit_per_minute",
        "definition": "분당 허용되는 API 호출 횟수",
        "domain": ("api",),
        "value_type": "number",
        "enum_values": (),
        "examples": ("분당 60회입니다 → 60",),
    }
    values.update(overrides)
    return PredicateEntry(**values)


def test_predicate_names_derive_from_entries() -> None:
    """entry가 있으면 이름 목록은 entry에서 파생된다."""
    vocabulary = ExtractionVocabulary(
        snapshot_id="2",
        predicate_entries=(_predicate_entry(),),
    )
    assert vocabulary.predicates == ("rate_limit_per_minute",)


def test_name_list_only_snapshot_still_loads() -> None:
    """v1 스냅샷(이름 목록만)은 그대로 읽힌다."""
    vocabulary = ExtractionVocabulary(
        snapshot_id="1",
        predicates=("status", "issue_type"),
    )
    assert vocabulary.predicates == ("status", "issue_type")
    assert vocabulary.predicate_entry("status") is None


def test_predicate_entry_lookup_by_name() -> None:
    vocabulary = ExtractionVocabulary(
        snapshot_id="2",
        predicate_entries=(_predicate_entry(),),
    )
    found = vocabulary.predicate_entry("rate_limit_per_minute")
    assert found is not None
    assert found.value_type == "number"


def test_enum_predicate_requires_enum_values() -> None:
    """치역이 enum인데 허용 값이 없으면 계약 위반이다."""
    with pytest.raises(ValueError):
        _predicate_entry(value_type="enum", enum_values=())


def test_entity_type_entry_scope_is_closed() -> None:
    with pytest.raises(ValueError):
        EntityTypeEntry(
            name="team",
            definition="회사 안에서 역할로 묶인 조직 단위",
            identity_scope="floating",
            examples=(),
        )


def test_empty_vocabulary_is_empty() -> None:
    assert ExtractionVocabulary().is_empty()


def test_entity_type_entries_alone_make_vocabulary_non_empty() -> None:
    """entity entry만 있어도 빈 어휘가 아니다.

    비었다고 보면 프롬프트의 어휘 섹션이 통째로 잘린다.
    """
    vocabulary = ExtractionVocabulary(
        snapshot_id="2",
        entity_type_entries=(
            EntityTypeEntry(
                name="team",
                definition="회사 안에서 역할로 묶인 조직 단위",
                identity_scope="anchored",
            ),
        ),
    )
    assert not vocabulary.is_empty()


def test_predicate_entries_alone_make_vocabulary_non_empty() -> None:
    vocabulary = ExtractionVocabulary(
        snapshot_id="2",
        predicate_entries=(_predicate_entry(),),
    )
    assert not vocabulary.is_empty()


@pytest.fixture(scope="module")
def engine() -> Iterator[Engine]:
    engine = create_engine(settings.sqlalchemy_database_url)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except OperationalError:
        engine.dispose()
        pytest.skip("PostgreSQL이 없어 통합 테스트를 건너뛴다.")

    if not inspect(engine).has_table(SnapshotRow.__tablename__):
        engine.dispose()
        pytest.skip("스냅샷 테이블이 없다. alembic upgrade head가 필요하다.")

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
def ontology_id() -> str:
    return f"catchup.test_vocabulary.{uuid.uuid4().hex}"


def _dictionary_vocabulary() -> ExtractionVocabulary:
    return ExtractionVocabulary(
        snapshot_id="2",
        entity_type_entries=(
            EntityTypeEntry(
                name="team",
                definition="회사 안에서 역할로 묶인 조직 단위",
                identity_scope="anchored",
                examples=("검색팀",),
            ),
        ),
        predicate_entries=(_predicate_entry(),),
        relation_type_entries=(
            RelationTypeEntry(
                name="integrates_with",
                definition="두 system이 서로 연동됨을 나타낸다",
                domain=("system",),
                range_=("system",),
                examples=("CatchUp은 Jira와 연동된다",),
            ),
        ),
    )


def test_entries_survive_postgres_roundtrip(
    workspace_id: int,
    session_factory: Callable[[], Session],
    ontology_id: str,
) -> None:
    """ensure로 저장한 entry 3종이 get으로 그대로 되살아난다."""
    vocabulary = _dictionary_vocabulary()

    with KnowledgeMaintenanceUnitOfWork(session_factory) as uow:
        uow.ontology.ensure(
            workspace_id=workspace_id,
            ontology_id=ontology_id,
            vocabulary=vocabulary,
        )
        uow.commit()

    with KnowledgeMaintenanceUnitOfWork(session_factory) as uow:
        loaded = uow.ontology.get(
            workspace_id=workspace_id,
            ontology_id=ontology_id,
            version="2",
        )

    assert loaded is not None
    assert loaded.entity_type_entries == vocabulary.entity_type_entries
    assert loaded.predicate_entries == vocabulary.predicate_entries
    assert loaded.relation_type_entries == vocabulary.relation_type_entries
    assert loaded.predicates == vocabulary.predicates
    assert loaded.relation_types == vocabulary.relation_types


def test_name_only_snapshot_row_still_loads(
    workspace_id: int,
    session_factory: Callable[[], Session],
    ontology_id: str,
) -> None:
    """entry 없이 이름 목록만 담긴 예전 행도 그대로 읽힌다."""
    with session_factory() as session:
        session.add(
            SnapshotRow(
                id=uuid.uuid4(),
                workspace_id=workspace_id,
                ontology_id=ontology_id,
                version="1",
                predicates=["status", "issue_type"],
                relation_types=["uses"],
            )
        )
        session.commit()

    with KnowledgeMaintenanceUnitOfWork(session_factory) as uow:
        loaded = uow.ontology.get(
            workspace_id=workspace_id,
            ontology_id=ontology_id,
            version="1",
        )

    assert loaded is not None
    assert loaded.predicates == ("status", "issue_type")
    assert loaded.relation_types == ("uses",)
    assert loaded.predicate_entries == ()


def test_same_names_different_definition_conflicts(
    workspace_id: int,
    session_factory: Callable[[], Session],
    ontology_id: str,
) -> None:
    """이름은 같아도 정의가 다르면 사전을 덮어쓰지 않고 거부한다."""
    vocabulary = _dictionary_vocabulary()
    with KnowledgeMaintenanceUnitOfWork(session_factory) as uow:
        uow.ontology.ensure(
            workspace_id=workspace_id,
            ontology_id=ontology_id,
            vocabulary=vocabulary,
        )
        uow.commit()

    rewritten = vocabulary.model_copy(
        update={
            "predicate_entries": (
                _predicate_entry(definition="분당 허용 호출 횟수(수정)"),
            )
        }
    )

    with KnowledgeMaintenanceUnitOfWork(session_factory) as uow:
        with pytest.raises(OntologySnapshotConflict):
            uow.ontology.ensure(
                workspace_id=workspace_id,
                ontology_id=ontology_id,
                vocabulary=rewritten,
            )
