from __future__ import annotations

import math
import random

import pytest

from catchup.knowledge_maintenance.domain.entity_blocking import BlockingMember
from catchup.knowledge_maintenance.domain.entity_blocking import BlockingOrigin
from catchup.knowledge_maintenance.domain.entity_blocking import build_entity_blocks


def _member(
    member_id: str,
    name: str,
    entity_type: str = "feature_request",
    origin: BlockingOrigin = BlockingOrigin.CANDIDATE,
) -> BlockingMember:
    return BlockingMember(
        member_id=member_id,
        entity_type=entity_type,
        name=name,
        origin=origin,
    )


def _unit(angle: float) -> tuple[float, float]:
    """단위원 위의 벡터를 만든다. 두 벡터의 cosine은 각도 차의 cos다."""
    return (math.cos(angle), math.sin(angle))


def _angle_for(similarity: float) -> float:
    return math.acos(similarity)


def _names(blocks) -> list[list[str]]:
    return [[member.name for member in block.members] for block in blocks]


def test_similarity_above_threshold_joins_one_block() -> None:
    """임계값 이상이면 같은 블록으로 묶인다."""
    members = (
        _member("a", "Google Workspace 연동"),
        _member("b", "Google Workspace 커넥터"),
    )
    vectors = (_unit(0.0), _unit(_angle_for(0.9)))

    blocks = build_entity_blocks(members, vectors)

    assert len(blocks) == 1
    assert len(blocks[0].members) == 2


def test_similarity_below_threshold_stays_apart() -> None:
    """임계값 미만이면 각자 블록으로 남는다."""
    members = (
        _member("a", "Google Workspace 연동"),
        _member("b", "결제 실패 알림"),
    )
    vectors = (_unit(0.0), _unit(_angle_for(0.5)))

    blocks = build_entity_blocks(members, vectors)

    assert len(blocks) == 2
    assert all(len(block.members) == 1 for block in blocks)


def test_threshold_is_inclusive() -> None:
    """임계값과 정확히 같으면 묶는다. 재현율 우선이다."""
    members = (_member("a", "가"), _member("b", "나"))
    vectors = ((1.0, 0.0), (1.0, 0.0))

    blocks = build_entity_blocks(members, vectors, threshold=1.0)

    assert len(blocks) == 1


def test_different_entity_types_never_meet() -> None:
    """entity_type이 다르면 벡터가 같아도 비교하지 않는다."""
    members = (
        _member("a", "Google Workspace 연동", entity_type="feature_request"),
        _member("b", "Google Workspace 연동 지원 여부", entity_type="faq_question"),
    )
    vectors = ((1.0, 0.0), (1.0, 0.0))

    blocks = build_entity_blocks(members, vectors)

    assert len(blocks) == 2
    assert {block.entity_type for block in blocks} == {
        "feature_request",
        "faq_question",
    }


def test_exact_name_match_joins_regardless_of_vectors() -> None:
    """정규화 이름이 같으면 임베딩과 무관하게 같은 블록이다."""
    members = (
        _member("a", "Google Workspace 연동"),
        _member("b", "google workspace  연동"),
    )
    vectors = ((1.0, 0.0), (0.0, 1.0))

    blocks = build_entity_blocks(members, vectors)

    assert len(blocks) == 1
    assert len(blocks[0].members) == 2


def test_connected_component_pulls_in_the_middle_neighbor() -> None:
    """A와 C가 안 닮아도 B를 통해 이어지면 한 블록이다."""
    members = (
        _member("a", "가"),
        _member("b", "나"),
        _member("c", "다"),
    )
    step = _angle_for(0.9)
    vectors = (_unit(0.0), _unit(step), _unit(step * 2))

    blocks = build_entity_blocks(members, vectors)

    assert len(blocks) == 1
    assert len(blocks[0].members) == 3


def test_block_size_cap_splits_the_component() -> None:
    """상한을 넘으면 유사도 상위부터 채우고 나머지는 다시 묶는다."""
    members = tuple(_member(f"m{index}", f"이름 {index}") for index in range(7))
    vectors = tuple((1.0, 0.0) for _ in members)

    blocks = build_entity_blocks(members, vectors, max_block_size=3)

    assert [len(block.members) for block in blocks] == [3, 3, 1]
    seen = [member.member_id for block in blocks for member in block.members]
    assert sorted(seen) == sorted(member.member_id for member in members)


def test_every_member_lands_in_exactly_one_block() -> None:
    """모든 멤버가 정확히 한 블록에 들어간다. 홀로 남는 멤버도 블록이다."""
    members = (
        _member("a", "가"),
        _member("b", "나"),
        _member("c", "다", entity_type="platform"),
    )
    vectors = (_unit(0.0), _unit(_angle_for(0.95)), _unit(0.0))

    blocks = build_entity_blocks(members, vectors)

    seen = [member.member_id for block in blocks for member in block.members]
    assert sorted(seen) == ["a", "b", "c"]


def test_existing_node_alias_joins_the_candidate_block() -> None:
    """기존 노드 별칭도 후보와 같은 블록에 들어간다."""
    members = (
        _member("cand", "Google Workspace 연동 지원"),
        _member("node", "Google Workspace 연동", origin=BlockingOrigin.NODE),
    )
    vectors = (_unit(0.0), _unit(_angle_for(0.92)))

    blocks = build_entity_blocks(members, vectors)

    assert len(blocks) == 1
    origins = {member.origin for member in blocks[0].members}
    assert origins == {BlockingOrigin.CANDIDATE, BlockingOrigin.NODE}


def test_result_does_not_depend_on_input_order() -> None:
    """입력 순서를 섞어도 같은 블록·같은 순서가 나온다."""
    members = [
        _member("a", "가"),
        _member("b", "나"),
        _member("c", "다"),
        _member("d", "라", entity_type="platform"),
        _member("e", "마", entity_type="platform"),
    ]
    step = _angle_for(0.9)
    vectors = [
        _unit(0.0),
        _unit(step),
        _unit(math.pi / 2),
        _unit(0.0),
        _unit(math.pi / 2),
    ]

    expected = _names(build_entity_blocks(tuple(members), tuple(vectors)))

    paired = list(zip(members, vectors, strict=True))
    rng = random.Random(7)
    for _ in range(5):
        rng.shuffle(paired)
        shuffled_members = tuple(item[0] for item in paired)
        shuffled_vectors = tuple(item[1] for item in paired)
        assert _names(
            build_entity_blocks(shuffled_members, shuffled_vectors)
        ) == expected


def test_empty_input_returns_no_block() -> None:
    """멤버가 없으면 블록도 없다."""
    assert build_entity_blocks((), ()) == ()


def test_vector_count_must_match_member_count() -> None:
    """벡터 수가 멤버 수와 다르면 짝을 지을 수 없어 예외다."""
    with pytest.raises(ValueError):
        build_entity_blocks((_member("a", "가"),), ())


def test_zero_vector_never_joins() -> None:
    """길이가 0인 벡터는 유사도를 잴 수 없어 홀로 남는다."""
    members = (_member("a", "가"), _member("b", "나"))
    vectors = ((0.0, 0.0), (1.0, 0.0))

    blocks = build_entity_blocks(members, vectors)

    assert len(blocks) == 2
