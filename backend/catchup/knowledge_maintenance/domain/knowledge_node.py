from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from datetime import timezone
from enum import StrEnum
from types import MappingProxyType

from catchup.knowledge_maintenance.domain.source_version import JsonValue


class NodeKind(StrEnum):
    """graph에서 주소를 갖는 대상의 종류를 나타낸다."""

    SOURCE_VERSION = "source_version"
    OBSERVATION = "observation"
    ENTITY = "entity"
    CLAIM = "claim"
    RELATION_ASSERTION = "relation_assertion"
    ARTIFACT = "artifact"
    ARTIFACT_REVISION = "artifact_revision"
    REVIEW_DECISION = "review_decision"
    EDITORIAL_OVERRIDE = "editorial_override"


class NodeLifecycleState(StrEnum):
    ACTIVE = "active"
    MERGED = "merged"
    RETIRED = "retired"


@dataclass(frozen=True, slots=True)
class ResourceRef:
    """자기 테이블을 이미 가진 record를 가리킨다.

    SourceVersion과 Observation처럼 본문이 다른 곳에 저장된 대상을 graph
    공간에 올릴 때 쓴다. `resource_type`은 대응하는 `NodeKind`의 값과 같다.

    Attributes:
        resource_type: 어떤 종류의 record인지 나타낸다.
        resource_id: 그 record의 식별자를 문자열로 보존한다.
    """

    resource_type: str
    resource_id: str

    def __post_init__(self) -> None:
        for field_name in ("resource_type", "resource_id"):
            value = getattr(self, field_name).strip()
            if not value:
                raise ValueError(f"{field_name} must not be blank")
            object.__setattr__(self, field_name, value)


@dataclass(frozen=True, slots=True)
class KnowledgeNode:
    """graph에서 주소를 갖는 대상 하나를 표현한다.

    본문을 담지 않는다. 이 타입이 하는 일은 "이것이 graph에서 누구인가"를
    말하는 것뿐이며, 내용은 각자의 테이블에 있다.

    Attributes:
        id: node 하나를 식별한다.
        workspace_id: node가 속한 CatchUp workspace를 식별한다.
        node_kind: 어떤 종류의 대상인지 나타낸다.
        resource: 자기 테이블을 가진 record를 가리킬 때 그 참조를 담는다.
        entity_type: 자기 테이블이 없는 Entity의 종류를 나타낸다.
        canonical_key: 같은 대상을 하나로 모으는 키를 나타낸다.
        display_name: 사람이 대상을 알아볼 이름을 나타낸다.
        lifecycle_state: node가 살아 있는지 병합·퇴역했는지 나타낸다.
        merged_into_node_id: 병합된 경우 흡수한 node를 가리킨다.
        attributes: 부가 정보를 JSON 호환 형태로 보존한다.
        created_at: CatchUp이 node를 만든 시각을 나타낸다.
    """

    id: uuid.UUID
    workspace_id: int
    node_kind: NodeKind
    resource: ResourceRef | None = None
    entity_type: str | None = None
    canonical_key: str | None = None
    display_name: str | None = None
    lifecycle_state: NodeLifecycleState = NodeLifecycleState.ACTIVE
    merged_into_node_id: uuid.UUID | None = None
    attributes: Mapping[str, JsonValue] = field(default_factory=dict)
    created_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.workspace_id <= 0:
            raise ValueError("workspace_id must be greater than 0")

        is_merged = self.lifecycle_state == NodeLifecycleState.MERGED
        if is_merged and self.merged_into_node_id is None:
            raise ValueError("merged node must point at the node it merged into")
        if not is_merged and self.merged_into_node_id is not None:
            raise ValueError("only a merged node may point at another node")

        if self.resource is not None:
            if self.resource.resource_type != self.node_kind.value:
                raise ValueError(
                    "resource_type must match node_kind: "
                    f"{self.resource.resource_type} != {self.node_kind.value}"
                )

        if self.created_at is not None:
            if self.created_at.tzinfo is None:
                raise ValueError("created_at must include timezone information")
            object.__setattr__(
                self,
                "created_at",
                self.created_at.astimezone(timezone.utc),
            )

        object.__setattr__(
            self,
            "attributes",
            MappingProxyType(dict(self.attributes)),
        )


def resource_ref_for(node_kind: NodeKind, resource_id: uuid.UUID) -> ResourceRef:
    """record 하나를 가리키는 참조를 만든다."""
    return ResourceRef(
        resource_type=node_kind.value,
        resource_id=str(resource_id),
    )
