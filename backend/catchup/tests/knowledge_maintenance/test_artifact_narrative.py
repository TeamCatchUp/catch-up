"""블록 산문이 저장·복원을 지나되 지문에는 끼지 않는지 확인한다.

산문이 지문에 끼면 문장만 다듬어도 문서 전체가 새 검토 사건으로 올라와
검수자가 진짜 변화를 못 찾는다. 그 제외가 이 슬라이스의 핵심 불변식이라
도메인 층에서 먼저 못박는다.
"""

from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import datetime
from datetime import timezone

from catchup.knowledge_maintenance.domain.artifact import BLOCK_KIND_CLAIM_SECTION
from catchup.knowledge_maintenance.domain.artifact import ArtifactBlock
from catchup.knowledge_maintenance.domain.artifact import BlockSource
from catchup.knowledge_maintenance.domain.artifact import block_content_hash
from catchup.knowledge_maintenance.domain.artifact import blocks_content_hash
from catchup.knowledge_maintenance.domain.artifact import deserialize_blocks
from catchup.knowledge_maintenance.domain.artifact import serialize_blocks

NOW = datetime(2026, 8, 15, 9, 0, tzinfo=timezone.utc)


def _block(narrative: str | None = None) -> ArtifactBlock:
    """근거 인용이 붙은 claim 절 블록 하나를 만든다."""
    claim_id = uuid.UUID("00000000-0000-4000-8000-000000000011")
    return ArtifactBlock(
        block_kind=BLOCK_KIND_CLAIM_SECTION,
        heading="status",
        body="검토 중 (2026-08-15 관찰)",
        claim_ids=(claim_id,),
        proposal_ids=(),
        ontology_version="v3",
        sources=(
            BlockSource(
                claim_id=claim_id,
                statement="상태는 검토 중이다",
                observed_at=NOW,
                citation_verified=True,
            ),
        ),
        narrative=narrative,
    )


def test_narrative_defaults_to_none() -> None:
    """산문 없이 만든 블록의 기본값은 없음이다."""
    assert _block().narrative is None


def test_narrative_survives_the_round_trip() -> None:
    """산문이 저장 형태를 왕복해도 그대로 돌아온다."""
    block = _block("이 요구는 아직 검토 중이다.")

    restored = deserialize_blocks(serialize_blocks([block]))

    assert restored == (block,)
    assert restored[0].narrative == "이 요구는 아직 검토 중이다."


def test_serialized_block_without_narrative_has_no_key() -> None:
    """산문이 없으면 저장 형태에 키를 적지 않는다."""
    item = serialize_blocks([_block()])[0]

    assert "narrative" not in item


def test_old_stored_block_reads_as_none() -> None:
    """산문 키가 없던 옛 저장 형태는 없음으로 읽힌다."""
    raw = serialize_blocks([_block()])

    assert deserialize_blocks(raw)[0].narrative is None


def test_block_hash_ignores_narrative() -> None:
    """산문만 다른 두 블록의 블록 지문이 같다."""
    plain = _block()
    narrated = replace(plain, narrative="이 요구는 아직 검토 중이다.")

    assert block_content_hash(plain) == block_content_hash(narrated)


def test_blocks_hash_ignores_narrative() -> None:
    """산문만 다른 두 본문의 문서 지문이 같다."""
    plain = [_block()]
    narrated = [replace(plain[0], narrative="다르게 쓴 문장이다.")]

    assert blocks_content_hash(plain) == blocks_content_hash(narrated)


def test_two_different_narratives_still_share_one_hash() -> None:
    """산문이 서로 다르게 바뀌어도 지문은 하나로 모인다."""
    first = _block("첫 번째로 쓴 문장이다.")
    second = _block("두 번째로 쓴 문장이다.")

    assert blocks_content_hash([first]) == blocks_content_hash([second])


def test_body_change_still_moves_the_hash() -> None:
    """본문이 바뀌면 지문은 그대로 움직인다."""
    before = _block("같은 문장이다.")
    after = replace(before, body="배포됨 (2026-08-16 관찰)")

    assert block_content_hash(before) != block_content_hash(after)
