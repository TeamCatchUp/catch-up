"""어떤 대상에 대해 특정 시점에 참이었던 claim을 읽는다.

대상은 검색이 아니라 정확 매칭으로만 찾는다. canonical key가 먼저이고,
없으면 정규화한 alias가 다음이다. canonical key는 identity 그 자체지만
alias는 단서일 뿐이라, 둘이 같은 입력에 걸리면 identity가 이겨야
하기 때문이다. 유사도 검색은 여기에 없다 — 읽기 경로가 어떤 노드를
답했는지 재현 가능해야 하고, 근사 매칭은 그 성질을 깨뜨린다.

시점 판정은 이 서비스가 하지 않는다. 구간 규칙의 정의처는
`domain.temporal.claim_valid_at`이고 reader의 SQL이 같은 규칙을
집행한다. 이 서비스가 하는 일은 시각을 한 번 고정해 두 조회가 같은
`at`을 보게 만드는 것뿐이다.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from datetime import timezone
from types import TracebackType
from typing import Protocol
from typing import Self

from catchup.knowledge_maintenance.domain.entity_resolution import normalize_name
from catchup.knowledge_maintenance.domain.knowledge_node import KnowledgeNode
from catchup.knowledge_maintenance.ports.knowledge_candidates import AsOfClaim
from catchup.knowledge_maintenance.ports.knowledge_candidates import (
    KnowledgeCandidateRepository,
)
from catchup.knowledge_maintenance.ports.knowledge_nodes import KnowledgeNodeRepository
from catchup.observability.logging import get_logger

logger = get_logger(__name__)

MATCHED_BY_CANONICAL_KEY = "canonical_key"
MATCHED_BY_ALIAS = "alias"


class KnowledgeReadUnitOfWork(Protocol):
    """as-of 조회가 쓰는 읽기 전용 transaction 경계를 정의한다.

    commit을 요구하지 않는다. 이 경로는 아무것도 쓰지 않기 때문이다.
    """

    knowledge_nodes: KnowledgeNodeRepository
    knowledge_candidates: KnowledgeCandidateRepository

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class MatchedSubject:
    """조회 입력이 어느 노드로, 어떻게 걸렸는지 표현한다.

    Attributes:
        node_id: 매칭된 entity 노드를 식별한다.
        entity_type: 그 노드의 entity 종류를 나타낸다.
        display_name: 사람이 알아볼 이름을 나타낸다.
        matched_by: canonical_key인지 alias인지 나타낸다.
    """

    node_id: uuid.UUID
    entity_type: str
    display_name: str | None
    matched_by: str


@dataclass(frozen=True, slots=True)
class AsOfQueryResult:
    """as-of 조회 한 번의 결과를 표현한다.

    Attributes:
        subject: 매칭된 대상을 담고, 못 찾으면 None이다.
        as_of: 판정 기준으로 실제 쓴 시각을 나타낸다.
        claims: 그 시점에 참이었던 accepted claim을 담는다.
    """

    subject: MatchedSubject | None
    as_of: datetime
    claims: tuple[AsOfClaim, ...]


def query_claims_as_of(
    *,
    workspace_id: int,
    subject: str,
    at: datetime | None = None,
    predicate: str | None = None,
    uow: KnowledgeReadUnitOfWork,
) -> AsOfQueryResult:
    """subject가 at 시점에 갖고 있던 claim을 읽는다.

    at을 주지 않으면 현재 시각을 한 번만 읽어 고정한다. 조회 도중
    시각을 두 번 읽으면 결과와 그 결과를 만든 기준이 어긋날 수 있기
    때문이다. at은 timezone을 포함해야 한다.
    """
    if at is not None and at.tzinfo is None:
        raise ValueError("at must include timezone information")
    as_of = datetime.now(timezone.utc) if at is None else at

    with uow:
        node, matched_by = _match_subject(
            workspace_id=workspace_id,
            subject=subject,
            uow=uow,
        )
        if node is None:
            claims: tuple[AsOfClaim, ...] = ()
            matched = None
        else:
            claims = uow.knowledge_candidates.find_accepted_claims_as_of(
                workspace_id=workspace_id,
                subject_node_id=node.id,
                at=as_of,
                predicate=predicate,
            )
            matched = MatchedSubject(
                node_id=node.id,
                # node 타입은 entity가 아닌 종류까지 담느라 entity_type을
                # optional로 두지만, 여기 오는 노드는 entity 조회의
                # 결과뿐이라 빈 문자열은 실제로 나오지 않는다.
                entity_type=node.entity_type or "",
                display_name=node.display_name,
                matched_by=matched_by,
            )

    logger.info(
        "knowledge_as_of_queried",
        workspace_id=workspace_id,
        subject=subject,
        matched_by=matched.matched_by if matched else None,
        matched_node_id=str(matched.node_id) if matched else None,
        as_of=as_of.isoformat(),
        predicate=predicate,
        claim_count=len(claims),
    )
    return AsOfQueryResult(subject=matched, as_of=as_of, claims=claims)


def _match_subject(
    *,
    workspace_id: int,
    subject: str,
    uow: KnowledgeReadUnitOfWork,
) -> tuple[KnowledgeNode | None, str]:
    """입력 문자열을 entity 노드 하나로 정확 매칭한다."""
    node = uow.knowledge_nodes.get_entity_by_canonical_key(
        workspace_id=workspace_id,
        canonical_key=subject,
    )
    if node is not None:
        return node, MATCHED_BY_CANONICAL_KEY

    node = uow.knowledge_nodes.find_entity_by_normalized_alias(
        workspace_id=workspace_id,
        normalized_alias=normalize_name(subject),
    )
    if node is not None:
        return node, MATCHED_BY_ALIAS

    return None, ""
