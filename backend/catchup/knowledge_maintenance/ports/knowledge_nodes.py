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
