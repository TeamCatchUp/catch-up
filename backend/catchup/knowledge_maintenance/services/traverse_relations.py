"""관계 경로를 따라가 도달 노드와 근거를 모으고 블록으로 만든다.

이 모듈은 `ArtifactDefinition`이 고른 `RelationPath`를 받는다. `RelationPath`는
step의 순서 목록이고, step 하나는 relation_type과 direction(out·in·any)의
짝이다. 순회는 시작 노드에서 출발해 step을 순서대로 따라가며 도달 노드,
사용한 간선, 근거 줄을 모은다. 그리고 그 결과를 relation section 종류의
`ArtifactBlock` 하나로 만든다.

한 step의 처리 순서는 이렇다.

1. 순회는 현재 frontier(직전 step까지 도달한 노드들)를 저장소에 한 번에
   넘겨 간선을 조회한다.
2. 순회는 간선의 frontier 반대쪽 끝점을 이웃으로 삼고, 표시 이름 순으로,
   이름이 같으면 노드 id 순으로 정렬한다.
3. 이웃 수가 `MAX_NODES_PER_STEP`을 넘으면 순회는 뒤쪽을 버리고 그 step
   번호를 `truncated_steps`에 남긴다.
4. 남은 이웃이 다음 step의 frontier가 된다.

순회는 step마다 저장소를 딱 한 번 부른다. frontier 노드를 하나씩 조회하면
노드 수만큼 왕복이 늘어나기 때문이다. 또 같은 step의 결과가 한 번의
정렬로 묶여야 순서가 흔들리지 않는다.

순회는 step마다 이웃 수를 `MAX_NODES_PER_STEP`으로 자른다. 폭발을 막기
위해서다. 이웃 수천 개를 단 허브 노드가 하나만 있어도 문서가 그래프
전체를 끌어온다. 순회는 자른 step의 번호를 `truncated_steps`에 남긴다.
문서가 자신이 완전하지 않다고 스스로 말할 수 있게 하기 위해서다.

순회는 이미 방문한 노드를 다음 frontier에서 뺀다. 사이클을 막기
위해서다. 시작 노드도 방문한 것으로 친다. 그래서 A→B→A 같은 왕복은 두
번째 step에서 멈춘다.

근거 장부(`edge_lines`·`relation_ids`)에는 마지막 step까지 완주한 경로 위의
간선만 남는다. 잘려 나간 이웃으로 가는 간선, 이미 방문한 노드로만 가는
간선, 중간에서 끊긴 가지는 제외한다. 이런 간선들은 문서에 실리는 도달
노드를 하나도 만들어 내지 못했으므로 근거가 아니기 때문이다. 반대로 완주한
경로 위라면 같은 노드로 가는 간선이 둘이어도 순회는 둘 다 남긴다. 둘 다 그
노드가 문서에 실린 이유이기 때문이다.

블록 본문에서 관계의 사실 줄은 "A → relation_type → B" 형태로 양끝 이름을
명시한다. 관계에 붙은 원문 문장은 그 아래 `RELATION_HINT_PREFIX`가 붙은 힌트
줄로만 싣는다. 원문 문장만 싣던 때에는 읽는 쪽이 그 인용문의 화자를 상대
노드로 오해할 수 있었기 때문이다. 이 형식을 넣으면서 본문 모양이 바뀌므로
관계 블록의 hash가 한 번 바뀐다. 이것은 정의된 동작이다. 다음 컴파일에서
새 판이 한 번 난 뒤로는 다시 안정된다.

이 모듈은 순회 결과를 블록으로 옮기는 일도 함께 맡는다. 무엇을 모았는지와
그것을 어떻게 적는지가 함께 바뀌기 때문이다. 상한에 걸려 잘랐다는 사실이
본문 마지막 줄이 되는 것이 그 예다.

이 모듈은 검색을 하지 않는다. 순회는 주입받은 `RelationRepository` 포트만
쓰고 SQL도 session도 모른다.

같은 입력이면 같은 결과가 나와야 한다. 그 재현성은 step마다의 정렬에서
나온다. 순회는 이웃을 표시 이름 순으로 세우고, 이름이 같으면 노드 id
순으로 세운다. 노드 id만으로 세우면 안 된다. 그러면 상한에 걸렸을 때 남는
이웃이 이름과 무관하게 정해지고, 노드 id를 다시 만들면 같은 지식에서 다른
문서가 나오기 때문이다.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from catchup.knowledge_maintenance.domain.artifact import BLOCK_KIND_RELATION_SECTION
from catchup.knowledge_maintenance.domain.artifact import ArtifactBlock
from catchup.knowledge_maintenance.domain.artifact_definition import DIRECTION_ANY
from catchup.knowledge_maintenance.domain.artifact_definition import DIRECTION_IN
from catchup.knowledge_maintenance.domain.artifact_definition import DIRECTION_OUT
from catchup.knowledge_maintenance.domain.artifact_definition import MAX_NODES_PER_STEP
from catchup.knowledge_maintenance.domain.artifact_definition import RelationPath
from catchup.knowledge_maintenance.ports.relations import RelationRepository
from catchup.knowledge_maintenance.ports.relations import StoredRelationEdge

# 블록 body 안에서 힌트 줄을 그 위 간선 줄과 구분하는 들여쓰기 접두다.
RELATION_HINT_PREFIX = "  ↳ "

# 간선 하나를 본문 한 줄로 옮기는 서식이다. 노출 수준을 적용하는 쪽이
# 이 자리를 갈아 끼우므로 순회는 서식을 알지 않는다.
EdgeFormatter = Callable[[StoredRelationEdge, str], str]


def format_edge_line(
    edge: StoredRelationEdge,
    relation_type: str,
    *,
    source_name: str | None = None,
    target_name: str | None = None,
) -> str:
    """간선을 "A → relation_type → B" 한 줄로 적는다.

    표시 이름은 사람이 적은 자유 문장이라 줄바꿈이 섞일 수 있다. 그래서
    공백을 한 칸으로 접어 한 줄로 만든다. 한 간선은 본문 한 줄이라는
    규약이 깨지면 소비처의 줄 단위 해석이 어긋나기 때문이다. 접고 나서도
    이름이 비면 노드 식별자를 대신 쓴다. 줄에서 한쪽 끝이 통째로 사라지면
    남은 이름이 어느 쪽인지 읽는 쪽이 알 수 없다.

    source_name·target_name을 넘기면 간선의 표시 이름 대신 그 이름을
    쓴다. 노출 수준처럼 이름을 갈아 끼우는 쪽도 이 두 방어를 함께
    받으라고 열어 둔 자리다. 갈아 끼운 이름을 따로 조립하면 접기와
    대체가 빠진 줄이 본문에 실린다. 넘기지 않으면 간선의 이름을 쓴다.
    """
    source = _one_line(
        edge.source_display_name if source_name is None else source_name
    ) or str(edge.source_node_id)
    target = _one_line(
        edge.target_display_name if target_name is None else target_name
    ) or str(edge.target_node_id)
    return f"{source} → {relation_type} → {target}"


def default_edge_line(edge: StoredRelationEdge, relation_type: str) -> str:
    """간선의 표시 이름을 그대로 써서 본문 한 줄을 만든다."""
    return format_edge_line(edge, relation_type)


def _one_line(text: str | None) -> str:
    """연속 공백과 줄바꿈을 한 칸으로 접어 한 줄로 만든다."""
    return " ".join(text.split()) if text else ""


@dataclass(frozen=True, slots=True)
class PathTraversal:
    """경로 하나를 따라간 결과를 담는다.

    Attributes:
        reached: 마지막 step까지 도달한 노드 id들. 경로 순→id순 정렬,
            중복 제거 완료.
        relation_ids: 경로상 거쳐간 모든 관계 id (중간 step 포함).
        edge_lines: 도달에 쓰인 간선을 양끝 이름으로 적은 줄들.
        hint_lines: 같은 차례의 간선에 붙은 원문 문장. edge_lines와
            길이가 같고, 문장이 없는 간선은 빈 문자열이다. 길이가
            어긋나면 힌트가 옆 간선 밑으로 밀려 붙기 때문이다.
        truncated_steps: 상한에 걸려 잘린 step 번호들(0-base).
    """

    reached: tuple[uuid.UUID, ...]
    relation_ids: tuple[uuid.UUID, ...]
    edge_lines: tuple[str, ...]
    hint_lines: tuple[str, ...]
    truncated_steps: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class _Arrival:
    """한 step에서 이웃 하나에 닿은 간선 하나를 담는다.

    간선만으로는 어느 쪽이 출발이고 어느 쪽이 도착인지가 direction마다
    달라진다. 완주 여부를 뒤에서 앞으로 되짚으려면 step 기준의 출발과
    도착이 필요하므로 여기에 함께 적어 둔다.

    Attributes:
        edge: 이 도달을 만든 관계 간선을 담는다.
        from_node_id: 이 step의 frontier 쪽 끝점을 담는다.
        to_node_id: 이 step이 새로 닿은 이웃을 담는다.
        relation_type: 이 step이 따라간 관계 종류를 담는다. 간선 자신은
            종류를 들고 있지 않은데, 본문 줄에는 그 이름이 들어간다.
    """

    edge: StoredRelationEdge
    from_node_id: uuid.UUID
    to_node_id: uuid.UUID
    relation_type: str


def traverse_relation_path(
    relations: RelationRepository,
    *,
    start_node_id: uuid.UUID,
    path: RelationPath,
    now: datetime,
    edge_line: EdgeFormatter = default_edge_line,
) -> PathTraversal:
    """시작 노드에서 경로를 따라가 도달 노드와 근거를 모은다.

    이 함수는 step마다 저장소를 한 번 부르고, 돌아온 간선에서 frontier
    반대쪽 끝점을 이웃으로 삼는다. 이웃은 표시 이름 차례로, 같은
    이름이면 노드 id 차례로 세우고 상한을 넘은 뒤쪽을 버린다. 자른
    step의 번호는 truncated_steps에 남는다.

    이미 방문한 노드는 이웃에서 뺀다. 시작 노드도 방문한 것으로 치므로
    A→B→A 같은 왕복은 두 번째 step에서 멈춘다.

    근거로 남기는 간선의 규칙은 하나다. 마지막 step까지 완주한 경로
    위의 간선만 남긴다. 이 함수는 step마다 도달(_Arrival)을 따로 적어
    두었다가, 순회가 끝난 뒤 마지막 도달 노드에서 거꾸로 되짚어 그
    되짚기에 걸리지 않은 간선을 버린다. 되짚기는 step이 층을 이루고 한
    번 방문한 노드로 돌아가지 않으므로 반드시 끝난다. 중간에서 끊긴
    가지를 남기면 문서 본문이 도달하지도 않은 노드의 문장을 싣고, 근거
    장부가 그것을 근거라고 말하게 된다.

    완주한 간선만 장부에 남으므로 잘림만 있고 완주가 없으면 블록이
    없다. 그때 그 문서의 컴파일은 실패한다. 불완전할 수 있는 문서를
    소비 표면에 올리지 않기 위해서다.

    본문 줄은 주입받은 서식(edge_line)이 만든다. 어느 이름을 어느
    수준까지 적을지는 소비처가 정하는 일이고, 순회는 어떤 간선이
    남았는지만 안다.

    남은 간선은 step 차례로, step 안에서는 간선 id 사전순으로 담는다.
    같은 간선이 두 step에 걸쳐 다시 나오면 한 번만 담는다. 근거 장부는
    어떤 간선을 썼는지의 목록이지 몇 번 스쳤는지의 기록이 아니기
    때문이다.

    이을 노드가 없어지면 남은 step은 조회하지 않는다. step이 하나도
    없는 경로는 시작 노드 자신을 도달점으로 돌려준다.

    Raises:
        ValueError: step의 direction이 out·in·any 셋 중 하나가 아닐 때
            던진다. 모르는 direction을 임의로 해석하면 정의가 고르지
            않은 간선이 문서에 실린다.
    """
    visited = {start_node_id}
    frontier: tuple[uuid.UUID, ...] = (start_node_id,)
    truncated_steps: list[int] = []
    layers: list[tuple[_Arrival, ...]] = []

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
        arrivals: list[_Arrival] = []
        names: dict[uuid.UUID, str] = {}
        for edge in sorted(edges, key=lambda edge: str(edge.id)):
            origin, neighbor, neighbor_name = _hop_of(
                edge, step.direction, frontier_nodes
            )
            if neighbor in visited:
                continue
            names.setdefault(neighbor, neighbor_name or "")
            arrivals.append(
                _Arrival(
                    edge=edge,
                    from_node_id=origin,
                    to_node_id=neighbor,
                    relation_type=step.relation_type,
                )
            )

        ordered = sorted(names.items(), key=lambda item: (item[1], str(item[0])))
        if len(ordered) > MAX_NODES_PER_STEP:
            truncated_steps.append(index)
            ordered = ordered[:MAX_NODES_PER_STEP]
        kept = {node_id for node_id, _ in ordered}

        layers.append(
            tuple(arrival for arrival in arrivals if arrival.to_node_id in kept)
        )
        visited |= kept
        frontier = tuple(node_id for node_id, _ in ordered)

    relation_ids, edge_lines, hint_lines = _ledger_of_completed_paths(
        layers, reached=frontier, edge_line=edge_line
    )

    return PathTraversal(
        reached=frontier,
        relation_ids=tuple(relation_ids),
        edge_lines=tuple(edge_lines),
        hint_lines=tuple(hint_lines),
        truncated_steps=tuple(truncated_steps),
    )


def _ledger_of_completed_paths(
    layers: list[tuple[_Arrival, ...]],
    *,
    reached: tuple[uuid.UUID, ...],
    edge_line: EdgeFormatter,
) -> tuple[list[uuid.UUID], list[str], list[str]]:
    """완주한 경로 위의 간선만 골라 근거 장부와 본문 줄을 만든다.

    이 함수는 마지막 도달 노드에서 거꾸로 올라간다. 마지막 층에서는
    도달 노드에 닿은 간선만 살아남고, 그 간선들의 출발 노드가 한 층
    위에서 살아남는 도착 노드가 된다. 이것을 첫 층까지 되풀이하면
    중간에서 끊긴 가지가 전부 떨어져 나간다.

    도달 노드가 하나도 없으면 살아남는 간선도 없다. 어느 간선도 문서에
    실리는 노드를 만들어 내지 못했기 때문이다.

    담는 차례는 step 차례가 먼저고 step 안에서는 간선 id 사전순이다.
    같은 간선이 두 번 나오면 처음 한 번만 담는다.

    본문 줄과 힌트 줄은 간선마다 하나씩 짝으로 담는다. 문장이 없는
    간선도 빈 힌트를 채워, 두 목록의 자리가 끝까지 맞물린다.
    """
    surviving = set(reached)
    kept_layers: list[tuple[_Arrival, ...]] = []
    for arrivals in reversed(layers):
        alive = tuple(
            arrival for arrival in arrivals if arrival.to_node_id in surviving
        )
        kept_layers.append(alive)
        surviving = {arrival.from_node_id for arrival in alive}
    kept_layers.reverse()

    relation_ids: list[uuid.UUID] = []
    edge_lines: list[str] = []
    hint_lines: list[str] = []
    recorded: set[uuid.UUID] = set()
    for arrivals in kept_layers:
        for arrival in sorted(arrivals, key=lambda a: str(a.edge.id)):
            if arrival.edge.id in recorded:
                continue
            recorded.add(arrival.edge.id)
            relation_ids.append(arrival.edge.id)
            edge_lines.append(edge_line(arrival.edge, arrival.relation_type))
            hint_lines.append(arrival.edge.assertion_text or "")
    return relation_ids, edge_lines, hint_lines


def relation_section_block(
    *,
    path: RelationPath,
    traversal: PathTraversal,
    ontology_version: str | None,
) -> ArtifactBlock | None:
    """경로 하나의 순회 결과를 relation_section 블록으로 만든다.

    제목은 경로 정의만으로 정해진다. 어떤 노드에 닿았는지와 무관하므로
    같은 정의로 만든 문서는 지식이 달라도 같은 자리에 같은 제목의
    섹션을 갖고, 판 사이의 비교가 제목에서 흔들리지 않는다.

    본문은 간선마다 양끝 이름을 명시한 줄을 순회가 정한 차례 그대로
    늘어놓고, 그 간선에 원문 문장이 있으면 바로 아래 들여쓴 힌트 줄을
    하나 붙인다. 인용문만 싣던 때에는 그 말을 누가 했는지가 상대
    노드로 오해되었다. 힌트는 공백을 접어 한 줄로 적는다. 들여쓰기
    접두가 붙는 것은 첫 줄뿐이라서, 원문의 줄바꿈을 그대로 두면 둘째
    줄부터가 접두 없는 줄이 되어 소비처에서 간선 줄로 읽히기
    때문이다. 잘린 step이 있으면 step마다 한 줄씩 오름차순으로 덧붙여,
    문서가 자신이 완전하지 않음을 스스로 말하게 한다. 조용한 누락은
    읽는 사람이 "이게 전부"라고 믿게 만들기 때문이다.

    근거 장부는 relation_ids 하나뿐이다. 관계 서술의 근거는 관계에
    붙은 문장 자체이므로 claim을 가리킬 것이 없고, 근거 종류를 하나로
    못박아야 장부가 흐려지지 않는다.

    빈 블록은 만들지 않는다. 도달한 노드도 잘린 step도 없으면 할 말이
    없고, 근거로 삼을 관계가 하나도 없어도 마찬가지다. 장부가 빈
    블록은 근거 계약을 통과할 수 없기 때문이다. 반대로 도달이 없어도
    잘림이 있으면 블록을 남긴다. "여기서 끊겼다"는 사실 자체가 정보다.
    """
    if not traversal.reached and not traversal.truncated_steps:
        return None
    if not traversal.relation_ids:
        return None

    lines: list[str] = []
    for line, hint in zip(traversal.edge_lines, traversal.hint_lines, strict=True):
        lines.append(line)
        one_line_hint = _one_line(hint)
        if one_line_hint:
            lines.append(f"{RELATION_HINT_PREFIX}{one_line_hint}")
    for step_index in sorted(traversal.truncated_steps):
        lines.append(
            f"(step {step_index}에서 이웃 {MAX_NODES_PER_STEP}개"
            " 상한 초과 — 일부만 따라감)"
        )

    return ArtifactBlock(
        block_kind=BLOCK_KIND_RELATION_SECTION,
        heading=" → ".join(
            f"{step.relation_type}({step.direction})" for step in path.steps
        ),
        body="\n".join(lines),
        claim_ids=(),
        proposal_ids=(),
        ontology_version=ontology_version,
        sources=(),
        relation_ids=traversal.relation_ids,
    )


def _hop_of(
    edge: StoredRelationEdge,
    direction: str,
    frontier_nodes: set[uuid.UUID],
) -> tuple[uuid.UUID, uuid.UUID, str | None]:
    """간선을 이 step의 출발점·이웃·이웃 이름으로 읽는다.

    direction이 out이면 도착 쪽이, in이면 출발 쪽이 이웃이다. any는 어느
    쪽이 frontier에 걸렸는지 모르므로, 출발 쪽이 frontier면 도착 쪽을
    이웃으로 보고 아니면 출발 쪽을 이웃으로 본다. 양 끝이 모두 frontier인
    간선은 어느 쪽을 골라도 이미 방문한 노드라 순회에서 걸러진다.

    출발점을 함께 돌려주는 것은 완주 여부를 거꾸로 되짚기 위해서다.
    간선만 들고 있으면 direction마다 어느 끝이 이 step의 출발이었는지를
    다시 따져야 한다.

    Raises:
        ValueError: direction이 규약 밖일 때 던진다.
    """
    if direction == DIRECTION_OUT:
        return (
            edge.source_node_id,
            edge.target_node_id,
            edge.target_display_name,
        )
    if direction == DIRECTION_IN:
        return (
            edge.target_node_id,
            edge.source_node_id,
            edge.source_display_name,
        )
    if direction == DIRECTION_ANY:
        if edge.source_node_id in frontier_nodes:
            return (
                edge.source_node_id,
                edge.target_node_id,
                edge.target_display_name,
            )
        return (
            edge.target_node_id,
            edge.source_node_id,
            edge.source_display_name,
        )
    raise ValueError(f"알 수 없는 관계 방향이다: {direction!r}")
