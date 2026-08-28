from __future__ import annotations

from datetime import datetime
from datetime import timezone

import pytest
from pydantic import ValidationError

from catchup.knowledge_maintenance.contracts.extraction import ClaimCandidateDraft
from catchup.knowledge_maintenance.contracts.extraction import EntityCandidateDraft
from catchup.knowledge_maintenance.contracts.extraction import KnowledgeCandidateBatch
from catchup.knowledge_maintenance.contracts.extraction import (
    RelationAssertionCandidateDraft,
)


def _entity(local_key: str = "e1", **overrides: object) -> EntityCandidateDraft:
    values: dict[str, object] = {
        "local_key": local_key,
        "proposed_type": "feature",
        "proposed_name": "결제 기능",
    }
    values.update(overrides)
    return EntityCandidateDraft.model_validate(values)


def _claim(**overrides: object) -> ClaimCandidateDraft:
    values: dict[str, object] = {
        "local_key": "c1",
        "subject_local_key": "e1",
        "predicate": "release_month",
        "value_type": "text",
        "value": "2026-09",
        "statement": "결제 기능은 9월 출시 예정이다.",
    }
    values.update(overrides)
    return ClaimCandidateDraft.model_validate(values)


def _relation(**overrides: object) -> RelationAssertionCandidateDraft:
    values: dict[str, object] = {
        "local_key": "r1",
        "source_local_key": "e1",
        "target_local_key": "e2",
        "relation_type": "depends_on",
        "assertion_text": "결제 기능은 인증 시스템에 의존한다.",
    }
    values.update(overrides)
    return RelationAssertionCandidateDraft.model_validate(values)


def test_claim_pointing_to_unknown_subject_is_rejected() -> None:
    with pytest.raises(ValidationError):
        KnowledgeCandidateBatch(
            entities=[_entity("e1")],
            claims=[_claim(subject_local_key="사라진-엔티티")],
            relation_assertions=[],
        )


def test_relation_pointing_to_unknown_endpoint_is_rejected() -> None:
    with pytest.raises(ValidationError):
        KnowledgeCandidateBatch(
            entities=[_entity("e1")],
            claims=[],
            relation_assertions=[_relation(target_local_key="e2")],
        )


def test_duplicate_local_key_is_rejected() -> None:
    with pytest.raises(ValidationError):
        KnowledgeCandidateBatch(
            entities=[_entity("e1"), _entity("e1", proposed_name="다른 이름")],
            claims=[],
            relation_assertions=[],
        )


def test_batch_with_resolvable_references_is_accepted() -> None:
    batch = KnowledgeCandidateBatch(
        entities=[_entity("e1"), _entity("e2", proposed_name="인증 시스템")],
        claims=[_claim()],
        relation_assertions=[_relation()],
    )

    assert len(batch.entities) == 2
    assert batch.claims[0].subject_local_key == "e1"


def test_metadata_reference_is_allowed_as_a_relation_endpoint() -> None:
    """레이어 1이 확정한 Entity는 batch 안에 없어도 가리킬 수 있다.

    고객이 무엇을 물었는지 같은 관계는 이 참조 없이는 표현할 수 없다.
    """
    batch = KnowledgeCandidateBatch(
        entities=[_entity("e1")],
        relation_assertions=[
            _relation(source_local_key="m1", target_local_key="e1")
        ],
    )

    assert batch.metadata_references() == frozenset({"m1"})


def test_metadata_reference_is_allowed_as_a_claim_subject() -> None:
    batch = KnowledgeCandidateBatch(
        entities=[_entity("e1")],
        claims=[_claim(subject_local_key="m2")],
    )

    assert batch.metadata_references() == frozenset({"m2"})


def test_reserved_key_cannot_name_a_new_entity() -> None:
    """`m1`은 이미 확정된 Entity의 자리이므로 새로 만들 수 없다."""
    with pytest.raises(ValidationError, match="예약된"):
        KnowledgeCandidateBatch(entities=[_entity("m1")])


