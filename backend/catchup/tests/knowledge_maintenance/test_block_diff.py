"""발행판 블록과 제안 블록의 짝짓기·변경 사유·markdown 계산을 확인한다.

블록에는 고유 id가 없어서 짝짓기 규칙이 곧 변경 표시의 정확도다. 규칙이
틀리면 그냥 순서만 바뀐 문서가 전면 교체로 보이므로 도메인 층에서 먼저
못박는다.
"""

from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import datetime
from datetime import timezone

from catchup.knowledge_maintenance.domain.artifact import ArtifactBlock
from catchup.knowledge_maintenance.domain.artifact import BlockSource
from catchup.knowledge_maintenance.domain.block_diff import BlockChange
from catchup.knowledge_maintenance.domain.block_diff import block_markdown
from catchup.knowledge_maintenance.domain.block_diff import change_reason
from catchup.knowledge_maintenance.domain.block_diff import diff_blocks


def _block(
    kind="claim_section",
    heading="상태",
    body="b",
    narrative=None,
    claim_ids=(),
):
    return ArtifactBlock(
        block_kind=kind,
        heading=heading,
        body=body,
        claim_ids=tuple(claim_ids),
        proposal_ids=(),
        ontology_version=None,
        narrative=narrative,
    )


def _source(claim_id, statement):
    return BlockSource(
        claim_id=claim_id,
        statement=statement,
        observed_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
        citation_verified=True,
    )


def test_same_kind_and_heading_pairs_and_unchanged_is_omitted():
    a = _block(body="x")
    assert diff_blocks([a], [a]) == ()


def test_modified_when_body_or_narrative_differs():
    base = [_block(body="x")]
    prop = [_block(body="y")]
    assert diff_blocks(base, prop) == (BlockChange("modified", 0, 0),)
    prop2 = [_block(body="x", narrative="새 산문")]
    assert diff_blocks(base, prop2) == (BlockChange("modified", 0, 0),)


def test_modified_when_only_claim_ids_differ():
    """본문과 산문이 같아도 근거가 갈리면 변경으로 잡는다.

    발행은 변경으로 잡히지 않은 블록의 사람 결정을 면제한다. 근거 교체가
    미변경으로 새면 사람이 보지 않은 근거가 판에 실리고 그 claim이 확정까지
    간다.
    """
    c1, c2 = uuid.uuid4(), uuid.uuid4()
    base = [_block(body="x", claim_ids=[c1])]
    prop = [_block(body="x", claim_ids=[c2])]
    assert diff_blocks(base, prop) == (BlockChange("modified", 0, 0),)


def test_modified_when_only_sources_differ():
    """claim 목록이 같아도 인용 근거가 갈리면 변경으로 잡는다."""
    claim_id = uuid.uuid4()
    base = [
        replace(
            _block(body="x", claim_ids=[claim_id]),
            sources=(_source(claim_id, "옛 인용"),),
        )
    ]
    prop = [
        replace(
            _block(body="x", claim_ids=[claim_id]),
            sources=(_source(claim_id, "새 인용"),),
        )
    ]
    assert diff_blocks(base, prop) == (BlockChange("modified", 0, 0),)


def test_change_reason_tells_evidence_swap_when_text_is_intact():
    """본문·산문이 그대로면서 근거만 갈린 블록은 근거 교체를 말한다."""
    claim_id = uuid.uuid4()
    base = [
        replace(
            _block(body="x", claim_ids=[claim_id]),
            sources=(_source(claim_id, "옛 인용"),),
        )
    ]
    prop = [
        replace(
            _block(body="x", claim_ids=[claim_id]),
            sources=(_source(claim_id, "새 인용"),),
        )
    ]
    change = diff_blocks(base, prop)[0]
    assert (
        change_reason(change, base=base, proposed=prop)
        == "본문은 그대로이고 근거가 갈렸습니다."
    )


