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

    def create_entity_node(
        self,
        *,
        workspace_id: int,
        entity_type: str,
        canonical_key: str,
        display_name: str,
    ) -> KnowledgeNode:
        """canonical entity 노드를 발급한다."""
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