def test_unknown_reference_is_still_rejected() -> None:
    """metadata 참조가 아닌 미지의 키는 그대로 막는다."""
    with pytest.raises(ValidationError, match="endpoint"):
        KnowledgeCandidateBatch(
            entities=[_entity("e1")],
            relation_assertions=[
                _relation(source_local_key="e1", target_local_key="e9")
            ],
        )


def test_metadata_reference_must_exist_in_the_request() -> None:
    """요청에 없던 metadata Entity를 지어내면 걸러진다."""
    batch = KnowledgeCandidateBatch(
        entities=[_entity("e1")],
        relation_assertions=[
            _relation(source_local_key="m3", target_local_key="e1")
        ],
    )

    batch.validate_metadata_references(frozenset({"m1", "m2", "m3"}))

    with pytest.raises(ValueError, match="m3"):
        batch.validate_metadata_references(frozenset({"m1", "m2"}))


# validity 경계는 claim의 값과 형식이 다르다. 값에는 `2026`, `2026-09` 같은
# 부분 날짜가 허용되지만, 경계는 완전한 달력 날짜만 받는다. 부분 날짜가
# 경계로 새어들면 pydantic이 Unix timestamp로 읽어 1970으로 변질시키거나
# 배치 전체를 탈락시킨다.


@pytest.mark.parametrize("bound", ["valid_from", "valid_to"])
def test_year_only_bound_is_rejected_instead_of_becoming_1970(bound) -> None:
    """연도만 있는 경계는 epoch 초로 읽히지 않고 거부된다."""
    with pytest.raises(ValidationError):
        _claim(**{bound: "2026"})
    with pytest.raises(ValidationError):
        _relation(**{bound: "2026"})


@pytest.mark.parametrize("bound", ["valid_from", "valid_to"])
def test_year_month_bound_is_rejected(bound) -> None:
    """연-월까지만 아는 경계는 채우지 않고 거부한다."""
    with pytest.raises(ValidationError):
        _claim(**{bound: "2026-09"})
    with pytest.raises(ValidationError):
        _relation(**{bound: "2026-09"})


@pytest.mark.parametrize("bound", ["valid_from", "valid_to"])
def test_numeric_bound_is_rejected(bound) -> None:
    """숫자로 들어온 경계는 timestamp로 해석하지 않는다."""
    with pytest.raises(ValidationError):
        _claim(**{bound: 2026})
    with pytest.raises(ValidationError):
        _relation(**{bound: 1782000000})


@pytest.mark.parametrize("bound", ["valid_from", "valid_to"])
def test_full_calendar_date_becomes_utc_midnight(bound) -> None:
    """`YYYY-MM-DD`는 그 날 UTC 자정으로 읽는다."""
    expected = datetime(2026, 9, 15, tzinfo=timezone.utc)

    assert getattr(_claim(**{bound: "2026-09-15"}), bound) == expected
    assert getattr(_relation(**{bound: "2026-09-15"}), bound) == expected


@pytest.mark.parametrize("bound", ["valid_from", "valid_to"])
def test_aware_iso_bound_passes_through(bound) -> None:
    """tz가 붙은 완전한 시각은 그대로 통과한다."""
    claim = _claim(**{bound: "2026-09-15T10:30:00+00:00"})

    assert getattr(claim, bound) == datetime(2026, 9, 15, 10, 30, tzinfo=timezone.utc)


@pytest.mark.parametrize("bound", ["valid_from", "valid_to"])
def test_naive_iso_bound_is_read_as_utc(bound) -> None:
    """tz 없는 시각은 UTC로 본다. 파이프라인의 시각 기준이 UTC이기 때문이다."""
    expected = datetime(2026, 9, 15, 10, 30, tzinfo=timezone.utc)

    assert getattr(_claim(**{bound: "2026-09-15T10:30:00"}), bound) == expected
    assert (
        getattr(_relation(**{bound: datetime(2026, 9, 15, 10, 30)}), bound) == expected
    )


def test_empty_bound_stays_empty() -> None:
    """확정할 수 없어 비워 보낸 경계는 None으로 남는다."""
    assert _claim(valid_from=None).valid_from is None
    assert _claim(valid_to="").valid_to is None