def test_added_and_removed():
    base = [_block(heading="A")]
    prop = [_block(heading="B")]
    assert diff_blocks(base, prop) == (
        BlockChange("added", 0, None),
        BlockChange("removed", None, 0),
    )


def test_ambiguous_heading_resolved_by_claim_ids_intersection():
    c1, c2 = uuid.uuid4(), uuid.uuid4()
    base = [
        _block(heading="H", body="1", claim_ids=[c1]),
        _block(heading="H", body="2", claim_ids=[c2]),
    ]
    prop = [
        _block(heading="H", body="2x", claim_ids=[c2]),
        _block(heading="H", body="1", claim_ids=[c1]),
    ]
    assert diff_blocks(base, prop) == (BlockChange("modified", 0, 1),)


def test_relation_block_with_empty_claim_ids_pairs_by_heading():
    base = [
        _block(
            kind="relation_section",
            heading="요청자",
            body="A → requested_by → B",
        )
    ]
    prop = [
        _block(
            kind="relation_section",
            heading="요청자",
            body="A → requested_by → C",
        )
    ]
    assert diff_blocks(base, prop) == (BlockChange("modified", 0, 0),)


def test_change_reason_counts_claim_diff():
    c1, c2, c3 = (uuid.uuid4() for _ in range(3))
    base = [_block(claim_ids=[c1, c2])]
    prop = [_block(body="n", claim_ids=[c2, c3])]
    change = diff_blocks(base, prop)[0]
    assert (
        change_reason(change, base=base, proposed=prop)
        == "근거 1건이 추가되고 1건이 빠졌습니다."
    )
    assert (
        change_reason(BlockChange("added", 0, None), base=[], proposed=prop)
        == "새로 추가된 섹션입니다."
    )
    assert (
        change_reason(BlockChange("removed", None, 0), base=base, proposed=[]) is None
    )
    same = [_block(body="n", claim_ids=[c1, c2])]
    assert (
        change_reason(diff_blocks(base, same)[0], base=base, proposed=same)
        == "산문 표현만 다듬었습니다."
    )


def test_change_reason_counts_only_dropped_claims():
    """근거가 빠지기만 했으면 빠진 건수만 말한다."""
    c1, c2 = uuid.uuid4(), uuid.uuid4()
    base = [_block(claim_ids=[c1, c2])]
    prop = [_block(body="n", claim_ids=[c1])]
    change = diff_blocks(base, prop)[0]
    assert (
        change_reason(change, base=base, proposed=prop) == "근거 1건이 빠졌습니다."
    )


def test_block_markdown_prefers_narrative():
    assert (
        block_markdown(_block(heading="상태", body="b", narrative="산문"))
        == "## 상태\n\n산문"
    )
    assert block_markdown(_block(heading="상태", body="b")) == "## 상태\n\nb"


def test_change_reason_prefers_stored_value():
    """블록에 저장된 수정 이유가 있으면 그 문장을 먼저 돌려준다."""
    c1, c2 = uuid.uuid4(), uuid.uuid4()
    base = [_block(body="x", claim_ids=(c1,))]
    prop = [
        replace(
            _block(body="y", claim_ids=(c1, c2)),
            change_reason="새 회의록이 붙어 값이 갱신됐다.",
        )
    ]
    change = diff_blocks(base, prop)[0]
    assert (
        change_reason(change, base=base, proposed=prop)
        == "새 회의록이 붙어 값이 갱신됐다."
    )


def test_change_reason_falls_back_when_stored_missing():
    """저장된 수정 이유가 없으면 기존 결정론 문구로 돌아간다."""
    c1, c2 = uuid.uuid4(), uuid.uuid4()
    base = [_block(body="x", claim_ids=(c1,))]
    prop = [_block(body="y", claim_ids=(c1, c2))]
    change = diff_blocks(base, prop)[0]
    assert (
        change_reason(change, base=base, proposed=prop)
        == "근거 1건이 추가되었습니다."
    )
