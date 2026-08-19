"""읽기 레이아웃이 블록을 어떻게 재배열하는지 검사한다."""

import uuid
from datetime import datetime
from datetime import timezone

from catchup.knowledge_maintenance.domain.artifact import BLOCK_KIND_SUMMARY
from catchup.knowledge_maintenance.domain.artifact import ArtifactBlock
from catchup.knowledge_maintenance.domain.artifact import BlockSource
from catchup.knowledge_maintenance.domain.layout import ITEM_BLOCK
from catchup.knowledge_maintenance.domain.layout import ITEM_PLACEHOLDER
from catchup.knowledge_maintenance.domain.layout import ITEM_TABLE
from catchup.knowledge_maintenance.domain.layout import Layout
from catchup.knowledge_maintenance.domain.layout import TableGroup
from catchup.knowledge_maintenance.domain.layout import apply_layout


def _block(
    heading: str,
    kind: str = "claim_section",
    body: str = "b",
    narrative: str | None = None,
) -> ArtifactBlock:
    """검사에 쓸 블록 하나를 만든다."""
    cid = uuid.uuid4()
    return ArtifactBlock(
        block_kind=kind,
        heading=heading,
        body=body,
        claim_ids=(cid,),
        proposal_ids=(),
        ontology_version=None,
        sources=(BlockSource(cid, "s", datetime.now(timezone.utc), True),),
        narrative=narrative,
    )


LAYOUT = Layout(
    sections=(
        ("request_status", "요청 상태"),
        ("usage_context", "사용 상황"),
        ("frequency", "빈도"),
        ("workaround", "우회 방법"),
        ("requested_by(out)", "요청 고객사"),
    ),
    table_groups=(
        TableGroup(
            key="usage_table",
            title="사용 상황",
            section_keys=("usage_context", "frequency"),
        ),
    ),
    always_show=("workaround",),
)


def test_none_layout_keeps_original_order() -> None:
    """레이아웃이 없으면 블록 순서를 그대로 낸다."""
    blocks = [_block("b"), _block("a")]
    items = apply_layout(blocks, None)
    assert [(i.item_kind, i.block_index) for i in items] == [
        (ITEM_BLOCK, 0),
        (ITEM_BLOCK, 1),
    ]


def test_reorders_relabels_and_preserves_index() -> None:
    """순서와 제목을 바꾸되 원래 블록 위치는 그대로 둔다."""
    blocks = [
        _block("requested_by(out)", kind="relation_section"),
        _block("request_status"),
    ]
    items = apply_layout(blocks, LAYOUT)
    kept = [
        (i.heading, i.block_index) for i in items if i.item_kind == ITEM_BLOCK
    ]
    assert kept == [("요청 상태", 1), ("요청 고객사", 0)]


def test_table_group_merges_blocks_into_one_item() -> None:
    """표 묶음에 속한 블록들을 항목 하나로 합친다."""
    blocks = [
        _block("frequency", body="주 3회"),
        _block("usage_context", narrative="모바일에서 쓴다"),
    ]
    items = apply_layout(blocks, LAYOUT)
    table = next(i for i in items if i.item_kind == ITEM_TABLE)
    assert table.heading == "사용 상황"
    assert table.block_indexes == (1, 0)
    assert table.rows == (
        ("usage_context", "모바일에서 쓴다"),
        ("frequency", "주 3회"),
    )


def test_always_show_inserts_placeholder_without_index() -> None:
    """비어도 보여줄 칸은 블록 없이 자리표시로 채운다."""
    items = apply_layout([_block("request_status")], LAYOUT)
    ph = [i for i in items if i.item_kind == ITEM_PLACEHOLDER]
    assert [(i.heading, i.text, i.block_index) for i in ph] == [
        ("우회 방법", "없음", None)
    ]


def test_unknown_blocks_go_last_and_summary_first() -> None:
    """요약은 맨 앞에, 레이아웃에 없는 블록은 맨 뒤에 놓는다."""
    blocks = [
        _block("열린 질문: x", kind="open_question"),
        _block("요약", kind=BLOCK_KIND_SUMMARY),
        _block("request_status"),
    ]
    items = apply_layout(blocks, LAYOUT)
    order = [i.block_index for i in items if i.item_kind == ITEM_BLOCK]
    assert order == [1, 2, 0]
