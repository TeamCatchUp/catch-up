from __future__ import annotations

import uuid
from datetime import UTC
from datetime import datetime

import pytest

from catchup.knowledge_maintenance.domain.artifact import BLOCK_KIND_CLAIM_SECTION
from catchup.knowledge_maintenance.domain.artifact import BLOCK_KIND_OPEN_QUESTION
from catchup.knowledge_maintenance.domain.artifact import ArtifactBlock
from catchup.knowledge_maintenance.domain.artifact import ArtifactBlockError
from catchup.knowledge_maintenance.domain.artifact import BlockSource
from catchup.knowledge_maintenance.domain.artifact import artifact_idempotency_key
from catchup.knowledge_maintenance.domain.artifact import blocks_content_hash
from catchup.knowledge_maintenance.domain.artifact import deserialize_blocks
from catchup.knowledge_maintenance.domain.artifact import serialize_blocks
from catchup.knowledge_maintenance.domain.artifact import validate_blocks

_CLAIM_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
_PROPOSAL_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
_OBSERVED_AT = datetime(2026, 8, 7, 12, 30, tzinfo=UTC)


def _claim_block(
    heading: str,
    body: str = "60",
    sources: tuple[BlockSource, ...] = (),
) -> ArtifactBlock:
    """근거 하나를 가진 정상 claim_section 블록을 만든다."""
    return ArtifactBlock(
        block_kind=BLOCK_KIND_CLAIM_SECTION,
        heading=heading,
        body=body,
        claim_ids=(_CLAIM_ID,),
        proposal_ids=(),
        ontology_version="v2",
        sources=sources,
    )


def _block_source(
    claim_id: uuid.UUID = _CLAIM_ID,
    statement: str = "분당 60건으로 제한한다",
    citation_verified: bool | None = True,
) -> BlockSource:
    """검증된 근거 인용 하나를 만든다."""
    return BlockSource(
        claim_id=claim_id,
        statement=statement,
        observed_at=_OBSERVED_AT,
        citation_verified=citation_verified,
    )


def _question_block(heading: str) -> ArtifactBlock:
    """근거 하나를 가진 정상 open_question 블록을 만든다."""
    return ArtifactBlock(
        block_kind=BLOCK_KIND_OPEN_QUESTION,
        heading=heading,
        body="확인 필요",
        claim_ids=(),
        proposal_ids=(_PROPOSAL_ID,),
        ontology_version=None,
    )


def test_claim_section_without_claims_rejected() -> None:
    block = ArtifactBlock(
        block_kind=BLOCK_KIND_CLAIM_SECTION,
        heading="rate_limit_per_minute",
        body="60",
        claim_ids=(),
        proposal_ids=(),
        ontology_version="v2",
    )
    with pytest.raises(ArtifactBlockError):
        validate_blocks([block])


def test_open_question_without_proposals_rejected() -> None:
    block = ArtifactBlock(
        block_kind=BLOCK_KIND_OPEN_QUESTION,
        heading="정책 확정 여부",
        body="확인 필요",
        claim_ids=(),
        proposal_ids=(),
        ontology_version=None,
    )
    with pytest.raises(ArtifactBlockError):
        validate_blocks([block])


def test_unknown_block_kind_rejected() -> None:
    block = ArtifactBlock(
        block_kind="freeform",
        heading="잡담",
        body="아무말",
        claim_ids=(_CLAIM_ID,),
        proposal_ids=(),
        ontology_version=None,
    )
    with pytest.raises(ArtifactBlockError):
        validate_blocks([block])


def test_valid_blocks_pass_validation() -> None:
    validate_blocks([_claim_block("h1"), _question_block("q1")])


def test_serialize_deserialize_round_trip() -> None:
    blocks = (_claim_block("h1"), _question_block("q1"))
    assert deserialize_blocks(serialize_blocks(blocks)) == blocks


def test_deserialize_missing_key_raises_block_error() -> None:
    """필수 키가 없으면 KeyError가 아니라 모듈 예외로 알린다."""
    with pytest.raises(ArtifactBlockError):
        deserialize_blocks([{}])


def test_deserialize_invalid_uuid_raises_block_error() -> None:
    """UUID 파싱 실패도 모듈 예외로 감싼다."""
    payload = serialize_blocks([_claim_block("h1")])[0]
    corrupted = {**payload, "claim_ids": ["not-a-uuid"]}
    with pytest.raises(ArtifactBlockError):
        deserialize_blocks([corrupted])


def test_serialize_writes_uuid_as_string() -> None:
    payload = serialize_blocks([_claim_block("h1")])[0]
    assert payload["claim_ids"] == [str(_CLAIM_ID)]
    assert payload["proposal_ids"] == []


