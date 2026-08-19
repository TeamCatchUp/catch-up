"""위키 문서를 읽을 때 쓸 레이아웃을 담는다.

레이아웃은 읽기 표현일 뿐이다. 저장된 블록 배열과 그 순서, 블록의 내용
지문(content hash), 검수 판정(verdict)은 이 모듈이 건드리지 않는다. 같은
블록 배열을 기획 양식의 순서와 이름으로 바꿔 보여 주기만 한다.

자리표시(placeholder)는 블록이 아니다. 값이 아직 없다는 사실을 읽는
사람에게 알리려고 화면에만 끼워 넣는 항목이라, 가리킬 블록도 근거도
없다. 그래서 block_index가 None이다.

block_index는 언제나 원래 블록 배열에서의 위치다. 검수 판정과 블록 변경
기록이 그 위치로 블록을 가리키므로, 표시 순서에 맞춰 번호를 다시 매기면
검수자가 고른 블록과 저장된 블록이 어긋난다.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from catchup.knowledge_maintenance.domain.artifact import BLOCK_KIND_SUMMARY
from catchup.knowledge_maintenance.domain.artifact import ArtifactBlock

# 레이아웃이 내놓는 항목의 종류다.
ITEM_BLOCK = "block"
ITEM_TABLE = "table"
ITEM_PLACEHOLDER = "placeholder"


@dataclass(frozen=True, slots=True)
class TableGroup:
    """여러 블록을 표 하나로 합쳐 보여 줄 묶음을 표현한다.

    Attributes:
        key: 표 묶음의 식별자다. 비어 있을 때 자리표시를 낼지 정하는
            always_show도 이 값으로 가리킨다.
        title: 표 항목의 제목으로 쓴다.
        section_keys: 표로 합칠 블록들의 heading을 순서대로 담는다.
    """

    key: str
    title: str
    section_keys: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Layout:
    """문서 한 종류를 어떤 순서와 이름으로 읽힐지 정한다.

    Attributes:
        sections: (section_key, 표시 제목)을 보여 줄 순서대로 담는다.
            section_key는 블록의 heading과 글자 그대로 같다.
        table_groups: 표 하나로 합칠 블록 묶음들을 담는다.
        always_show: 해당하는 블록이 없어도 자리표시로 보여 줄
            section_key와 표 묶음 key를 담는다.
        empty_text: 자리표시에 넣을 문구다.
    """

    sections: tuple[tuple[str, str], ...]
    table_groups: tuple[TableGroup, ...] = ()
    always_show: tuple[str, ...] = ()
    empty_text: str = "없음"


@dataclass(frozen=True, slots=True)
class LayoutItem:
    """레이아웃이 내놓는 표시 항목 하나를 표현한다.

    Attributes:
        item_kind: 항목의 종류다. block·table·placeholder 중 하나다.
        heading: 화면에 보여 줄 제목이다.
        block_index: block 항목이 가리키는 원래 블록의 위치다. 표와
            자리표시는 None이다.
        block_indexes: table 항목이 합친 블록들의 원래 위치를 담는다.
        rows: table 항목의 행을 (열 제목, 값)으로 담는다. 열 제목은 합친
            블록의 heading이고, 값은 산문이 있으면 산문, 없으면 본문이다.
        text: placeholder 항목에 넣을 문구다.
    """

    item_kind: str
    heading: str
    block_index: int | None = None
    block_indexes: tuple[int, ...] = ()
    rows: tuple[tuple[str, str], ...] = ()
    text: str | None = None


def apply_layout(
    blocks: Sequence[ArtifactBlock], layout: Layout | None
) -> tuple[LayoutItem, ...]:
    """블록 배열을 레이아웃 순서의 표시 항목으로 바꾼다.

    레이아웃이 없으면 블록을 원래 순서 그대로 낸다. 레이아웃이 있으면
    요약 블록을 맨 앞에 놓고, sections 순서대로 항목을 만들고, 레이아웃이
    이름을 대지 않은 블록을 원래 순서로 맨 뒤에 붙인다. 어느 경우에도
    블록 자체는 바뀌지 않는다.

    Args:
        blocks: 문서에 저장된 블록 배열이다.
        layout: 적용할 레이아웃이다. 없으면 None이다.

    Returns:
        표시 순서대로 정렬한 항목들이다.
    """
    if layout is None:
        return tuple(
            LayoutItem(ITEM_BLOCK, block.heading, block_index=index)
            for index, block in enumerate(blocks)
        )

    items: list[LayoutItem] = []
    for index, block in enumerate(blocks):
        if block.block_kind == BLOCK_KIND_SUMMARY:
            items.append(
                LayoutItem(ITEM_BLOCK, block.heading, block_index=index)
            )

    indexes_by_heading: dict[str, list[int]] = {}
    for index, block in enumerate(blocks):
        if block.block_kind == BLOCK_KIND_SUMMARY:
            continue
        indexes_by_heading.setdefault(block.heading, []).append(index)

    group_by_key = {
        section_key: group
        for group in layout.table_groups
        for section_key in group.section_keys
    }

    placed: set[int] = set()
    done_groups: set[str] = set()
    for section_key, title in layout.sections:
        group = group_by_key.get(section_key)
        if group is not None:
            if group.key in done_groups:
                continue
            done_groups.add(group.key)
            item = _table_item(blocks, indexes_by_heading, group, layout)
            if item is not None:
                items.append(item)
                placed.update(item.block_indexes)
            continue
        indexes = indexes_by_heading.get(section_key, [])
        if indexes:
            for index in indexes:
                items.append(LayoutItem(ITEM_BLOCK, title, block_index=index))
                placed.add(index)
        elif section_key in layout.always_show:
            items.append(
                LayoutItem(ITEM_PLACEHOLDER, title, text=layout.empty_text)
            )

    for index, block in enumerate(blocks):
        if block.block_kind == BLOCK_KIND_SUMMARY or index in placed:
            continue
        items.append(LayoutItem(ITEM_BLOCK, block.heading, block_index=index))
    return tuple(items)


def _table_item(
    blocks: Sequence[ArtifactBlock],
    indexes_by_heading: dict[str, list[int]],
    group: TableGroup,
    layout: Layout,
) -> LayoutItem | None:
    """표 묶음 하나를 표 항목이나 자리표시로 만든다.

    묶음에 속한 블록이 하나도 없으면 always_show일 때만 자리표시를 내고,
    아니면 아무 항목도 내지 않는다.

    Args:
        blocks: 문서에 저장된 블록 배열이다.
        indexes_by_heading: heading별 블록 위치 목록이다.
        group: 만들 표 묶음이다.
        layout: 적용 중인 레이아웃이다.

    Returns:
        표 항목이나 자리표시 항목이다. 낼 항목이 없으면 None이다.
    """
    indexes: list[int] = []
    rows: list[tuple[str, str]] = []
    for section_key in group.section_keys:
        for index in indexes_by_heading.get(section_key, []):
            block = blocks[index]
            indexes.append(index)
            rows.append((block.heading, block.narrative or block.body))
    if indexes:
        return LayoutItem(
            ITEM_TABLE,
            group.title,
            block_indexes=tuple(indexes),
            rows=tuple(rows),
        )
    if group.key in layout.always_show:
        return LayoutItem(
            ITEM_PLACEHOLDER, group.title, text=layout.empty_text
        )
    return None
