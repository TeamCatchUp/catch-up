from __future__ import annotations

from catchup.knowledge_maintenance.domain.claim_conflict import normalize_value


def test_number_values_compare_numerically() -> None:
    assert normalize_value("number", 60) == normalize_value("number", 60.0)
    assert normalize_value("number", "60") == normalize_value("number", 60)


def test_boolean_and_enum_normalize_as_strings() -> None:
    assert normalize_value("boolean", True) == normalize_value(
        "boolean", "true"
    )
    assert normalize_value("enum", " 지원 ") == normalize_value(
        "enum", "지원"
    )


def test_unparseable_value_returns_none() -> None:
    assert normalize_value("number", "약 60회") is None
    assert normalize_value("date", "다음 달") is None


def test_date_normalizes_to_iso_prefix() -> None:
    assert normalize_value("date", "2026-09") == "2026-09"


def test_text_values_are_not_compared() -> None:
    """text는 비교 키를 만들지 않는다. 표현 차이가 모순이 아니기 때문이다."""
    assert normalize_value("text", "9월 예정") is None
