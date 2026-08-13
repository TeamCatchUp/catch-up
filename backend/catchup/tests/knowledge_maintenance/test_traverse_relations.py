"""관계 경로 순회를 인메모리 저장소로 확인한다.

순회는 저장소의 한 걸음을 되풀이하는 순수 도메인 함수다. 그래서 확인할
것은 SQL이 아니라 되풀이의 규칙이다 — 방향에 따라 어느 끝점을 다음
출발점으로 삼는지, 상한에 걸린 이웃을 어떻게 버리는지, 사이클에서 멈추는지,
버려진 이웃으로 가는 간선이 근거 장부에 남지 않는지.

저장소 fake는 실 조회의 계약을 그대로 흉내 낸다: 관계 종류는 정확히
일치해야 하고, 방향은 out·in·any 규칙을 따르며, 결과는 관계 식별자
사전순이다. 이 계약이 어긋난 fake는 순회의 정렬 의존성을 가려 버린다.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from datetime import timezone

import pytest

from catchup.knowledge_maintenance.domain.artifact_definition import DIRECTION_ANY
from catchup.knowledge_maintenance.domain.artifact_definition import DIRECTION_IN
from catchup.knowledge_maintenance.domain.artifact_definition import DIRECTION_OUT
from catchup.knowledge_maintenance.domain.artifact_definition import MAX_NODES_PER_STEP
from catchup.knowledge_maintenance.domain.artifact_definition import RelationPath
from catchup.knowledge_maintenance.domain.artifact_definition import RelationStep
from catchup.knowledge_maintenance.ports.relations import StoredRelationEdge
from catchup.knowledge_maintenance.services.traverse_relations import (
    traverse_relation_path,
)

NOW = datetime(2026, 8, 12, tzinfo=timezone.utc)


def node(number: int) -> uuid.UUID:
    """확인용 노드 식별자를 번호에서 만든다.

    번호 순서가 사전순과 같아지도록 자리를 채운다. 정렬을 확인하는
    시험이 우연한 식별자에 기대지 않게 하려는 것이다.
    """
    return uuid.UUID(f"00000000-0000-4000-8000-{number:012d}")


def relation(number: int) -> uuid.UUID:
    """확인용 관계 식별자를 번호에서 만든다."""
    return uuid.UUID(f"ffffffff-0000-4000-8000-{number:012d}")


@dataclass
class FakeRelationRepository:
    """관계 한 걸음 조회를 메모리에서 흉내 낸다.

    Attributes:
        edges: 저장된 간선들을 관계 종류별로 담는다.
        calls: 걸음마다 어떤 인자로 불렸는지 기록한다. 걸음당 조회가
            한 번인지 확인하는 데 쓴다.
    """

    edges: dict[str, list[StoredRelationEdge]] = field(default_factory=dict)
    calls: list[tuple[tuple[uuid.UUID, ...], str, str]] = field(
        default_factory=list
    )

    def add(
        self,
        relation_type: str,
        relation_id: uuid.UUID,
        source_node_id: uuid.UUID,
        target_node_id: uuid.UUID,
        assertion_text: str | None = None,
    ) -> None:
        """간선 하나를 저장한다."""
        self.edges.setdefault(relation_type, []).append(
            StoredRelationEdge(
                id=relation_id,
                source_node_id=source_node_id,
                target_node_id=target_node_id,
                assertion_text=assertion_text,
            )
        )

    def find_edges(
        self,
        *,
        node_ids: Sequence[uuid.UUID],
        relation_type: str,
        direction: str,
        now: datetime,
    ) -> list[StoredRelationEdge]:
        """주어진 노드에 걸린 간선을 방향 규칙대로 고른다."""
        assert now == NOW
        self.calls.append((tuple(node_ids), relation_type, direction))
        wanted = set(node_ids)
        found = []
        for edge in self.edges.get(relation_type, []):
            if direction == DIRECTION_OUT:
                matched = edge.source_node_id in wanted
            elif direction == DIRECTION_IN:
                matched = edge.target_node_id in wanted
            else:
                matched = (
                    edge.source_node_id in wanted
                    or edge.target_node_id in wanted
                )
            if matched:
                found.append(edge)
        return sorted(found, key=lambda edge: str(edge.id))


def test_two_hop_collects_intermediate_relation_ids() -> None:
    """두 걸음을 따라가면 중간 걸음의 관계도 장부에 남는다."""
    repository = FakeRelationRepository()
    repository.add("owns", relation(1), node(1), node(2), "A가 B를 맡는다")
    repository.add("member_of", relation(2), node(3), node(2), "C는 B 소속")

    result = traverse_relation_path(
        repository,
        start_node_id=node(1),
        path=RelationPath(
            steps=(
                RelationStep("owns", DIRECTION_OUT),
                RelationStep("member_of", DIRECTION_IN),
            )
        ),
        now=NOW,
    )

    assert result.reached == (node(3),)
    assert set(result.relation_ids) == {relation(1), relation(2)}
    assert result.assertion_lines == ("A가 B를 맡는다", "C는 B 소속")
    assert result.truncated_steps == ()


def test_one_lookup_per_step() -> None:
    """걸음마다 조회는 한 번이고 frontier 전체를 한꺼번에 넘긴다."""
    repository = FakeRelationRepository()
    repository.add("owns", relation(1), node(1), node(2))
    repository.add("owns", relation(2), node(1), node(3))
    repository.add("reports_to", relation(3), node(2), node(4))
    repository.add("reports_to", relation(4), node(3), node(5))

    result = traverse_relation_path(
        repository,
        start_node_id=node(1),
        path=RelationPath(
            steps=(
                RelationStep("owns", DIRECTION_OUT),
                RelationStep("reports_to", DIRECTION_OUT),
            )
        ),
        now=NOW,
    )

    assert result.reached == (node(4), node(5))
    assert repository.calls == [
        ((node(1),), "owns", DIRECTION_OUT),
        ((node(2), node(3)), "reports_to", DIRECTION_OUT),
    ]


def test_step_cap_truncates_and_marks() -> None:
    """상한을 넘은 이웃은 앞에서부터 남기고 걸음 번호를 기록한다."""
    repository = FakeRelationRepository()
    for number in range(1, 61):
        repository.add(
            "owns", relation(number), node(1), node(100 + number), f"L{number}"
        )

    result = traverse_relation_path(
        repository,
        start_node_id=node(1),
        path=RelationPath(steps=(RelationStep("owns", DIRECTION_OUT),)),
        now=NOW,
    )

    assert len(result.reached) == MAX_NODES_PER_STEP
    assert result.reached == tuple(
        node(100 + number) for number in range(1, MAX_NODES_PER_STEP + 1)
    )
    assert result.truncated_steps == (0,)
    assert len(result.relation_ids) == MAX_NODES_PER_STEP
    assert relation(60) not in result.relation_ids
    assert "L60" not in result.assertion_lines


def test_edges_to_dropped_nodes_do_not_contribute() -> None:
    """버려진 이웃으로만 가는 간선은 근거 장부에 남지 않는다."""
    repository = FakeRelationRepository()
    for number in range(1, 61):
        repository.add("owns", relation(number), node(1), node(100 + number))
    # 잘려 나간 이웃으로 가는 두 번째 간선도 함께 버려져야 한다.
    repository.add("owns", relation(90), node(1), node(160), "잘린 쪽")

    result = traverse_relation_path(
        repository,
        start_node_id=node(1),
        path=RelationPath(steps=(RelationStep("owns", DIRECTION_OUT),)),
        now=NOW,
    )

    assert relation(90) not in result.relation_ids
    assert result.assertion_lines == ()


def test_cycle_does_not_loop() -> None:
    """이미 방문한 노드로는 돌아가지 않는다."""
    repository = FakeRelationRepository()
    repository.add("owns", relation(1), node(1), node(2))
    repository.add("owns", relation(2), node(2), node(1))

    result = traverse_relation_path(
        repository,
        start_node_id=node(1),
        path=RelationPath(
            steps=(
                RelationStep("owns", DIRECTION_OUT),
                RelationStep("owns", DIRECTION_OUT),
            )
        ),
        now=NOW,
    )

    assert node(1) not in result.reached
    assert result.reached == ()
    assert result.relation_ids == (relation(1),)


def test_traversal_stops_when_frontier_empties() -> None:
    """이을 노드가 없으면 남은 걸음은 조회하지 않는다."""
    repository = FakeRelationRepository()

    result = traverse_relation_path(
        repository,
        start_node_id=node(1),
        path=RelationPath(
            steps=(
                RelationStep("owns", DIRECTION_OUT),
                RelationStep("owns", DIRECTION_OUT),
            )
        ),
        now=NOW,
    )

    assert result.reached == ()
    assert len(repository.calls) == 1


def test_incoming_direction_walks_to_source() -> None:
    """in 방향은 출발 쪽 노드를 다음 걸음의 출발점으로 삼는다."""
    repository = FakeRelationRepository()
    repository.add("member_of", relation(1), node(2), node(1))

    result = traverse_relation_path(
        repository,
        start_node_id=node(1),
        path=RelationPath(steps=(RelationStep("member_of", DIRECTION_IN),)),
        now=NOW,
    )

    assert result.reached == (node(2),)


def test_any_direction_walks_to_the_far_side() -> None:
    """any 방향은 frontier가 아닌 쪽 끝점으로 이어진다."""
    repository = FakeRelationRepository()
    repository.add("owns", relation(1), node(1), node(3))
    repository.add("owns", relation(2), node(2), node(1))

    result = traverse_relation_path(
        repository,
        start_node_id=node(1),
        path=RelationPath(steps=(RelationStep("owns", DIRECTION_ANY),)),
        now=NOW,
    )

    assert result.reached == (node(2), node(3))


def test_self_loop_is_not_reached() -> None:
    """자기 자신으로 도는 간선은 도달점이 되지 않는다."""
    repository = FakeRelationRepository()
    repository.add("owns", relation(1), node(1), node(1), "자기 자신")

    result = traverse_relation_path(
        repository,
        start_node_id=node(1),
        path=RelationPath(steps=(RelationStep("owns", DIRECTION_ANY),)),
        now=NOW,
    )

    assert result.reached == ()
    assert result.relation_ids == ()
    assert result.assertion_lines == ()


def test_missing_assertion_text_keeps_relation_id() -> None:
    """문장이 없는 관계도 근거 장부에는 남고 줄만 만들지 않는다."""
    repository = FakeRelationRepository()
    repository.add("owns", relation(1), node(1), node(2), None)
    repository.add("owns", relation(2), node(1), node(3), "설명 있음")

    result = traverse_relation_path(
        repository,
        start_node_id=node(1),
        path=RelationPath(steps=(RelationStep("owns", DIRECTION_OUT),)),
        now=NOW,
    )

    assert result.relation_ids == (relation(1), relation(2))
    assert result.assertion_lines == ("설명 있음",)


def test_parallel_edges_to_the_same_node_both_count() -> None:
    """같은 노드로 가는 간선이 둘이면 둘 다 근거로 남는다."""
    repository = FakeRelationRepository()
    repository.add("owns", relation(2), node(1), node(2), "둘째 근거")
    repository.add("owns", relation(1), node(1), node(2), "첫째 근거")

    result = traverse_relation_path(
        repository,
        start_node_id=node(1),
        path=RelationPath(steps=(RelationStep("owns", DIRECTION_OUT),)),
        now=NOW,
    )

    assert result.reached == (node(2),)
    assert result.relation_ids == (relation(1), relation(2))
    assert result.assertion_lines == ("첫째 근거", "둘째 근거")


def test_empty_path_reaches_the_start_node() -> None:
    """걸음이 없으면 시작 노드 자신이 도달점이다."""
    repository = FakeRelationRepository()

    result = traverse_relation_path(
        repository,
        start_node_id=node(1),
        path=RelationPath(steps=()),
        now=NOW,
    )

    assert result.reached == (node(1),)
    assert repository.calls == []


def test_unknown_direction_is_rejected() -> None:
    """규약에 없는 방향은 조용히 넘기지 않고 거부한다."""
    repository = FakeRelationRepository()
    repository.add("owns", relation(1), node(1), node(2))

    with pytest.raises(ValueError):
        traverse_relation_path(
            repository,
            start_node_id=node(1),
            path=RelationPath(steps=(RelationStep("owns", "sideways"),)),
            now=NOW,
        )


def test_deterministic_ordering() -> None:
    """같은 지식 상태를 두 번 물으면 같은 결과가 나온다."""
    repository = FakeRelationRepository()
    repository.add("owns", relation(5), node(1), node(9), "다섯")
    repository.add("owns", relation(3), node(1), node(4), "셋")
    repository.add("owns", relation(4), node(1), node(7), None)

    path = RelationPath(steps=(RelationStep("owns", DIRECTION_OUT),))
    first = traverse_relation_path(
        repository, start_node_id=node(1), path=path, now=NOW
    )
    second = traverse_relation_path(
        repository, start_node_id=node(1), path=path, now=NOW
    )

    assert first == second
    assert first.reached == (node(4), node(7), node(9))
    assert first.relation_ids == (relation(3), relation(4), relation(5))
    assert first.assertion_lines == ("셋", "다섯")
