"""블록 배열을 읽기 레이아웃 응답으로 옮긴다.

문서 읽기와 검수 상세가 같은 함수를 쓴다. 두 화면이 같은 문서를 서로 다른
순서나 다른 이름으로 보여 주면, 검토자가 승인한 화면과 발행 뒤 화면이
달라지기 때문이다.

레이아웃은 표현일 뿐이라 블록 배열과 그 순서를 바꾸지 않는다. 항목이 나르는
block_index도 원래 블록 배열에서의 자리 그대로다.
"""

from __future__ import annotations

from collections.abc import Sequence

from catchup.knowledge_maintenance.domain.artifact import ArtifactBlock
from catchup.knowledge_maintenance.domain.layout import apply_layout
from catchup.knowledge_maintenance.domain.preset_catalog import layout_for_kind
from catchup.server.wiki.schemas import LayoutItemResponse


def layout_items(
    blocks: Sequence[ArtifactBlock], *, kind: str | None
) -> list[LayoutItemResponse]:
    """블록 배열을 그 문서 종류의 읽기 레이아웃 항목으로 옮긴다.

    카탈로그에 없는 종류이거나 종류를 모르면 레이아웃이 없다. 그때는 블록을
    저장된 순서 그대로 낸다.

    Args:
        blocks: 문서에 저장된 블록 배열이다.
        kind: 문서 종류다. 모르면 None이다.

    Returns:
        표시 순서대로 정렬한 응답 항목들이다.
    """
    layout = None if kind is None else layout_for_kind(kind)
    return [
        LayoutItemResponse(
            item_kind=item.item_kind,
            heading=item.heading,
            block_index=item.block_index,
            text=item.text,
        )
        for item in apply_layout(blocks, layout)
    ]
