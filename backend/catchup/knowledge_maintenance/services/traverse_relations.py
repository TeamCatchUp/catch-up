"""관계 경로를 따라가 도달 노드와 근거를 모은다.

정의가 고른 경로는 걸음의 목록이다. 순회는 그 걸음을 하나씩 밟으며
frontier를 갈아 끼우는 일이고, 걸음마다 저장소 조회는 딱 한 번이다 —
frontier 노드를 한 번에 넘기면 노드 수만큼 왕복이 늘어나는 것을 막을 수
있고, 같은 걸음의 결과가 한 번의 정렬로 묶여 차례가 흔들리지 않는다.

두 가지를 반드시 막는다. 하나는 폭발이다: 허브 노드 하나가 이웃 수천을
달고 있으면 문서가 그래프 전체를 끌어온다. 그래서 걸음마다 이웃 수를
상한으로 자르고, 잘랐다는 사실을 걸음 번호로 남겨 문서가 자신이 완전하지
않음을 알 수 있게 한다. 다른 하나는 사이클이다: 이미 밟은 노드로 되돌아
가면 순회가 끝나지 않는다. 그래서 시작 노드를 포함해 한 번 방문한 노드는
다음 frontier에서 제외한다.

근거 장부는 도달에 실제로 쓰인 간선만 담는다. 잘려 나간 이웃이나 이미
방문한 노드로만 가는 간선은 문서에 실리는 노드를 만들어 내지 않았으므로
근거가 될 수 없다. 남은 이웃에 닿은 간선은 모두 남긴다 — 같은 노드로 가는
간선이 둘이면 둘 다 그 노드가 문서에 실린 이유이기 때문이다.

검색은 없다. 순회는 주입받은 저장소 포트만 쓰고 SQL도 session도 모른다.
같은 입력이면 같은 결과가 나와야 하고, 그 재현성은 걸음마다의 사전순
정렬에서 나온다.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from catchup.knowledge_maintenance.domain.artifact_definition import DIRECTION_ANY
from catchup.knowledge_maintenance.domain.artifact_definition import DIRECTION_IN
from catchup.knowledge_maintenance.domain.artifact_definition import DIRECTION_OUT
from catchup.knowledge_maintenance.domain.artifact_definition import MAX_NODES_PER_STEP
from catchup.knowledge_maintenance.domain.artifact_definition import RelationPath
from catchup.knowledge_maintenance.ports.relations import RelationRepository
from catchup.knowledge_maintenance.ports.relations import StoredRelationEdge


@dataclass(frozen=True, slots=True)
class PathTraversal:
    """경로 하나를 따라간 결과를 담는다.

    Attributes:
        reached: 마지막 step까지 도달한 노드 id들. 경로 순→id순 정렬,
            중복 제거 완료.
        relation_ids: 경로상 거쳐간 모든 관계 id (중간 step 포함).
        assertion_lines: 도달에 쓰인 관계들의 assertion_text.
            None인 관계는 줄을 만들지 않는다(장부에는 남는다).
        truncated_steps: 상한에 걸려 잘린 step 번호들(0-base).
    """

    reached: tuple[uuid.UUID, ...]
    relation_ids: tuple[uuid.UUID, ...]
    assertion_lines: tuple[str, ...]
    truncated_steps: tuple[int, ...]


def traverse_relation_path(
    relations: RelationRepository,
    *,
    start_node_id: uuid.UUID,
    path: RelationPath,
    now: datetime,
) -> PathTraversal:
    """시작 노드에서 경로를 따라가 도달 노드와 근거를 모은다.

    걸음마다 저장소를 한 번 부르고, 돌아온 간선에서 frontier 반대쪽
    끝점을 이웃으로 삼는다. 이웃은 id 사전순으로 세우고 상한을 넘은
    뒤쪽을 버린다. 자른 걸음의 번호는 truncated_steps에 남는다.

    이미 방문한 노드는 이웃에서 뺀다. 시작 노드도 방문한 것으로 치므로
    A→B→A 같은 왕복은 두 번째 걸음에서 멈춘다.

    근거로 남기는 간선의 규칙은 하나다: 남은 이웃에 닿은 간선은 모두
    남긴다. 간선 id 사전순으로 담으므로 같은 노드로 가는 간선이 여럿
    이어도 차례가 정해진다. 같은 간선이 두 걸음에 걸쳐 다시 나오면 한
    번만 담는다 — 근거 장부는 어떤 간선을 썼는지의 목록이지 몇 번
    스쳤는지의 기록이 아니다.

    이을 노드가 없어지면 남은 걸음은 조회하지 않는다. 걸음이 하나도
    없는 경로는 시작 노드 자신을 도달점으로 돌려준다.

    Raises:
        ValueError: 걸음의 방향이 out·in·any 셋 중 하나가 아닐 때
            던진다. 모르는 방향을 임의로 해석하면 정의가 고르지 않은
            간선이 문서에 실린다.
    """
    visited = {start_node_id}
    frontier: tuple[uuid.UUID, ...] = (start_node_id,)
    relation_ids: list[uuid.UUID] = []
    assertion_lines: list[str] = []
    truncated_steps: list[int] = []
    recorded: set[uuid.UUID] = set()

    for index, step in enumerate(path.steps):
        if not frontier:
            break
        edges = relations.find_edges(
            node_ids=list(frontier),
            relation_type=step.relation_type,
            direction=step.direction,
            now=now,
        )
        frontier_nodes = set(frontier)
        arrivals: list[tuple[StoredRelationEdge, uuid.UUID]] = []
        for edge in sorted(edges, key=lambda edge: str(edge.id)):
            neighbor = _neighbor_of(edge, step.direction, frontier_nodes)
            if neighbor in visited:
                continue
            arrivals.append((edge, neighbor))

        neighbors = sorted({neighbor for _, neighbor in arrivals}, key=str)
        if len(neighbors) > MAX_NODES_PER_STEP:
            truncated_steps.append(index)
            neighbors = neighbors[:MAX_NODES_PER_STEP]
        kept = set(neighbors)

        for edge, neighbor in arrivals:
            if neighbor not in kept or edge.id in recorded:
                continue
            recorded.add(edge.id)
            relation_ids.append(edge.id)
            if edge.assertion_text is not None:
                assertion_lines.append(edge.assertion_text)

        visited |= kept
        frontier = tuple(neighbors)

    return PathTraversal(
        reached=frontier,
        relation_ids=tuple(relation_ids),
        assertion_lines=tuple(assertion_lines),
        truncated_steps=tuple(truncated_steps),
    )


def _neighbor_of(
    edge: StoredRelationEdge,
    direction: str,
    frontier_nodes: set[uuid.UUID],
) -> uuid.UUID:
    """간선에서 다음 걸음의 출발점이 될 끝점을 고른다.

    out이면 도착 쪽이, in이면 출발 쪽이 이웃이다. any는 어느 쪽이
    frontier에 걸렸는지 모르므로 출발 쪽이 frontier면 도착 쪽을,
    아니면 출발 쪽을 이웃으로 본다. 양 끝이 모두 frontier인 간선은
    어느 쪽을 골라도 이미 방문한 노드라 순회에서 걸러진다.

    Raises:
        ValueError: 방향이 규약 밖일 때 던진다.
    """
    if direction == DIRECTION_OUT:
        return edge.target_node_id
    if direction == DIRECTION_IN:
        return edge.source_node_id
    if direction == DIRECTION_ANY:
        if edge.source_node_id in frontier_nodes:
            return edge.target_node_id
        return edge.source_node_id
    raise ValueError(f"알 수 없는 관계 방향이다: {direction!r}")