def test_same_blocks_produce_same_hash() -> None:
    first = blocks_content_hash([_claim_block("h1"), _question_block("q1")])
    second = blocks_content_hash([_claim_block("h1"), _question_block("q1")])
    assert first == second


def test_content_hash_is_order_sensitive() -> None:
    a, b = _claim_block("h1"), _claim_block("h2")
    assert blocks_content_hash([a, b]) != blocks_content_hash([b, a])


def test_content_hash_changes_with_one_character_body_diff() -> None:
    a = _claim_block("h1", body="60")
    b = _claim_block("h1", body="61")
    assert blocks_content_hash([a]) != blocks_content_hash([b])


def test_sources_roundtrip_through_serialization() -> None:
    """근거 인용은 저장 형태를 왕복해도 값이 그대로 남는다."""
    blocks = (
        _claim_block(
            "h1",
            sources=(
                _block_source(),
                _block_source(
                    statement="예외는 없다", citation_verified=False
                ),
                _block_source(statement="출처 미확인", citation_verified=None),
            ),
        ),
    )
    assert deserialize_blocks(serialize_blocks(blocks)) == blocks


def test_deserialize_without_sources_key_yields_empty_tuple() -> None:
    """옛 저장 형태에는 sources 키가 없으니 빈 튜플로 읽는다."""
    payload = serialize_blocks([_claim_block("h1")])[0]
    legacy = {
        key: value for key, value in payload.items() if key != "sources"
    }
    (block,) = deserialize_blocks([legacy])
    assert block.sources == ()


def test_validate_blocks_rejects_source_outside_claim_ids() -> None:
    """근거 인용의 claim_id는 블록 claim_ids의 부분집합이어야 한다."""
    stranger = uuid.UUID("66666666-6666-6666-6666-666666666666")
    block = _claim_block("h1", sources=(_block_source(claim_id=stranger),))
    with pytest.raises(ArtifactBlockError):
        validate_blocks([block])


def test_content_hash_changes_when_sources_added() -> None:
    """sources가 붙으면 내용 지문이 달라져 재컴파일이 전파된다."""
    without = _claim_block("h1")
    with_sources = _claim_block("h1", sources=(_block_source(),))
    assert blocks_content_hash([without]) != blocks_content_hash(
        [with_sources]
    )


def test_deserialize_source_with_bad_uuid_raises_block_error() -> None:
    """sources의 claim_id가 UUID가 아니면 모듈 예외로 알린다."""
    block = _claim_block("h1", sources=(_block_source(),))
    payload = serialize_blocks([block])[0]
    corrupted = {
        **payload,
        "sources": [{**payload["sources"][0], "claim_id": "not-a-uuid"}],
    }
    with pytest.raises(ArtifactBlockError):
        deserialize_blocks([corrupted])


def test_deserialize_source_with_bad_datetime_raises_block_error() -> None:
    """observed_at이 ISO 형식이 아니면 모듈 예외로 알린다."""
    block = _claim_block("h1", sources=(_block_source(),))
    payload = serialize_blocks([block])[0]
    corrupted = {
        **payload,
        "sources": [{**payload["sources"][0], "observed_at": "어제"}],
    }
    with pytest.raises(ArtifactBlockError):
        deserialize_blocks([corrupted])


def test_deserialize_source_with_string_verified_raises_block_error() -> None:
    """문자열 "false"를 검증 통과로 뒤집지 않고 손상으로 알린다."""
    block = _claim_block("h1", sources=(_block_source(),))
    payload = serialize_blocks([block])[0]
    corrupted = {
        **payload,
        "sources": [
            {**payload["sources"][0], "citation_verified": "false"}
        ],
    }
    with pytest.raises(ArtifactBlockError):
        deserialize_blocks([corrupted])


def test_idempotency_key_is_stable_and_distinct() -> None:
    artifact_id = uuid.UUID("33333333-3333-3333-3333-333333333333")
    other_id = uuid.UUID("44444444-4444-4444-4444-444444444444")
    content_hash = blocks_content_hash([_claim_block("h1")])
    base = uuid.UUID("55555555-5555-5555-5555-555555555555")
    key = artifact_idempotency_key(
        artifact_id, content_hash, base_revision_id=None
    )
    assert key == artifact_idempotency_key(
        artifact_id, content_hash, base_revision_id=None
    )
    assert key != artifact_idempotency_key(
        other_id, content_hash, base_revision_id=None
    )
    assert key != artifact_idempotency_key(
        artifact_id, content_hash, base_revision_id=base
    )
    assert len(key) == 64
