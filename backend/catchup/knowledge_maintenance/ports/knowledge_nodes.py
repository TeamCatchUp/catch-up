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
