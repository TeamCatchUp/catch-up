from __future__ import annotations

import uuid
from typing import Protocol

from catchup.knowledge_maintenance.domain.knowledge_node import KnowledgeNode
from catchup.knowledge_maintenance.domain.knowledge_node import NodeKind


class KnowledgeNodeRepository(Protocol):
    """graph node identity의 영속성 기능을 정의한다."""

    def get_for_resource(
        self,
        *,
        workspace_id: int,
        node_kind: NodeKind,
        resource_id: uuid.UUID,
    ) -> KnowledgeNode | None: ...

    def get_entity_by_canonical_key(
        self,
        *,
        workspace_id: int,
        canonical_key: str,
    ) -> KnowledgeNode | None:
        """canonical key로 entity 노드를 찾는다."""
        ...

    def find_entity_by_normalized_alias(
        self,
        *,
        workspace_id: int,
        normalized_alias: str,
    ) -> KnowledgeNode | None:
        """정규화된 alias 정확 일치로 entity 노드를 찾는다.

        alias는 identity가 아니라 단서이므로 같은 alias가 여러 노드에
        걸릴 수 있다. 그때는 node id 순 첫 번째 하나만 돌려준다 —
        같은 질의가 같은 답을 주어야 하기 때문이다. 못 찾으면 None이다.
        """
        ...

    def get_entity_by_id(
        self,
        *,
        workspace_id: int,
        node_id: uuid.UUID,
    ) -> KnowledgeNode | None:
        """node id로 entity 노드를 그대로 찾는다.

        이름을 거치지 않는 유일한 조회다. 이미 identity를 손에 쥔
        호출자가 그것을 이름으로 되돌렸다가 다시 푸는 일을 막는다 —
        같은 이름이 여러 노드에 걸릴 수 있어 그 왕복은 다른 노드로
        착지할 수 있기 때문이다.

        lifecycle은 거르지 않고 찾은 그대로 돌려준다. 살아 있는 노드만
        쓸지는 읽기 경로마다 다른 판단이라 저장소가 미리 정하지 않는다.
        entity가 아니거나 없으면 None이다.
        """
        ...

    def find_entity_candidates_by_similarity(
        self,
        *,
        workspace_id: int,
        normalized_query: str,
        threshold: float,
        limit: int,
    ) -> list[tuple[KnowledgeNode, float]]:
        """이름이 비슷한 active entity 노드를 점수와 함께 찾는다.

        정확 일치가 실패했을 때 쓰는 fallback이다. alias 하나하나에
        bigram 유사도를 매기고 노드마다 가장 높은 점수만 남긴다 —
        alias가 많은 노드가 상위 후보를 독차지하지 않게 하기 위해서다.

        threshold 이상인 것만, 점수 내림차순·node id 오름차순으로 최대
        limit개를 준다. 흡수된(merged) 노드는 후보가 아니다.
        """
        ...

    def create_entity_node(
        self,
        *,
        workspace_id: int,
        entity_type: str,
        canonical_key: str | None,
        display_name: str,
    ) -> KnowledgeNode:
        """canonical entity 노드를 발급한다.

        외부 ID가 있는 결정론 경로는 canonical_key를 채우고, 사람이
        승인한 병합처럼 외부 키가 없는 entity는 None으로 만든다.
        """
        ...

    def add_alias(
        self,
        *,
        workspace_id: int,
        node_id: uuid.UUID,
        alias: str,
        normalized_alias: str,
        source: str,
    ) -> None:
        """노드에 이름 단서를 남긴다. 같은 정규화 alias면 넘어간다."""
        ...

    def ensure_for_resource(
        self,
        *,
        workspace_id: int,
        node_kind: NodeKind,
        resource_id: uuid.UUID,
        display_name: str | None = None,
    ) -> KnowledgeNode:
        """record 하나에 대응하는 node를 만들거나 이미 있는 것을 돌려준다.

        수집과 정규화는 같은 record를 여러 번 볼 수 있으므로 두 번째부터는
        새 node를 만들지 않아야 한다. 그렇지 않으면 같은 원문이 graph에서
        서로 다른 대상으로 보인다.
        """
        ...
