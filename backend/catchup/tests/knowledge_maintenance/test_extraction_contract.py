from __future__ import annotations

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
