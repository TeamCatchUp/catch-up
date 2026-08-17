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

from catchup.knowledge_maintenance.domain.artifact import BLOCK_KIND_RELATION_SECTION
from catchup.knowledge_maintenance.domain.artifact import validate_blocks
from catchup.knowledge_maintenance.domain.artifact_definition import DIRECTION_ANY
from catchup.knowledge_maintenance.domain.artifact_definition import DIRECTION_IN
from catchup.knowledge_maintenance.domain.artifact_definition import DIRECTION_OUT
from catchup.knowledge_maintenance.domain.artifact_definition import MAX_NODES_PER_STEP
from catchup.knowledge_maintenance.domain.artifact_definition import RelationPath
from catchup.knowledge_maintenance.domain.artifact_definition import RelationStep
from catchup.knowledge_maintenance.ports.relations import StoredRelationEdge
from catchup.knowledge_maintenance.services.traverse_relations import (
    RELATION_HINT_PREFIX,
)
from catchup.knowledge_maintenance.services.traverse_relations import PathTraversal
from catchup.knowledge_maintenance.services.traverse_relations import default_edge_line
from catchup.knowledge_maintenance.services.traverse_relations import (
    relation_section_block,
)
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
        source_display_name: str | None = None,
        target_display_name: str | None = None,
    ) -> None:
        """간선 하나를 저장한다.

        이름을 주지 않으면 식별자 문자열을 그대로 이름으로 쓴다. 이름
        순서와 식별자 순서가 같아지므로, 이름 정렬을 확인하지 않는
        시험이 이름을 일일이 붙이지 않아도 된다.
        """
        self.edges.setdefault(relation_type, []).append(
            StoredRelationEdge(
                id=relation_id,
                source_node_id=source_node_id,
                target_node_id=target_node_id,
                assertion_text=assertion_text,
                source_display_name=(
                    source_display_name
                    if source_display_name is not None
                    else str(source_node_id)
                ),
                target_display_name=(
                    target_display_name
                    if target_display_name is not None
                    else str(target_node_id)
                ),
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
    assert result.hint_lines == ("A가 B를 맡는다", "C는 B 소속")
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
    assert "L60" not in result.hint_lines


def test_step_cap_keeps_the_first_names_not_the_first_ids() -> None:
    """상한은 이름 차례로 자른다 — 식별자 차례로 자르지 않는다.

    이름과 식별자의 차례를 일부러 반대로 둔다. 식별자로 자르면 이름이
    가장 앞선 노드가 잘려 나가고, 식별자를 다시 만들 때마다 남는 이웃이
    달라진다.
    """
    repository = FakeRelationRepository()
    for number in range(1, 52):
        repository.add(
            "owns",
            relation(number),
            node(1),
            node(200 + number),
            target_display_name=f"이웃{51 - number:02d}",
        )

    result = traverse_relation_path(
        repository,
        start_node_id=node(1),
        path=RelationPath(steps=(RelationStep("owns", DIRECTION_OUT),)),
        now=NOW,
    )

    assert result.truncated_steps == (0,)
    assert len(result.reached) == MAX_NODES_PER_STEP
    assert result.reached == tuple(
        node(200 + number) for number in range(51, 1, -1)
    )
    # 식별자가 가장 앞선 이웃은 이름이 가장 뒤이므로 잘려 나간다.
    assert node(201) not in result.reached
    assert relation(1) not in result.relation_ids


def test_dead_branch_edges_stay_out_of_the_ledger() -> None:
    """중간에서 끊긴 가지의 간선은 본문에도 장부에도 남지 않는다."""
    repository = FakeRelationRepository()
    repository.add("owns", relation(1), node(1), node(2), "끊기는 가지")
    repository.add("owns", relation(2), node(1), node(3), "이어지는 가지")
    repository.add("member_of", relation(3), node(3), node(4), "끝까지 감")

    result = traverse_relation_path(
        repository,
        start_node_id=node(1),
        path=RelationPath(
            steps=(
                RelationStep("owns", DIRECTION_OUT),
                RelationStep("member_of", DIRECTION_OUT),
            )
        ),
        now=NOW,
    )

    assert result.reached == (node(4),)
    assert relation(1) not in result.relation_ids
    assert "끊기는 가지" not in result.hint_lines
    assert result.relation_ids == (relation(2), relation(3))
    assert result.hint_lines == ("이어지는 가지", "끝까지 감")


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
    assert "잘린 쪽" not in result.hint_lines


def test_cycle_does_not_loop() -> None:
    """이미 방문한 노드로는 돌아가지 않는다.

    되돌아가느라 도달이 사라진 가지는 완주하지 못한 가지다. 그래서
    첫 걸음의 간선도 근거 장부에 남지 않는다.
    """
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
    assert result.relation_ids == ()
    assert result.hint_lines == ()


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
    assert result.hint_lines == ()


def test_missing_assertion_text_keeps_relation_id() -> None:
    """문장이 없는 관계도 근거 장부에 남고 힌트 줄만 비운다."""
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
    assert result.hint_lines == ("", "설명 있음")


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
    assert result.hint_lines == ("첫째 근거", "둘째 근거")


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
    assert first.hint_lines == ("셋", "", "다섯")


PATH_2HOP = RelationPath(
    steps=(
        RelationStep("owns", DIRECTION_OUT),
        RelationStep("member_of", DIRECTION_IN),
    )
)


def test_block_carries_full_relation_ledger() -> None:
    """블록은 경로가 거쳐간 관계를 전부 근거 장부로 나른다."""
    traversal = PathTraversal(
        reached=(node(3),),
        relation_ids=(relation(1), relation(2)),
        edge_lines=("A → owns → B", "C → member_of → B"),
        hint_lines=("A가 B를 맡는다", "C는 B 소속"),
        truncated_steps=(),
    )

    block = relation_section_block(
        path=PATH_2HOP, traversal=traversal, ontology_version="v1"
    )

    assert block is not None
    assert block.block_kind == BLOCK_KIND_RELATION_SECTION
    assert set(block.relation_ids) == {relation(1), relation(2)}
    assert block.claim_ids == ()
    assert block.sources == ()
    assert block.proposal_ids == ()
    assert block.ontology_version == "v1"
    assert block.body == (
        "A → owns → B\n  ↳ A가 B를 맡는다\nC → member_of → B\n  ↳ C는 B 소속"
    )
    validate_blocks((block,))


def test_heading_names_the_path_regardless_of_content() -> None:
    """제목은 경로 정의만으로 정해진다 — 내용이 달라도 같다."""
    first = relation_section_block(
        path=PATH_2HOP,
        traversal=PathTraversal(
            reached=(node(3),),
            relation_ids=(relation(1),),
            edge_lines=("A → owns → B",),
            hint_lines=("첫째",),
            truncated_steps=(),
        ),
        ontology_version=None,
    )
    second = relation_section_block(
        path=PATH_2HOP,
        traversal=PathTraversal(
            reached=(node(4),),
            relation_ids=(relation(2),),
            edge_lines=("A → owns → C",),
            hint_lines=("둘째",),
            truncated_steps=(),
        ),
        ontology_version=None,
    )

    assert first is not None
    assert second is not None
    assert first.heading == "owns(out) → member_of(in)"
    assert first.heading == second.heading


def test_truncation_appears_in_body() -> None:
    """잘린 걸음은 본문 마지막 줄에 드러난다 — 조용한 누락 금지."""
    block = relation_section_block(
        path=PATH_2HOP,
        traversal=PathTraversal(
            reached=(node(3),),
            relation_ids=(relation(1),),
            edge_lines=("A → owns → B",),
            hint_lines=("A가 B를 맡는다",),
            truncated_steps=(0,),
        ),
        ontology_version="v1",
    )

    assert block is not None
    assert "상한 초과" in block.body
    assert block.body.splitlines()[-1] == (
        f"(step 0에서 이웃 {MAX_NODES_PER_STEP}개 상한 초과 — 일부만 따라감)"
    )


def test_every_truncated_step_gets_its_own_line() -> None:
    """걸음이 여럿 잘리면 걸음마다 한 줄씩 오름차순으로 남는다."""
    block = relation_section_block(
        path=PATH_2HOP,
        traversal=PathTraversal(
            reached=(node(3),),
            relation_ids=(relation(1),),
            edge_lines=(),
            hint_lines=(),
            truncated_steps=(1, 0),
        ),
        ontology_version="v1",
    )

    assert block is not None
    assert block.body.splitlines() == [
        f"(step 0에서 이웃 {MAX_NODES_PER_STEP}개 상한 초과 — 일부만 따라감)",
        f"(step 1에서 이웃 {MAX_NODES_PER_STEP}개 상한 초과 — 일부만 따라감)",
    ]
    validate_blocks((block,))


def test_truncation_alone_still_makes_a_block() -> None:
    """도달이 없어도 잘림 자체가 정보이므로 블록은 남는다."""
    block = relation_section_block(
        path=PATH_2HOP,
        traversal=PathTraversal(
            reached=(),
            relation_ids=(relation(1),),
            edge_lines=(),
            hint_lines=(),
            truncated_steps=(0,),
        ),
        ontology_version="v1",
    )

    assert block is not None
    assert "상한 초과" in block.body
    validate_blocks((block,))


def test_empty_traversal_returns_none() -> None:
    """도달도 잘림도 없으면 블록을 만들지 않는다."""
    empty = PathTraversal(
        reached=(),
        relation_ids=(),
        edge_lines=(),
        hint_lines=(),
        truncated_steps=(),
    )

    assert (
        relation_section_block(
            path=PATH_2HOP, traversal=empty, ontology_version="v1"
        )
        is None
    )


def test_reached_without_relation_ledger_returns_none() -> None:
    """근거 장부가 비면 블록을 만들지 않는다 — 빈 경로의 시작 노드."""
    block = relation_section_block(
        path=RelationPath(steps=()),
        traversal=PathTraversal(
            reached=(node(1),),
            relation_ids=(),
            edge_lines=(),
            hint_lines=(),
            truncated_steps=(),
        ),
        ontology_version="v1",
    )

    assert block is None


def test_dropped_reach_without_truncation_returns_none() -> None:
    """사이클로 도달이 사라지고 잘림도 없으면 블록이 없다."""
    block = relation_section_block(
        path=PATH_2HOP,
        traversal=PathTraversal(
            reached=(),
            relation_ids=(relation(1),),
            edge_lines=("A → owns → B",),
            hint_lines=("A가 B를 맡는다",),
            truncated_steps=(),
        ),
        ontology_version="v1",
    )

    assert block is None


PATH_REQUESTED_BY = RelationPath(
    steps=(RelationStep("requested_by", DIRECTION_OUT),)
)


def _requested_by_repository(
    assertion_text: str | None,
) -> FakeRelationRepository:
    """이름이 붙은 간선 하나짜리 저장소를 만든다."""
    repository = FakeRelationRepository()
    repository.add(
        "requested_by",
        relation(1),
        node(1),
        node(2),
        assertion_text,
        source_display_name="기능 요청 A",
        target_display_name="팀원A",
    )
    return repository


def test_edge_lines_name_both_parties_and_keep_assertion_as_hint() -> None:
    """사실 입력은 양끝 이름을 명시한 줄이고 원문은 힌트로 남는다."""
    result = traverse_relation_path(
        _requested_by_repository("커넥터 있어?"),
        start_node_id=node(1),
        path=PATH_REQUESTED_BY,
        now=NOW,
    )

    assert result.edge_lines == ("기능 요청 A → requested_by → 팀원A",)
    assert result.hint_lines == ("커넥터 있어?",)


def test_edge_line_formatter_is_injectable() -> None:
    """줄 서식은 주입할 수 있다 — 노출 수준이 이 자리를 갈아 끼운다."""
    result = traverse_relation_path(
        _requested_by_repository("커넥터 있어?"),
        start_node_id=node(1),
        path=PATH_REQUESTED_BY,
        now=NOW,
        edge_line=lambda edge, rel: f"[{rel}] {edge.target_display_name}",
    )

    assert result.edge_lines == ("[requested_by] 팀원A",)


def test_relation_block_body_puts_hint_under_its_edge() -> None:
    """블록 본문은 간선 줄 바로 아래에 그 간선의 힌트를 붙인다."""
    result = traverse_relation_path(
        _requested_by_repository("커넥터 있어?"),
        start_node_id=node(1),
        path=PATH_REQUESTED_BY,
        now=NOW,
    )

    block = relation_section_block(
        path=PATH_REQUESTED_BY, traversal=result, ontology_version="v1"
    )

    assert block is not None
    assert block.body == "기능 요청 A → requested_by → 팀원A\n  ↳ 커넥터 있어?"


def test_relation_block_collapses_multiline_hint_into_one_line() -> None:
    """여러 줄짜리 원문도 힌트 줄 하나로 접는다.

    접두가 붙는 것은 첫 줄뿐이라, 줄바꿈을 그대로 두면 둘째 줄부터가
    접두 없는 줄이 되어 소비처에서 사실 줄로 읽힌다.
    """
    result = traverse_relation_path(
        _requested_by_repository("첫 줄\n둘째 줄"),
        start_node_id=node(1),
        path=PATH_REQUESTED_BY,
        now=NOW,
    )

    block = relation_section_block(
        path=PATH_REQUESTED_BY, traversal=result, ontology_version="v1"
    )

    assert block is not None
    body_lines = block.body.split("\n")
    assert [
        line for line in body_lines if line.startswith(RELATION_HINT_PREFIX)
    ] == ["  ↳ 첫 줄 둘째 줄"]
    assert len(body_lines) == 2


def test_edge_line_collapses_newline_in_display_name() -> None:
    """표시 이름에 줄바꿈이 있어도 간선은 한 줄로 적는다."""
    edge = StoredRelationEdge(
        id=relation(1),
        source_node_id=node(1),
        target_node_id=node(2),
        assertion_text=None,
        source_display_name="기능\n요청 A",
        target_display_name="팀원A  님",
    )

    line = default_edge_line(edge, "requested_by")

    assert line == "기능 요청 A → requested_by → 팀원A 님"


def test_relation_block_omits_hint_line_when_assertion_missing() -> None:
    """원문 문장이 없으면 힌트 줄 자체를 만들지 않는다."""
    result = traverse_relation_path(
        _requested_by_repository(None),
        start_node_id=node(1),
        path=PATH_REQUESTED_BY,
        now=NOW,
    )

    block = relation_section_block(
        path=PATH_REQUESTED_BY, traversal=result, ontology_version="v1"
    )

    assert block is not None
    assert block.body == "기능 요청 A → requested_by → 팀원A"
