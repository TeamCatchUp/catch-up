"""아티팩트 정의의 선택 규칙 검증을 확인한다.

선택 규칙은 좁은 스키마다 — 슬롯 3개(entity 필터·relation 경로·predicate
섹션)에 값을 채울 수만 있고 조합 연산이 없다. id 박제는 스키마에 필드
자체가 없어 구조적으로 불가능하며, 이름은 어휘에 존재해야 한다 — 오타가
조용히 빈 문서를 만드는 대신 저장 시점에 거부된다.
"""

import pytest

from catchup.knowledge_maintenance.contracts.extraction import EntityTypeEntry
from catchup.knowledge_maintenance.contracts.extraction import ExtractionVocabulary
from catchup.knowledge_maintenance.contracts.extraction import PredicateEntry
from catchup.knowledge_maintenance.contracts.extraction import RelationTypeEntry
from catchup.knowledge_maintenance.domain.artifact_definition import RelationPath
from catchup.knowledge_maintenance.domain.artifact_definition import RelationStep
from catchup.knowledge_maintenance.domain.artifact_definition import SelectionSpec
from catchup.knowledge_maintenance.domain.artifact_definition import SelectionSpecError
from catchup.knowledge_maintenance.domain.artifact_definition import (
    deserialize_selection_spec,
)
from catchup.knowledge_maintenance.domain.artifact_definition import (
    serialize_selection_spec,
)
from catchup.knowledge_maintenance.domain.artifact_definition import (
    validate_selection_spec,
)


def _vocabulary() -> ExtractionVocabulary:
    # 사전 항목의 필수 필드는 contracts/extraction.py 정의에 맞춘다 —
    # identity_scope는 기본값이 없고, domain·range_는 이름 튜플이다.
    return ExtractionVocabulary(
        entity_type_entries=(
            EntityTypeEntry(
                name="feature_request",
                definition="고객 요구",
                identity_scope="standalone",
            ),
        ),
        predicate_entries=(
            PredicateEntry(
                name="status",
                definition="상태",
                domain=("feature_request",),
                value_type="enum",
                enum_values=("검토중", "확정"),
            ),
        ),
        relation_type_entries=(
            RelationTypeEntry(
                name="requested_by",
                definition="요청 주체",
                domain=("feature_request",),
                range_=("customer",),
            ),
        ),
    )


def _valid_spec() -> SelectionSpec:
    return SelectionSpec(
        entity_types=("feature_request",),
        relation_paths=(
            RelationPath(steps=(RelationStep("requested_by", "in"),)),
        ),
        predicate_sections=("status",),
    )


def test_valid_spec_passes():
    validate_selection_spec(_valid_spec(), _vocabulary())


def test_empty_entity_types_rejected():
    spec = SelectionSpec(
        entity_types=(), relation_paths=(), predicate_sections=None
    )
    with pytest.raises(SelectionSpecError):
        validate_selection_spec(spec, _vocabulary())


def test_duplicate_names_rejected():
    vocab = _vocabulary()
    duplicated_entity = SelectionSpec(
        entity_types=("feature_request", "feature_request"),
        relation_paths=(),
        predicate_sections=None,
    )
    with pytest.raises(SelectionSpecError):
        validate_selection_spec(duplicated_entity, vocab)
    duplicated_predicate = SelectionSpec(
        entity_types=("feature_request",),
        relation_paths=(),
        predicate_sections=("status", "status"),
    )
    with pytest.raises(SelectionSpecError):
        validate_selection_spec(duplicated_predicate, vocab)


def test_unknown_names_rejected():
    # entity_type·relation_type·predicate 각각 어휘에 없으면 거부된다.
    vocab = _vocabulary()
    unknown_entity = SelectionSpec(
        entity_types=("ghost",), relation_paths=(), predicate_sections=None
    )
    with pytest.raises(SelectionSpecError):
        validate_selection_spec(unknown_entity, vocab)
    unknown_relation = SelectionSpec(
        entity_types=("feature_request",),
        relation_paths=(
            RelationPath(steps=(RelationStep("ghost_rel", "in"),)),
        ),
        predicate_sections=None,
    )
    with pytest.raises(SelectionSpecError):
        validate_selection_spec(unknown_relation, vocab)
    unknown_predicate = SelectionSpec(
        entity_types=("feature_request",),
        relation_paths=(),
        predicate_sections=("ghost_pred",),
    )
    with pytest.raises(SelectionSpecError):
        validate_selection_spec(unknown_predicate, vocab)


def test_path_depth_capped_at_three():
    step = RelationStep("requested_by", "in")
    with pytest.raises(SelectionSpecError):
        validate_selection_spec(
            SelectionSpec(
                entity_types=("feature_request",),
                relation_paths=(RelationPath(steps=(step,) * 4),),
                predicate_sections=None,
            ),
            _vocabulary(),
        )


def test_empty_path_rejected():
    with pytest.raises(SelectionSpecError):
        validate_selection_spec(
            SelectionSpec(
                entity_types=("feature_request",),
                relation_paths=(RelationPath(steps=()),),
                predicate_sections=None,
            ),
            _vocabulary(),
        )


def test_invalid_direction_rejected():
    with pytest.raises(SelectionSpecError):
        validate_selection_spec(
            SelectionSpec(
                entity_types=("feature_request",),
                relation_paths=(
                    RelationPath(
                        steps=(RelationStep("requested_by", "sideways"),)
                    ),
                ),
                predicate_sections=None,
            ),
            _vocabulary(),
        )


def test_serialize_round_trip():
    spec = _valid_spec()
    assert deserialize_selection_spec(serialize_selection_spec(spec)) == spec


def test_serialize_round_trip_without_predicate_sections():
    # None과 빈 튜플은 다른 뜻이다 — 섹션을 고르지 않음과 하나도 고르지
    # 않음이 왕복에서 뒤섞이지 않아야 한다.
    spec = SelectionSpec(
        entity_types=("feature_request",),
        relation_paths=(),
        predicate_sections=None,
    )
    restored = deserialize_selection_spec(serialize_selection_spec(spec))
    assert restored == spec
    assert restored.predicate_sections is None


def test_deserialize_rejects_unknown_keys():
    # 슬롯 3개 외의 키는 스키마 밖이다 — DSL로 자라는 것을 막는 경계.
    payload = serialize_selection_spec(_valid_spec())
    payload["combine"] = {"or": []}
    with pytest.raises(SelectionSpecError):
        deserialize_selection_spec(payload)


def test_deserialize_rejects_unknown_step_keys():
    payload = serialize_selection_spec(_valid_spec())
    payload["relation_paths"][0]["steps"][0]["hops"] = 2
    with pytest.raises(SelectionSpecError):
        deserialize_selection_spec(payload)


def test_deserialize_rejects_malformed_payload():
    with pytest.raises(SelectionSpecError):
        deserialize_selection_spec(["entity_filter"])
    with pytest.raises(SelectionSpecError):
        deserialize_selection_spec(
            {"entity_filter": {"entity_types": "feature_request"}}
        )
