"""이름 유사도로 판정 블록을 만드는 규칙을 정의한다.

해소의 후보군 형성이 정규화 이름 완전 일치뿐이면 "Google Workspace
연동"과 "Google Workspace 커넥터"는 서로를 만나지 못하고 각자 노드가
된다. 그래서 완전 일치 경로 위에 이름 임베딩 유사도를 얹어, 같은 대상일
수 있는 이름들을 한 블록으로 모아 판정대에 올린다.

이 모듈은 순수하다. 임베딩 호출도, 저장소 접근도 하지 않고 이미 만들어진
벡터만 받는다. 판정은 하지 않는다. 여기서 정하는 것은 "누구를 함께
물어볼 것인가"뿐이고, "같은 대상인가"는 identity judge가 답한다.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from catchup.knowledge_maintenance.domain.entity_resolution import normalize_name

# 재현율을 우선한 값이다. 놓친 짝은 각자 노드로 굳어 다시는 만나지
# 못하지만, 과하게 묶인 블록은 judge가 여러 그룹으로 갈라 준다. 그래서
# 경계에서는 묶는 쪽으로 기운다. 임계값을 낮출수록 블록이 커져 판정
# 비용과 프롬프트 길이가 늘어나므로, 실측 결과에 따라 조정한다.
NAME_SIMILARITY_THRESHOLD = 0.80

# 블록 하나에 담는 멤버 수의 상한이다. 상한이 없으면 임계값을 넉넉히 잡은
# 대가가 한 블록의 폭주로 나타나, 프롬프트가 길어지고 판정 품질이 함께
# 떨어진다.
MAX_BLOCK_SIZE = 8


class BlockingOrigin(StrEnum):
    """블록 멤버가 어디서 왔는지 표현한다.

    후보끼리 묶인 그룹과 후보·기존 노드가 섞인 그룹은 뒤따르는 처리가
    다르다. 앞은 후보 병합, 뒤는 기존 노드로의 병합 제안이다.
    """

    CANDIDATE = "candidate"
    NODE = "node"


@dataclass(frozen=True, slots=True)
class BlockingMember:
    """블록에 올릴 이름 한 건을 표현한다.

    Attributes:
        member_id: 멤버를 가리키는 안정 식별자를 담는다. 후보 행이나 기존
            노드의 id를 문자열로 담는다.
        entity_type: entity 종류를 나타낸다. 종류가 다르면 비교하지 않는다.
        name: 비교 대상이 되는 표시 이름을 담는다.
        origin: 후보인지 기존 노드인지 나타낸다.
        excerpt: 판정 프롬프트에 실을 원문 맥락을 담는다. 없을 수 있고,
            블록 형성에는 쓰지 않는다.
    """

    member_id: str
    entity_type: str
    name: str
    origin: BlockingOrigin
    excerpt: str | None = None

    def __post_init__(self) -> None:
        if not self.member_id.strip():
            raise ValueError("member_id must not be blank")
        if not self.entity_type.strip():
            raise ValueError("entity_type must not be blank")
        if not self.name.strip():
            raise ValueError("name must not be blank")

    @property
    def normalized_name(self) -> str:
        """비교에 쓸 정규화 이름을 돌려준다."""
        return normalize_name(self.name)


@dataclass(frozen=True, slots=True)
class EntityBlock:
    """한 번의 판정에 함께 올릴 멤버들을 표현한다."""

    entity_type: str
    members: tuple[BlockingMember, ...]

    def __post_init__(self) -> None:
        if not self.members:
            raise ValueError("block must have at least one member")
        if any(member.entity_type != self.entity_type for member in self.members):
            raise ValueError("block members must share one entity_type")

    @property
    def member_ids(self) -> tuple[str, ...]:
        """멤버 식별자들을 순서대로 돌려준다."""
        return tuple(member.member_id for member in self.members)


def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    """두 벡터의 cosine 유사도를 돌려준다.

    길이가 다르거나 어느 한쪽의 크기가 0이면 0을 돌려준다. 잴 수 없는
    값을 예외로 올리면 벡터 한 건의 이상이 라운드 전체를 멈추는데,
    유사도 0은 "묶지 않는다"로 안전하게 읽힌다.
    """
    if len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return dot / (left_norm * right_norm)


def build_entity_blocks(
    members: Sequence[BlockingMember],
    vectors: Sequence[Sequence[float]],
    *,
    threshold: float = NAME_SIMILARITY_THRESHOLD,
    max_block_size: int = MAX_BLOCK_SIZE,
) -> tuple[EntityBlock, ...]:
    """멤버들을 판정 블록으로 나눈다.

    규칙은 셋이다. 첫째, entity_type이 같은 멤버끼리만 비교한다. 둘째,
    정규화 이름이 같거나 벡터 유사도가 임계값 이상이면 이어져 있다고
    보고, 이어진 것들을 연결 요소로 묶는다. 셋째, 한 요소가 상한을 넘으면
    선두 멤버와 그에 가장 가까운 멤버들로 블록을 채우고, 남은 멤버들은
    같은 방식으로 다시 블록을 만든다.

    정규화 이름 일치를 벡터와 무관하게 이어 두는 이유는 지금의 완전 일치
    경로를 유사도가 덮어쓰지 않게 하기 위해서다. 이미 같은 이름으로 묶이던
    후보들은 벡터가 어떻든 계속 같은 블록에 있어야 한다.

    모든 멤버는 정확히 한 블록에 들어간다. 홀로 남은 멤버도 크기 1의
    블록으로 나온다. 부르는 쪽이 멤버를 잃지 않도록 배정 자체를 전수로
    두고, 크기 1인 블록을 어떻게 다룰지는 부르는 쪽이 정한다.

    결과는 입력 순서에 좌우되지 않는다. 비교와 정렬을 모두 (정규화 이름,
    member_id) 기준으로 하므로 같은 입력 집합이면 같은 블록이 같은 순서로
    나온다.

    Args:
        members: 블록으로 나눌 멤버들을 받는다.
        vectors: 멤버와 같은 순서의 이름 벡터들을 받는다.
        threshold: 이 값 이상이면 이어져 있다고 본다.
        max_block_size: 블록 하나에 담을 멤버 수의 상한을 받는다.

    Returns:
        블록들을 (entity_type, 선두 멤버) 순으로 돌려준다.

    Raises:
        ValueError: 벡터 수가 멤버 수와 다르거나 상한이 1보다 작을 때
            던진다.
    """
    if len(members) != len(vectors):
        raise ValueError("vector count must match member count")
    if max_block_size < 1:
        raise ValueError("max_block_size must be at least one")
    if not members:
        return ()

    vector_by_id = {
        member.member_id: tuple(vector)
        for member, vector in zip(members, vectors, strict=True)
    }

    by_type: dict[str, list[BlockingMember]] = {}
    for member in members:
        by_type.setdefault(member.entity_type, []).append(member)

    blocks: list[EntityBlock] = []
    for entity_type in sorted(by_type):
        ordered = sorted(by_type[entity_type], key=_sort_key)
        for component in _connected_components(
            ordered, vector_by_id, threshold=threshold
        ):
            blocks.extend(
                EntityBlock(entity_type=entity_type, members=tuple(chunk))
                for chunk in _cap(
                    component, vector_by_id, max_block_size=max_block_size
                )
            )

    blocks.sort(key=lambda block: (block.entity_type, _sort_key(block.members[0])))
    return tuple(blocks)


def _sort_key(member: BlockingMember) -> tuple[str, str]:
    """멤버의 정렬 기준을 만든다. 입력 순서를 결과에서 지운다."""
    return (member.normalized_name, member.member_id)


def _linked(
    left: BlockingMember,
    right: BlockingMember,
    vector_by_id: dict[str, tuple[float, ...]],
    *,
    threshold: float,
) -> bool:
    """두 멤버가 같은 블록에 올라도 되는지 본다."""
    if left.normalized_name == right.normalized_name:
        return True
    similarity = cosine_similarity(
        vector_by_id[left.member_id], vector_by_id[right.member_id]
    )
    return similarity >= threshold


def _connected_components(
    ordered: list[BlockingMember],
    vector_by_id: dict[str, tuple[float, ...]],
    *,
    threshold: float,
) -> list[list[BlockingMember]]:
    """이어진 멤버들을 연결 요소로 묶는다.

    A와 C가 안 닮아도 B가 둘 다와 닮았으면 셋을 한 판정대에 올린다.
    쌍 단위로 끊어 물으면 비이행 판정을 조정할 자리가 없기 때문이다.
    """
    parent = {member.member_id: member.member_id for member in ordered}

    def find(member_id: str) -> str:
        while parent[member_id] != member_id:
            parent[member_id] = parent[parent[member_id]]
            member_id = parent[member_id]
        return member_id

    for index, left in enumerate(ordered):
        for right in ordered[index + 1 :]:
            if not _linked(left, right, vector_by_id, threshold=threshold):
                continue
            left_root = find(left.member_id)
            right_root = find(right.member_id)
            if left_root != right_root:
                parent[right_root] = left_root

    grouped: dict[str, list[BlockingMember]] = {}
    for member in ordered:
        grouped.setdefault(find(member.member_id), []).append(member)
    roots = sorted(grouped, key=lambda root: _sort_key(grouped[root][0]))
    return [grouped[root] for root in roots]


def _cap(
    component: list[BlockingMember],
    vector_by_id: dict[str, tuple[float, ...]],
    *,
    max_block_size: int,
) -> list[list[BlockingMember]]:
    """상한을 넘는 연결 요소를 여러 블록으로 나눈다.

    선두 멤버를 기준으로 가까운 순서대로 상한까지 채운다. 정규화 이름이
    같은 멤버는 벡터와 무관하게 가장 가깝게 친다. 상한을 못 넘긴 나머지는
    버리지 않고 같은 방식으로 다시 채워, 멤버가 하나도 빠지지 않게 한다.
    """
    if len(component) <= max_block_size:
        return [component]

    remaining = list(component)
    chunks: list[list[BlockingMember]] = []
    while remaining:
        anchor = remaining[0]
        others = remaining[1:]
        if len(others) + 1 <= max_block_size:
            chunks.append(remaining)
            break
        ranked = sorted(
            others,
            key=lambda member: (
                -_closeness(anchor, member, vector_by_id),
                _sort_key(member),
            ),
        )
        picked = ranked[: max_block_size - 1]
        chunk = sorted([anchor, *picked], key=_sort_key)
        chunks.append(chunk)
        chosen = {member.member_id for member in chunk}
        remaining = [
            member for member in remaining if member.member_id not in chosen
        ]
    return chunks


def _closeness(
    anchor: BlockingMember,
    member: BlockingMember,
    vector_by_id: dict[str, tuple[float, ...]],
) -> float:
    """선두 멤버에 얼마나 가까운지 잰다. 이름 일치가 가장 가깝다."""
    if anchor.normalized_name == member.normalized_name:
        return 1.0
    return cosine_similarity(
        vector_by_id[anchor.member_id], vector_by_id[member.member_id]
    )
