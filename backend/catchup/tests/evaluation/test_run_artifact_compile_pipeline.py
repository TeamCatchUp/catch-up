"""카드 컴파일 러너의 정의 고르기를 확인한다.

러너는 정의 하나만 돌려 볼 수 있어야 한다. 그 고르기를 컴파일 서비스에
인자로 두면 "workspace의 정의를 전부 돈다"는 계약이 무너지므로, 러너가
UnitOfWork를 감싸 정의 목록을 가린다. 그 가림막이 정의만 가리고 나머지
저장소와 transaction 경계는 그대로 통과시키는지 못 박는다.

DB도 LLM도 부르지 않는다.
"""

from __future__ import annotations

import uuid
from typing import Any

from catchup.evaluation.run_artifact_compile_pipeline import only_definition
from catchup.knowledge_maintenance.domain.artifact_definition import SelectionSpec
from catchup.knowledge_maintenance.ports.artifact_definitions import (
    StoredArtifactDefinition,
)

FIRST_ID = uuid.UUID("00000000-0000-4000-8000-000000000001")
SECOND_ID = uuid.UUID("ffffffff-0000-4000-8000-000000000002")


def _definition(definition_id: uuid.UUID) -> StoredArtifactDefinition:
    """정의 한 줄을 만든다. 여기서 보는 것은 식별자뿐이다."""
    return StoredArtifactDefinition(
        id=definition_id,
        channel_id=uuid.uuid4(),
        kind="entity_summary",
        selection_spec=SelectionSpec(
            entity_types=("feature_request",),
            relation_paths=(),
            predicate_sections=None,
        ),
        title_prefix="entity_summary",
    )


class _FakeDefinitionRepository:
    """정의 목록을 그대로 돌려주는 저장소를 대신한다."""

    def __init__(self, definitions: tuple[StoredArtifactDefinition, ...]):
        self.definitions = definitions

    def list_definitions(self) -> tuple[StoredArtifactDefinition, ...]:
        return self.definitions


class _FakeUnitOfWork:
    """저장소 몇 개와 transaction 경계만 갖춘 UnitOfWork를 대신한다.

    실제 UnitOfWork는 저장소를 `__enter__`에서 만든다. 감싸는 쪽이 그
    시점을 앞질러 저장소를 붙들면 실행 때 없는 것을 잡으므로, fake도
    같은 시점에 붙인다.
    """

    def __init__(self, definitions: tuple[StoredArtifactDefinition, ...]):
        self._definitions = definitions
        self.artifacts = object()
        self.entered = 0
        self.exited = 0
        self.committed = 0

    def __enter__(self) -> _FakeUnitOfWork:
        self.entered += 1
        self.artifact_definitions = _FakeDefinitionRepository(
            self._definitions
        )
        return self

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        self.exited += 1

    def commit(self) -> None:
        self.committed += 1


def test_only_the_chosen_definition_is_listed() -> None:
    """고른 정의 하나만 컴파일 입구에 보인다."""
    inner = _FakeUnitOfWork((_definition(FIRST_ID), _definition(SECOND_ID)))
    wrapped = only_definition(inner, SECOND_ID)

    with wrapped:
        listed = wrapped.artifact_definitions.list_definitions()

    assert [item.id for item in listed] == [SECOND_ID]


def test_unknown_definition_id_lists_nothing() -> None:
    """없는 식별자를 고르면 빈 목록이다.

    엉뚱한 정의를 대신 돌리는 것보다 아무것도 하지 않는 편이 낫다.
    """
    inner = _FakeUnitOfWork((_definition(FIRST_ID),))
    wrapped = only_definition(inner, SECOND_ID)

    with wrapped:
        assert wrapped.artifact_definitions.list_definitions() == ()


def test_other_repositories_and_boundary_pass_through() -> None:
    """정의 말고는 감싸지 않고 그대로 통과시킨다."""
    inner = _FakeUnitOfWork((_definition(FIRST_ID),))
    wrapped = only_definition(inner, FIRST_ID)

    with wrapped:
        assert wrapped.artifacts is inner.artifacts
        wrapped.commit()

    assert inner.entered == 1
    assert inner.exited == 1
    assert inner.committed == 1
