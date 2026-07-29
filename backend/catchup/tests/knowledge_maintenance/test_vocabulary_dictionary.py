"""어휘 사전 entry 계약과 vocabulary 확장을 검증한다."""

from __future__ import annotations

import pytest

from catchup.knowledge_maintenance.contracts.extraction import EntityTypeEntry
from catchup.knowledge_maintenance.contracts.extraction import ExtractionVocabulary
from catchup.knowledge_maintenance.contracts.extraction import PredicateEntry


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
