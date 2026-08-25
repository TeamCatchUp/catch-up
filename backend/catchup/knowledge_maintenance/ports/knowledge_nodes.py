from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from catchup.knowledge_maintenance.domain.knowledge_node import KnowledgeNode
from catchup.knowledge_maintenance.domain.knowledge_node import NodeKind
from catchup.knowledge_maintenance.domain.source_version import JsonValue


@dataclass(frozen=True, slots=True)
class ActiveEntityAlias:
    """살아 있는 entity 노드가 지금 들고 있는 이름 하나를 담는다.

    Attributes:
        node_id: 이 이름을 가진 노드를 가리킨다.
        entity_type: 노드의 entity 종류를 나타낸다. 종류가 다르면 비교하지
            않으므로 이름과 함께 와야 한다.
        alias: 사람이 읽는 이름 그대로다.
        normalized_alias: 비교에 쓰는 정규화 이름이다.
    """

    node_id: uuid.UUID
    entity_type: str
    alias: str
    normalized_alias: str


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
        entity_type: str | None = None,
    ) -> KnowledgeNode | None:
        """정규화된 alias 정확 일치로 entity 노드를 찾는다.

        alias는 identity가 아니라 단서이므로 같은 alias가 여러 노드에
        걸릴 수 있다. 그때는 node id 순 첫 번째 하나만 돌려준다 —
        같은 질의가 같은 답을 주어야 하기 때문이다. 못 찾으면 None이다.

        entity_type을 주면 그 type의 노드만 후보로 본다. 걸러내기를
        호출자가 아니라 조회가 해야 하는 이유는, 1건만 돌려주는 조회에서
        type을 나중에 보면 다른 type 노드가 id 순으로 앞설 때 정작 맞는
        노드가 영영 보이지 않기 때문이다.
        """
        ...

    def list_active_entity_aliases(
        self,
        *,
        workspace_id: int,
    ) -> list[ActiveEntityAlias]:
        """살아 있는 entity 노드의 이름을 모두 모은다.

        해소가 이름 유사도로 판정 블록을 만들 때 쓴다. 이번 라운드 후보만
        서로 견주면 라운드를 넘어 갈라진 노드들과는 영영 만나지 못하므로,
        이미 서 있는 노드의 이름도 같은 판정대에 올린다.

        노드 하나가 여러 이름을 들고 있으면 그 수만큼 돌려준다. 어느
        표기가 후보와 닮았는지는 부르는 쪽이 견줘 봐야 알 수 있기
        때문이다. 흡수·퇴역한 노드는 빼고, node id·정규화 이름 순으로
        정렬해 같은 질의가 같은 순서를 주게 한다.
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

    def lock_entity_node(
        self,
        *,
        workspace_id: int,
        node_id: uuid.UUID,
    ) -> KnowledgeNode | None:
        """노드 행을 이 트랜잭션이 끝날 때까지 잠그고 현재 값을 준다.

        후보를 붙이는 mark_entity_resolved와 노드를 물리는
        retire_entity_node가 같은 행을 잠그므로, 먼저 잠근 쪽이 끝날 때까지
        나머지는 기다린다. 되돌림이 노드 상태를 견주기 전에 부른다.
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
        attributes: Mapping[str, JsonValue] | None = None,
    ) -> KnowledgeNode:
        """canonical entity 노드를 발급한다.

        외부 ID가 있는 결정론 경로는 canonical_key를 채우고, 사람이
        승인한 병합처럼 외부 키가 없는 entity는 None으로 만든다.

        attributes는 노드가 만들어지는 순간부터 들고 있어야 하는 부가
        정보다. 발급 후 따로 갱신하지 않고 여기서 함께 넣는 이유는,
        attributes로 노드를 찾는 조회가 있어 빈 채로 남은 짧은 순간에도
        같은 대상이 다른 노드로 한 번 더 발급될 수 있기 때문이다.
        """
        ...

    def find_entity_by_actor_key(
        self,
        *,
        workspace_id: int,
        entity_type: str,
        key_kind: str,
        value: str,
    ) -> KnowledgeNode | None:
        """행위자 키로 active entity 노드를 찾는다.

        canonical_key 하나로는 같은 사람을 못 묶는다. 외부 소스는 한
        사람에게 세션마다 다른 external_key를 주므로, 나중에 온 후보의
        canonical_key가 이미 만들어진 노드의 것과 달라지기 때문이다.
        그래서 노드는 지금까지 본 이메일·external_key를
        attributes[ACTOR_ATTRIBUTE] 아래 목록으로 쌓아 두고, 조회는 그
        목록에 값이 들어 있는지를 본다.

        key_kind는 "emails" 또는 "external_keys"다. 흡수·퇴역한 노드는
        후보가 아니다. 둘 이상이 걸리면 created_at·id 순 첫 번째
        하나만 준다 — 같은 질의가 같은 답을 주어야 하기 때문이다.
        못 찾으면 None이다.
        """
        ...

    def set_entity_attributes(
        self,
        *,
        workspace_id: int,
        node_id: uuid.UUID,
        attributes: Mapping[str, JsonValue],
    ) -> KnowledgeNode:
        """노드의 attributes를 통째로 바꾸고 갱신된 노드를 돌려준다.

        키 단위로 합치지 않는다. 무엇을 남기고 무엇을 덮을지는 도메인
        규칙이라 호출자가 이미 합친 결과를 넘기고, 저장소는 그 결과를
        그대로 적는다.
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
    ) -> bool:
        """노드에 이름 단서를 남긴다. 같은 정규화 alias면 넘어간다.

        Returns:
            이번 호출이 행을 새로 넣었으면 참, 같은 정규화 alias가 이미
            있어 넘어갔으면 거짓을 준다. 부르는 쪽이 "이 이름은 내가
            붙였다"를 저널에 적을 때 이 값으로 가른다. 시도만 보고 적으면
            같은 이름의 두 번째 병합이 앞 병합의 alias를 자기 것으로
            적고, 그 되돌림이 남의 이름을 지운다.
        """
        ...

    def remove_alias(
        self,
        *,
        workspace_id: int,
        node_id: uuid.UUID,
        normalized_alias: str,
    ) -> None:
        """확정이 남긴 이름 단서 하나를 노드에서 거둔다.

        되돌림이 쓴다. 같은 표기가 다른 관찰에서 따로 붙어 있을 수 있어
        정규화 이름만으로 지우면 되돌림과 무관한 단서까지 함께 사라진다.
        그래서 확정이 남긴 표시(source가 "system")가 붙은 행만 지운다.
        지울 행이 없으면 아무것도 하지 않는다.
        """
        ...

    def retire_entity_node(
        self,
        *,
        workspace_id: int,
        node_id: uuid.UUID,
    ) -> bool:
        """가리키는 후보가 없는 entity 노드를 퇴역 상태로 물린다.

        되돌림이 쓴다. 확정이 세운 노드에서 후보가 전부 떠나면 그 노드는
        가리키는 것이 없는 빈 자리로 남는데, 지우지는 않는다. 저널과 지난
        기록이 그 노드를 계속 가리키기 때문이다. 대신 lifecycle을 물려
        살아 있는 노드를 보는 경로에서 빠지게 한다.

        남은 후보가 있는지는 이 호출 안에서 확인한다. 부르는 쪽이 먼저
        세어 보고 그 뒤에 물리면, 세는 시점과 물리는 시점 사이에 다른
        트랜잭션이 같은 노드로 후보를 붙일 수 있고 그 후보는 퇴역한 노드를
        가리키게 된다. 구현은 노드 행을 잠근 뒤 확인해서 후보를 붙이는
        경로와 순서를 맞춘다.

        Returns:
            퇴역시켰으면 참, 아직 이 노드를 가리키는 후보가 있어 그대로
            두었으면 거짓을 준다. 이미 퇴역한 노드는 참이다.

        Raises:
            ValueError: 노드가 없을 때 던진다.
        """
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
