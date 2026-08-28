"""아티팩트 정의의 선택 규칙(SelectionSpec)을 담는다.

선택 규칙은 좁은 스키마다: entity 필터·relation 경로·predicate 섹션
슬롯 3개에 값을 채울 수만 있고 조합 연산은 없다. claim·entity id를
지정하는 필드는 존재하지 않는다 — 정의는 조건이지 목록이 아니며, 같은
정의와 같은 지식 상태면 같은 문서가 나와야 한다. 이름은 어휘 스냅샷에
존재해야 저장된다 — 없는 이름이 조용히 빈 문서를 만드는 것을 저장
시점에 거부한다.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from catchup.knowledge_maintenance.contracts.extraction import ExtractionVocabulary

# 관계 경로의 최대 길이다. 더 멀리 따라가면 문서 하나가 그래프 전체를
# 끌어오게 되므로 정의 단계에서 막는다.
MAX_PATH_DEPTH = 3
# 경로의 한 단계에서 이어붙일 수 있는 이웃 수의 상한이다. 허브 노드
# 하나가 문서를 폭발시키는 것을 컴파일 단계에서 막는 데 쓴다.
MAX_NODES_PER_STEP = 50

DIRECTION_IN = "in"
DIRECTION_OUT = "out"
DIRECTION_ANY = "any"
_DIRECTIONS = frozenset({DIRECTION_IN, DIRECTION_OUT, DIRECTION_ANY})

_SPEC_KEYS = frozenset(
    {"entity_filter", "relation_paths", "predicate_sections"}
)
_ENTITY_FILTER_KEYS = frozenset({"entity_types"})
_PATH_KEYS = frozenset({"steps"})
_STEP_KEYS = frozenset({"type", "dir"})


class SelectionSpecError(ValueError):
    """선택 규칙을 받아들일 수 없음을 알린다."""


@dataclass(frozen=True, slots=True)
class RelationStep:
    """관계 경로의 한 걸음을 표현한다.

    Attributes:
        relation_type: 따라갈 관계 종류의 이름을 나타낸다.
        direction: 관계를 어느 쪽으로 따라갈지 나타낸다.
    """

    relation_type: str
    direction: str


@dataclass(frozen=True, slots=True)
class RelationPath:
    """시작 entity에서 이어지는 관계 경로 하나를 표현한다."""

    steps: tuple[RelationStep, ...]


@dataclass(frozen=True, slots=True)
class SelectionSpec:
    """문서가 어떤 지식을 담을지 정하는 선택 규칙을 표현한다.

    Attributes:
        entity_types: 문서의 시작점이 될 entity 종류를 고른다.
        relation_paths: 시작점에서 따라갈 관계 경로들을 고른다.
        predicate_sections: 문서에 실을 claim 섹션을 고른다. None은
            섹션을 따로 고르지 않았다는 뜻으로, 하나도 고르지 않은
            빈 튜플과 구분된다.
    """

    entity_types: tuple[str, ...]
    relation_paths: tuple[RelationPath, ...]
    predicate_sections: tuple[str, ...] | None


def validate_selection_spec(
    spec: SelectionSpec, vocabulary: ExtractionVocabulary
) -> None:
    """선택 규칙이 어휘 스냅샷과 맞는지 검사한다.

    이름이 어휘에 없으면 통과시키지 않는다(fail-closed). 오타 하나가
    조용히 빈 문서를 만들어 검토자가 지식이 없다고 오해하는 것이 이
    검증이 막으려는 사고다.

    Raises:
        SelectionSpecError: entity 종류가 비었거나 중복이거나, 이름이
            어휘에 없거나, 경로 길이·방향이 규약을 벗어났을 때 던진다.
    """
    _validate_entity_types(spec.entity_types, vocabulary)
    _validate_relation_paths(spec.relation_paths, vocabulary)
    _validate_predicate_sections(spec.predicate_sections, vocabulary)


def _validate_entity_types(
    entity_types: tuple[str, ...], vocabulary: ExtractionVocabulary
) -> None:
    """시작점 entity 종류를 검사한다.

    Raises:
        SelectionSpecError: 비었거나 중복이거나 어휘에 없을 때 던진다.
    """
    if not entity_types:
        raise SelectionSpecError(
            "entity_types가 비었다: 문서의 시작점이 하나는 있어야 한다"
        )
    duplicated = _duplicates(entity_types)
    if duplicated:
        raise SelectionSpecError(f"entity_types가 중복됐다: {duplicated}")
    for name in entity_types:
        if vocabulary.entity_type_entry(name) is None:
            raise SelectionSpecError(
                f"어휘에 없는 entity 종류다: {name!r}"
            )


def _validate_relation_paths(
    relation_paths: tuple[RelationPath, ...],
    vocabulary: ExtractionVocabulary,
) -> None:
    """관계 경로들의 길이·방향·이름을 검사한다.

    Raises:
        SelectionSpecError: 경로가 비었거나 상한을 넘었거나, 방향이
            규약 밖이거나, 관계 종류가 어휘에 없을 때 던진다.
    """
    known = {entry.name for entry in vocabulary.relation_type_entries}
    for index, path in enumerate(relation_paths):
        if not path.steps:
            raise SelectionSpecError(
                f"relation_paths[{index}]: 경로에 단계가 없다"
            )
        if len(path.steps) > MAX_PATH_DEPTH:
            raise SelectionSpecError(
                f"relation_paths[{index}]: 경로 길이 {len(path.steps)}가"
                f" 상한 {MAX_PATH_DEPTH}을 넘었다"
            )
        for step_index, step in enumerate(path.steps):
            if step.direction not in _DIRECTIONS:
                raise SelectionSpecError(
                    f"relation_paths[{index}].steps[{step_index}]:"
                    f" 알 수 없는 방향 {step.direction!r}"
                )
            if step.relation_type not in known:
                raise SelectionSpecError(
                    f"relation_paths[{index}].steps[{step_index}]:"
                    f" 어휘에 없는 관계 종류다 {step.relation_type!r}"
                )


def _validate_predicate_sections(
    predicate_sections: tuple[str, ...] | None,
    vocabulary: ExtractionVocabulary,
) -> None:
    """문서에 실을 claim 섹션 이름을 검사한다.

    Raises:
        SelectionSpecError: 중복이거나 어휘에 없을 때 던진다.
    """
    if predicate_sections is None:
        return
    duplicated = _duplicates(predicate_sections)
    if duplicated:
        raise SelectionSpecError(
            f"predicate_sections가 중복됐다: {duplicated}"
        )
    for name in predicate_sections:
        if vocabulary.predicate_entry(name) is None:
            raise SelectionSpecError(f"어휘에 없는 predicate다: {name!r}")


def _duplicates(names: Sequence[str]) -> list[str]:
    """같은 이름이 두 번 이상 나온 것들을 모은다."""
    return sorted({name for name in names if names.count(name) > 1})


def serialize_selection_spec(spec: SelectionSpec) -> dict[str, Any]:
    """선택 규칙을 JSONB 저장 형태로 바꾼다.

    predicate_sections의 None은 그대로 null로 적는다. 섹션을 고르지
    않은 것과 하나도 고르지 않은 것은 다른 뜻이기 때문이다.
    """
    return {
        "entity_filter": {"entity_types": list(spec.entity_types)},
        "relation_paths": [
            {
                "steps": [
                    {"type": step.relation_type, "dir": step.direction}
                    for step in path.steps
                ]
            }
            for path in spec.relation_paths
        ],
        "predicate_sections": (
            None
            if spec.predicate_sections is None
            else list(spec.predicate_sections)
        ),
    }


def deserialize_selection_spec(value: Any) -> SelectionSpec:
    """JSONB 저장 형태를 선택 규칙으로 되돌린다.

    어휘 검증은 하지 않는다. 그것은 validate_selection_spec의 몫이며,
    역직렬화는 어휘가 바뀐 뒤에 저장된 값도 읽어낼 수 있어야 한다.

    스키마 밖의 키는 거부한다. 조합 연산 같은 필드가 저장 형태로
    슬쩍 들어와 선택 규칙이 질의 언어로 자라는 것을 막는 경계다.

    Raises:
        SelectionSpecError: 모양이 mapping이 아니거나, 알 수 없는
            키가 있거나, 값의 타입이 규약과 다를 때 던진다.
    """
    payload = _require_mapping(value, "selection_spec")
    _reject_unknown_keys(payload, _SPEC_KEYS, "selection_spec")
    entity_filter = _require_mapping(
        payload.get("entity_filter", {}), "entity_filter"
    )
    _reject_unknown_keys(entity_filter, _ENTITY_FILTER_KEYS, "entity_filter")
    entity_types = _require_str_tuple(
        entity_filter.get("entity_types", ()), "entity_filter.entity_types"
    )
    raw_sections = payload.get("predicate_sections")
    return SelectionSpec(
        entity_types=entity_types,
        relation_paths=_parse_relation_paths(payload.get("relation_paths")),
        predicate_sections=(
            None
            if raw_sections is None
            else _require_str_tuple(raw_sections, "predicate_sections")
        ),
    )


def _parse_relation_paths(value: Any) -> tuple[RelationPath, ...]:
    """저장된 관계 경로들을 되돌린다. 값이 없으면 빈 튜플이다.

    Raises:
        SelectionSpecError: 경로나 단계의 모양이 규약과 다를 때 던진다.
    """
    paths: list[RelationPath] = []
    for index, raw_path in enumerate(_require_list(value, "relation_paths")):
        field = f"relation_paths[{index}]"
        path = _require_mapping(raw_path, field)
        _reject_unknown_keys(path, _PATH_KEYS, field)
        steps: list[RelationStep] = []
        raw_steps = _require_list(path.get("steps"), f"{field}.steps")
        for step_index, raw_step in enumerate(raw_steps):
            step_field = f"{field}.steps[{step_index}]"
            step = _require_mapping(raw_step, step_field)
            _reject_unknown_keys(step, _STEP_KEYS, step_field)
            steps.append(
                RelationStep(
                    relation_type=_require_str(
                        step.get("type"), f"{step_field}.type"
                    ),
                    direction=_require_str(
                        step.get("dir"), f"{step_field}.dir"
                    ),
                )
            )
        paths.append(RelationPath(steps=tuple(steps)))
    return tuple(paths)


def _require_mapping(value: Any, field: str) -> Mapping[str, Any]:
    """값이 mapping인지 확인한다.

    Raises:
        SelectionSpecError: mapping이 아닐 때 던진다.
    """
    if not isinstance(value, Mapping):
        raise SelectionSpecError(f"{field}: 객체가 아니다 {value!r}")
    return value


def _require_list(value: Any, field: str) -> Sequence[Any]:
    """값이 목록인지 확인한다. 없으면 빈 목록으로 본다.

    문자열은 목록이 아니다. 문자 하나씩 순회해 조용히 잘못 읽히는 것을
    막으려고 따로 거른다.

    Raises:
        SelectionSpecError: 목록이 아닐 때 던진다.
    """
    if value is None:
        return ()
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise SelectionSpecError(f"{field}: 목록이 아니다 {value!r}")
    return value


def _require_str(value: Any, field: str) -> str:
    """값이 비어 있지 않은 문자열인지 확인한다.

    Raises:
        SelectionSpecError: 문자열이 아니거나 비었을 때 던진다.
    """
    if not isinstance(value, str) or not value.strip():
        raise SelectionSpecError(f"{field}: 이름이 아니다 {value!r}")
    return value


def _require_str_tuple(value: Any, field: str) -> tuple[str, ...]:
    """값이 이름 목록인지 확인하고 튜플로 바꾼다.

    Raises:
        SelectionSpecError: 목록이 아니거나 원소가 이름이 아닐 때 던진다.
    """
    items = _require_list(value, field)
    return tuple(
        _require_str(item, f"{field}[{index}]")
        for index, item in enumerate(items)
    )


def _reject_unknown_keys(
    payload: Mapping[str, Any], allowed: frozenset[str], field: str
) -> None:
    """스키마에 없는 키를 거부한다.

    Raises:
        SelectionSpecError: 허용되지 않은 키가 있을 때 던진다.
    """
    unknown = sorted(set(payload) - allowed)
    if unknown:
        raise SelectionSpecError(
            f"{field}: 스키마에 없는 키다 {unknown}"
        )
