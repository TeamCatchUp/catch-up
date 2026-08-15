"""관계 간선을 읽는 포트를 정의한다.

정의가 고른 노드에서 관계를 한 걸음 따라가는 자리다. 경로 순회는 이
한 걸음을 되풀이해 만들어지므로, 한 걸음의 계약을 따로 못 박아 둔다.
쓰기는 여기에 없다 — 컴파일은 관계를 읽기만 한다.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True, slots=True)
class StoredRelationEdge:
    """살아 있는 관계 간선 하나를 순회가 쓸 수 있는 형태로 담는다.

    Attributes:
        id: 관계 주장 후보 행을 가리킨다. 근거 장부가 이 식별자로
            간선의 출처를 되짚는다.
        source_node_id: 관계의 출발 쪽 canonical 노드를 가리킨다.
            후보를 거쳐 들어온 끝점도 해소된 노드로 바뀌어 담긴다 —
            순회 다음 걸음이 노드 식별자만 쓰기 때문이다.
        target_node_id: 관계의 도착 쪽 canonical 노드를 가리킨다.
        assertion_text: 관계를 사람 말로 적은 문장을 담는다. 추출이
            문장을 남기지 않은 관계도 있으므로 비어 있을 수 있다.
        source_display_name: 출발 쪽 노드의 표시 이름을 담는다. 순회가
            이웃을 이름 차례로 세우려면 식별자만으로는 모자라기
            때문이다. 이름이 비어 있는 노드도 있으므로 None일 수 있다.
        target_display_name: 도착 쪽 노드의 표시 이름을 담는다.
    """

    id: uuid.UUID
    source_node_id: uuid.UUID
    target_node_id: uuid.UUID
    assertion_text: str | None
    source_display_name: str | None
    target_display_name: str | None


class RelationRepository(Protocol):
    """관계 간선을 읽는 기능을 정의한다.

    workspace 범위는 저장소를 만들 때 정해진다. 문서 저장소와 정의
    저장소와 같은 관례다 — 메서드마다 workspace를 다시 넘기게 하면
    호출자가 그것을 틀릴 자리가 생기기 때문이다.
    """

    def find_edges(
        self,
        *,
        node_ids: Sequence[uuid.UUID],
        relation_type: str,
        direction: str,
        now: datetime,
    ) -> list[StoredRelationEdge]:
        """주어진 노드에 걸린 살아 있는 관계 간선을 읽는다.

        relation_type은 정확히 일치해야 한다. 상위 개념으로 넓히면
        정의가 고른 관계가 아닌 간선이 문서에 실린다.

        살아 있는 관계만 본다. 판정은 claim의 live-only 기본과 같은
        함수(domain.temporal.claim_not_closed_at)를 쓴다 — 같은 시간축
        위의 두 종류가 서로 다른 시점 판정을 쓰면 문서 안에서 닫힌
        관계와 살아 있는 주장이 뒤섞인다.

        반려된 관계와 재추출이 대체한 관계는 빠진다. claim 조회의 기본과
        같은 기준이다 — 반려는 참이었던 적이 없다는 판정이고, 대체된 구
        배치는 새 배치와 함께 실리면 같은 관계를 두 번 싣는다. 아직
        판정 전인 관계는 그대로 나온다.

        양 끝이 canonical 노드로 해소된 행만 나온다. 아직 해소되지 않은
        끝점은 어느 노드를 가리키는지 정해지지 않았으므로, 순회가 그것을
        다음 걸음의 출발점으로 삼을 수 없다.

        방향은 out이면 출발 쪽이, in이면 도착 쪽이 node_ids에 든 간선을
        고른다. any는 그 둘의 합집합이다.

        차례는 관계 주장 식별자 사전순이다. 같은 지식 상태에서 두 번
        물으면 같은 목록이 나와야 문서 본문이 흔들리지 않는다.

        양 끝점의 표시 이름을 함께 돌려준다. 순회가 이웃을 이름 차례로
        세우고 상한을 자르므로, 이름을 뒤늦게 따로 물으면 걸음마다
        왕복이 한 번씩 더 늘고 그 사이 상태가 바뀔 자리가 생긴다.
        """
        ...
