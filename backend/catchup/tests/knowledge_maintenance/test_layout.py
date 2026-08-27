"""읽기 레이아웃이 블록을 어떻게 재배열하는지 검사한다."""

import uuid
from datetime import datetime
from datetime import timezone

from catchup.knowledge_maintenance.domain.artifact import BLOCK_KIND_SUMMARY
from catchup.knowledge_maintenance.domain.artifact import ArtifactBlock
from catchup.knowledge_maintenance.domain.artifact import BlockSource
from catchup.knowledge_maintenance.domain.layout import ITEM_BLOCK
from catchup.knowledge_maintenance.domain.layout import ITEM_PLACEHOLDER
from catchup.knowledge_maintenance.domain.layout import Layout
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


def test_each_section_becomes_its_own_block_item() -> None:
    """칸마다 블록 항목을 따로 내고 sections 순서를 따른다."""
    blocks = [
        _block("frequency", body="주 3회"),
        _block("usage_context", narrative="모바일에서 쓴다"),
    ]
    items = apply_layout(blocks, LAYOUT)
    assert [(i.item_kind, i.heading, i.block_index) for i in items] == [
        (ITEM_BLOCK, "사용 상황", 1),
        (ITEM_BLOCK, "빈도", 0),
        (ITEM_PLACEHOLDER, "우회 방법", None),
    ]


def test_no_item_is_a_table() -> None:
    """어떤 항목도 표 종류로 나오지 않는다."""
    blocks = [
        _block("frequency"),
        _block("usage_context"),
        _block("request_status"),
    ]
    items = apply_layout(blocks, LAYOUT)
    assert {i.item_kind for i in items} <= {ITEM_BLOCK, ITEM_PLACEHOLDER}


def test_always_show_inserts_placeholder_without_index() -> None:
    """비어도 보여줄 칸은 블록 없이 자리표시로 채운다."""
    items = apply_layout([_block("request_status")], LAYOUT)
    ph = [i for i in items if i.item_kind == ITEM_PLACEHOLDER]
    assert [(i.heading, i.text, i.block_index) for i in ph] == [
        ("우회 방법", "없음", None)
    ]


def test_unknown_blocks_go_last_and_summary_first() -> None:
    """머리말은 맨 앞에, 레이아웃에 없는 블록은 맨 뒤에 놓는다."""
    blocks = [
        _block("열린 질문: x", kind="open_question"),
        _block("요약", kind=BLOCK_KIND_SUMMARY),
        _block("request_status"),
    ]
    items = apply_layout(blocks, LAYOUT)
    order = [i.block_index for i in items if i.item_kind == ITEM_BLOCK]
    assert order == [1, 2, 0]


def test_summary_sections_are_labeled_and_come_first() -> None:
    """머리말 세 블록이 양식 제목을 달고 저장 순서대로 맨 앞에 선다."""
    blocks = [
        _block("request_status"),
        _block("one_line_summary", kind=BLOCK_KIND_SUMMARY),
        _block("desired_outcome", kind=BLOCK_KIND_SUMMARY),
        _block("background", kind=BLOCK_KIND_SUMMARY),
    ]

    items = apply_layout(blocks, LAYOUT)

    assert [(i.heading, i.block_index) for i in items[:3]] == [
        ("한 줄 요약", 1),
        ("원하는 결과", 2),
        ("요청 배경", 3),
    ]


def test_old_single_summary_keeps_its_heading() -> None:
    """표에 없는 heading의 머리말은 저장된 제목 그대로 첫 항목이 된다.

    머리말이 세 섹션으로 갈리기 전에 발행된 판이 그렇다. 그 판의 heading은
    문서 제목이라 바꿔 붙일 이름이 없다.
    """
    blocks = [
        _block("request_status"),
        _block("요청 현황: 엑셀 내려받기", kind=BLOCK_KIND_SUMMARY),
    ]

    items = apply_layout(blocks, LAYOUT)

    assert (items[0].heading, items[0].block_index) == (
        "요청 현황: 엑셀 내려받기",
        1,
    )
