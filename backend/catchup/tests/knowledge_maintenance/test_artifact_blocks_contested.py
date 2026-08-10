import uuid
from datetime import datetime
from datetime import timezone

import pytest

from catchup.knowledge_maintenance.domain.artifact import BLOCK_KIND_CLAIM_SECTION
from catchup.knowledge_maintenance.domain.artifact import BLOCK_KIND_CONTESTED
from catchup.knowledge_maintenance.domain.artifact import ArtifactBlock
from catchup.knowledge_maintenance.domain.artifact import ArtifactBlockError
from catchup.knowledge_maintenance.domain.artifact import BlockSource
from catchup.knowledge_maintenance.domain.artifact import ContestedVariant
from catchup.knowledge_maintenance.domain.artifact import block_content_hash
from catchup.knowledge_maintenance.domain.artifact import deserialize_blocks
from catchup.knowledge_maintenance.domain.artifact import serialize_blocks
from catchup.knowledge_maintenance.domain.artifact import validate_blocks

_NOW = datetime(2026, 8, 9, tzinfo=timezone.utc)


def _variant(claim_id: uuid.UUID, body: str) -> ContestedVariant:
    return ContestedVariant(
        claim_id=claim_id,
        body=body,
        sources=(
            BlockSource(
                claim_id=claim_id,
                statement=body,
                observed_at=_NOW,
                citation_verified=None,
            ),
        ),
    )


def _contested_block(claim_a: uuid.UUID, claim_b: uuid.UUID) -> ArtifactBlock:
    return ArtifactBlock(
        block_kind=BLOCK_KIND_CONTESTED,
        heading="배포 주기",
        body="상충하는 값 2개 — 검토 필요",
        claim_ids=(claim_a, claim_b),
        proposal_ids=(uuid.uuid4(),),
        ontology_version="v1",
        variants=tuple(
            sorted(
                (_variant(claim_a, "주 1회"), _variant(claim_b, "월 1회")),
                key=lambda v: str(v.claim_id),
            )
        ),
    )


def test_contested_block_serialize_roundtrip():
    claim_a, claim_b = uuid.uuid4(), uuid.uuid4()
    block = _contested_block(claim_a, claim_b)
    restored = deserialize_blocks(serialize_blocks([block]))
    assert restored == (block,)


def test_contested_requires_two_variants():
    claim_a, claim_b = uuid.uuid4(), uuid.uuid4()
    block = _contested_block(claim_a, claim_b)
    broken = ArtifactBlock(
        block_kind=block.block_kind,
        heading=block.heading,
        body=block.body,
        claim_ids=block.claim_ids,
        proposal_ids=block.proposal_ids,
        ontology_version=block.ontology_version,
        variants=block.variants[:1],
    )
    with pytest.raises(ArtifactBlockError):
        validate_blocks([broken])


def test_variant_claim_must_be_in_claim_ids():
    claim_a, claim_b = uuid.uuid4(), uuid.uuid4()
    block = _contested_block(claim_a, claim_b)
    alien = ArtifactBlock(
        block_kind=block.block_kind,
        heading=block.heading,
        body=block.body,
        claim_ids=(claim_a,),
        proposal_ids=block.proposal_ids,
        ontology_version=block.ontology_version,
        variants=block.variants,
    )
    with pytest.raises(ArtifactBlockError):
        validate_blocks([alien])


def test_block_content_hash_is_deterministic_and_content_sensitive():
    claim_a, claim_b = uuid.uuid4(), uuid.uuid4()
    block = _contested_block(claim_a, claim_b)
    assert block_content_hash(block) == block_content_hash(block)
    other = ArtifactBlock(
        block_kind=BLOCK_KIND_CLAIM_SECTION,
        heading="다른 제목",
        body="본문",
        claim_ids=(claim_a,),
        proposal_ids=(),
        ontology_version="v1",
    )
    assert block_content_hash(block) != block_content_hash(other)


def test_plain_block_serialization_has_no_variants_key():
    block = ArtifactBlock(
        block_kind=BLOCK_KIND_CLAIM_SECTION,
        heading="h",
        body="b",
        claim_ids=(uuid.uuid4(),),
        proposal_ids=(),
        ontology_version=None,
    )
    assert "variants" not in serialize_blocks([block])[0]
