"""relation_section 블록과 relation_ids 장부 계약을 확인한다.

핵심 제약: 기존 블록(claim_section 등)의 직렬화 결과가 이 확장으로
변하면 안 된다 — 변하면 전 문서의 content hash가 바뀌어 검수 큐에
헛물결이 인다. 빈 relation_ids는 직렬화에서 키를 생략한다.
"""

import uuid

import pytest

from catchup.knowledge_maintenance.domain.artifact import BLOCK_KIND_CLAIM_SECTION
from catchup.knowledge_maintenance.domain.artifact import BLOCK_KIND_RELATION_SECTION
from catchup.knowledge_maintenance.domain.artifact import ArtifactBlock
from catchup.knowledge_maintenance.domain.artifact import ArtifactBlockError
from catchup.knowledge_maintenance.domain.artifact import blocks_content_hash
from catchup.knowledge_maintenance.domain.artifact import deserialize_blocks
from catchup.knowledge_maintenance.domain.artifact import serialize_blocks
from catchup.knowledge_maintenance.domain.artifact import validate_blocks


def _claim_block() -> ArtifactBlock:
    return ArtifactBlock(
        block_kind=BLOCK_KIND_CLAIM_SECTION,
        heading="상태",
        body="검토 중이다.",
        claim_ids=(uuid.uuid4(),),
        proposal_ids=(),
        ontology_version="v1",
    )


def test_relation_section_requires_relation_ids():
    block = ArtifactBlock(
        block_kind=BLOCK_KIND_RELATION_SECTION,
        heading="요청 고객",
        body="A사가 요청했다.",
        claim_ids=(),
        proposal_ids=(),
        ontology_version="v1",
    )
    with pytest.raises(ArtifactBlockError):
        validate_blocks([block])


def test_relation_section_rejects_claim_ids():
    block = ArtifactBlock(
        block_kind=BLOCK_KIND_RELATION_SECTION,
        heading="요청 고객",
        body="A사가 요청했다.",
        claim_ids=(uuid.uuid4(),),
        proposal_ids=(),
        ontology_version="v1",
        relation_ids=(uuid.uuid4(),),
    )
    with pytest.raises(ArtifactBlockError):
        validate_blocks([block])


def test_non_relation_block_rejects_relation_ids():
    block = ArtifactBlock(
        block_kind=BLOCK_KIND_CLAIM_SECTION,
        heading="상태",
        body="검토 중이다.",
        claim_ids=(uuid.uuid4(),),
        proposal_ids=(),
        ontology_version="v1",
        relation_ids=(uuid.uuid4(),),
    )
    with pytest.raises(ArtifactBlockError):
        validate_blocks([block])


def test_relation_section_round_trip():
    relation_id = uuid.uuid4()
    block = ArtifactBlock(
        block_kind=BLOCK_KIND_RELATION_SECTION,
        heading="요청 고객",
        body="A사가 요청했다.",
        claim_ids=(),
        proposal_ids=(),
        ontology_version="v1",
        relation_ids=(relation_id,),
    )
    validate_blocks([block])
    restored = deserialize_blocks(serialize_blocks([block]))
    assert restored[0].relation_ids == (relation_id,)


def test_existing_block_serialization_unchanged():
    # 빈 relation_ids는 키를 생략한다 — 기존 문서 hash 보존.
    payload = serialize_blocks([_claim_block()])
    assert "relation_ids" not in payload[0]


def test_legacy_payload_without_relation_ids_parses():
    payload = serialize_blocks([_claim_block()])
    restored = deserialize_blocks(payload)
    assert restored[0].relation_ids == ()


def test_hash_stable_for_blocks_without_relations():
    # relation_ids 기본값이 hash 입력에 흔적을 남기지 않는다. 옛 저장
    # 형태(키 없음)에서 되살린 블록과 지문이 같아야 한다.
    block = _claim_block()
    legacy_payload = [
        {
            key: value
            for key, value in serialize_blocks([block])[0].items()
            if key != "relation_ids"
        }
    ]
    restored = deserialize_blocks(legacy_payload)
    assert blocks_content_hash([block]) == blocks_content_hash(restored)
    assert "relation_ids" not in serialize_blocks(restored)[0]
