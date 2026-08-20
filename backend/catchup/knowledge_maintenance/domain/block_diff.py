"""발행판 블록과 제안 블록을 짝지어 무엇이 바뀌었는지 계산한다.

블록에는 고유 id가 없다. 블록은 컴파일 산출물이라 정체성이 내용에 있기
때문이다. 그래서 짝짓기 규칙이 필요하다. 규칙은 세 단계다.

1. block_kind와 heading이 같으면 같은 블록으로 본다.
2. 1의 후보가 여럿이면 claim_ids 교집합이 있는 것을 고른다.
3. 짝이 없으면 제안 쪽은 added, 발행판 쪽은 removed다.

짝이 맞은 블록은 body와 narrative가 모두 같을 때만 미변경이고, 미변경은
결과에 넣지 않는다. 이 규칙은 표시용 파생이며 stale 판정에는 쓰지 않는다.
stale 판정은 block_content_hash와 base_revision_id가 맡는다.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from catchup.knowledge_maintenance.domain.artifact import ArtifactBlock

# 블록 하나에 붙는 변경 종류다.
CHANGE_ADDED = "added"
CHANGE_MODIFIED = "modified"
CHANGE_REMOVED = "removed"


@dataclass(frozen=True, slots=True)
class BlockChange:
    """블록 하나의 변경을 표현한다.

    Attributes:
        change: 변경 종류를 나타낸다.
        block_index: 제안 blocks 안 위치를 가리킨다. removed면 없음이다.
        base_block_index: base_blocks 안 위치를 가리킨다. added면 없음이다.
    """

    change: str
    block_index: int | None
    base_block_index: int | None


def diff_blocks(
    base: Sequence[ArtifactBlock], proposed: Sequence[ArtifactBlock]
) -> tuple[BlockChange, ...]:
    """발행판 블록과 제안 블록을 짝지어 변경 목록을 만든다.

    Args:
        base: 발행판 블록들을 순서대로 받는다.
        proposed: 제안 블록들을 순서대로 받는다.

    Returns:
        변경된 블록만 담은 목록이다. 제안 순서대로 added·modified가 먼저
        오고, 짝을 찾지 못한 발행판 블록의 removed가 뒤에 온다.
    """
    remaining = list(range(len(base)))
    changes: list[BlockChange] = []
    for index, block in enumerate(proposed):
        candidates = [
            i
            for i in remaining
            if base[i].block_kind == block.block_kind
            and base[i].heading == block.heading
        ]
        if len(candidates) > 1:
            claim_set = set(block.claim_ids)
            narrowed = [i for i in candidates if claim_set & set(base[i].claim_ids)]
            # 제목이 같은 블록이 여럿인데 claim 교집합이 하나도 없으면
            # 어느 쪽이 짝인지 가릴 근거가 없다. 그럴 때는 앞에 있는
            # 블록과 짝짓는다.
            candidates = narrowed or candidates[:1]
        if not candidates:
            changes.append(BlockChange(CHANGE_ADDED, index, None))
            continue
        base_index = candidates[0]
        remaining.remove(base_index)
        paired = base[base_index]
        if paired.body != block.body or paired.narrative != block.narrative:
            changes.append(BlockChange(CHANGE_MODIFIED, index, base_index))
    for base_index in remaining:
        changes.append(BlockChange(CHANGE_REMOVED, None, base_index))
    return tuple(changes)


def change_reason(
    change: BlockChange,
    *,
    base: Sequence[ArtifactBlock],
    proposed: Sequence[ArtifactBlock],
) -> str | None:
    """변경 하나를 검토자가 읽을 짧은 사유 문구로 옮긴다.

    내용이 바뀐 블록은 거기 적혀 있는 수정 이유를 먼저 쓴다. 컴파일이
    앞뒤 내용을 보고 받아 둔 문장이라 여기서 세는 근거 개수보다 사람에게
    훨씬 많은 것을 알려 준다. 그 문장이 없는 블록만 개수를 세어 문구를
    만든다. 새로 생긴 블록과 빠진 블록은 짝이 없어 수정 이유를 받지
    않으므로 예전 문구를 그대로 쓴다.

    Args:
        change: 사유를 붙일 변경이다.
        base: 발행판 블록들이다.
        proposed: 제안 블록들이다.

    Returns:
        사유 문구다. removed는 붙일 사유가 없어서 None이다.
    """
    if change.change == CHANGE_ADDED:
        return "새 섹션"
    if change.change == CHANGE_REMOVED:
        return None
    stored = proposed[change.block_index].change_reason
    if stored is not None:
        return stored
    before = set(base[change.base_block_index].claim_ids)
    after = set(proposed[change.block_index].claim_ids)
    added, dropped = len(after - before), len(before - after)
    if added == 0 and dropped == 0:
        return "산문 갱신"
    return f"근거 {added}건 추가·{dropped}건 폐기"


def block_markdown(block: ArtifactBlock) -> str:
    """블록 하나를 markdown 조각으로 옮긴다.

    산문이 있으면 산문을 쓴다. 산문은 사람이 읽으라고 쓴 표현이고 body는
    근거를 나열한 원본이라, 화면에는 산문이 더 알맞기 때문이다.

    Args:
        block: 옮길 블록이다.

    Returns:
        제목 한 줄과 본문으로 이루어진 markdown 조각이다.
    """
    text = block.narrative if block.narrative else block.body
    return f"## {block.heading}\n\n{text}"
