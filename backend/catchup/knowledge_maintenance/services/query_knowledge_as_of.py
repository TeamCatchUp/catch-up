"""어떤 대상에 대해 특정 시점에 참이었던 claim을 읽는다.

대상은 검색이 아니라 정확 매칭으로만 찾는다. canonical key가 먼저이고,
없으면 정규화한 alias가 다음이다. canonical key는 identity 그 자체지만
alias는 단서일 뿐이라, 둘이 같은 입력에 걸리면 identity가 이겨야
하기 때문이다. 정확 매칭이 모두 빗나가면 이름이 비슷한 노드를
후보로 함께 돌려주지만, 유사도는 후보 제시까지만 한다 — 확정은
소비자 몫이라 이 서비스가 답한 노드는 여전히 정확 매칭의 결과뿐이고
재현성은 그대로다.

후보 중 하나를 고른 소비자를 위해 node id로 바로 읽는 경로도 함께
연다(`query_claims_of_node`). 이름을 거치지 않으므로 근사 매칭이
아니고, 오히려 정확 매칭보다 더 좁다 — 해소할 것이 없기 때문이다.
후보의 이름을 다시 넣어 조회하는 왕복이 훨씬 위험하다. 같은 정규화
alias가 여러 노드에 걸릴 수 있어 고른 노드가 아닌 다른 노드에
착지할 수 있다.

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
from catchup.knowledge_maintenance.domain.knowledge_node import NodeLifecycleState
from catchup.knowledge_maintenance.ports.knowledge_candidates import AsOfClaim
from catchup.knowledge_maintenance.ports.knowledge_candidates import (
    KnowledgeCandidateRepository,
)
from catchup.knowledge_maintenance.ports.knowledge_nodes import KnowledgeNodeRepository
from catchup.observability.logging import get_logger

logger = get_logger(__name__)

MATCHED_BY_CANONICAL_KEY = "canonical_key"
MATCHED_BY_ALIAS = "alias"
MATCHED_BY_NODE_ID = "node_id"

# 정확 매칭이 빗나갔을 때만 쓰는 후보 조회 기준이다. 문턱값을 낮게
# 두는 이유는 오타나 부분 표기가 대개 낮은 점수로 떨어지기 때문이고,
# 후보 수를 다섯으로 묶는 이유는 사람이 한눈에 고를 수 있는 양이기
# 때문이다. 둘 다 매칭 기준이 아니라 제시 기준이다.
SIMILARITY_THRESHOLD = 0.1
SIMILARITY_CANDIDATE_LIMIT = 5


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
        matched_by: canonical_key인지 alias인지 나타내고, 이름을 거치지
            않고 node id로 바로 읽었으면 node_id다.
    """

    node_id: uuid.UUID
    entity_type: str
    display_name: str | None
    matched_by: str


@dataclass(frozen=True, slots=True)
class SubjectCandidate:
    """정확 매칭이 빗나갔을 때 함께 제시하는 유사 후보를 표현한다.

    MatchedSubject와 달리 "이 노드가 답이다"라는 뜻이 아니다.
    matched_by가 없는 것도 그래서다 — 어떤 방식으로도 매칭되지
    않았기 때문이다.

    Attributes:
        node_id: 후보 entity 노드를 식별한다.
        display_name: 사람이 알아볼 이름을 나타낸다.
        entity_type: 그 노드의 entity 종류를 나타낸다.
        score: 이름 유사도 점수를 나타낸다. 순위를 매기는 용도이고
            절대값의 의미는 구현에 달려 있다.
    """

    node_id: uuid.UUID
    display_name: str | None
    entity_type: str | None
    score: float


@dataclass(frozen=True, slots=True)
class AsOfQueryResult:
    """as-of 조회 한 번의 결과를 표현한다.

    Attributes:
        subject: 매칭된 대상을 담고, 못 찾으면 None이다.
        as_of: 판정 기준으로 실제 쓴 시각을 나타낸다. history 조회에서는
            거르지 않고 조회한 시각을 기록만 한다.
        claims: 그 시점에 참이었던 accepted claim을 담는다. history
            조회에서는 닫힌 accepted까지 함께 담는다.
        similar_candidates: 정확 매칭이 빗나갔을 때만 채운다. 매칭에
            성공하면 언제나 비어 있다 — 답이 정해진 자리에 근사
            후보를 섞으면 소비자가 둘을 구별할 수 없기 때문이다.
    """

    subject: MatchedSubject | None
    as_of: datetime
    claims: tuple[AsOfClaim, ...]
    similar_candidates: tuple[SubjectCandidate, ...] = ()


def query_claims_as_of(
    *,
    workspace_id: int,
    subject: str,
    at: datetime | None = None,
    predicate: str | None = None,
    include_similar: bool = True,
    uow: KnowledgeReadUnitOfWork,
) -> AsOfQueryResult:
    """subject가 at 시점에 갖고 있던 claim을 읽는다.

    at을 주지 않으면 현재 시각을 한 번만 읽어 고정한다. 조회 도중
    시각을 두 번 읽으면 결과와 그 결과를 만든 기준이 어긋날 수 있기
    때문이다. at은 timezone을 포함해야 한다.

    `include_similar`를 끄면 정확 매칭이 빗나가도 유사 후보를 조회하지
    않는다. 후보를 쓰지 않을 호출자에게는 그 조회가 workspace의 모든
    alias를 훑는 순수한 낭비이고, 되짚기가 점수를 얼마나 움직였는지
    재려면 그 비용까지 빠진 기준선이 필요하기 때문이다.
    """
    if at is not None and at.tzinfo is None:
        raise ValueError("at must include timezone information")
    as_of = datetime.now(timezone.utc) if at is None else at

    with uow:
        node, matched_by = _resolve_subject(
            workspace_id=workspace_id,
            subject=subject,
            uow=uow,
        )
        if node is None:
            claims: tuple[AsOfClaim, ...] = ()
            matched = None
            similar = (
                _find_similar_candidates(
                    workspace_id=workspace_id,
                    subject=subject,
                    uow=uow,
                )
                if include_similar
                else ()
            )
        else:
            similar = ()
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
        similar_candidate_count=len(similar),
        top_similarity_score=similar[0].score if similar else None,
    )
    return AsOfQueryResult(
        subject=matched,
        as_of=as_of,
        claims=claims,
        similar_candidates=similar,
    )


def query_claims_history(
    *,
    workspace_id: int,
    subject: str,
    predicate: str | None = None,
    include_similar: bool = True,
    uow: KnowledgeReadUnitOfWork,
) -> AsOfQueryResult:
    """subject에 대해 accepted였던 claim을 시점 제한 없이 읽는다.

    as-of 조회가 "지금 무엇이 참인가"라면 이쪽은 "무엇이 참이었던
    적 있는가"다. 닫힌 accepted가 함께 나오므로 valid_from·valid_to를
    이어 붙이면 "언제 바뀌었는지"를 되짚을 수 있다. rejected는
    as-of와 똑같이 뺀다 — 한 번도 참이었던 적이 없기 때문이다.

    결과의 `as_of`는 조회한 시각을 그대로 담을 뿐, 어떤 행도 거르지
    않는다. as-of 조회와 결과 모양을 맞춰 소비자가 두 경로를 같은
    코드로 다루게 하려는 것이고, 시점 필터가 아니다.

    `include_similar`의 뜻은 `query_claims_as_of`와 같다. 끄면 miss여도
    유사 후보를 조회하지 않는다.
    """
    queried_at = datetime.now(timezone.utc)

    with uow:
        node, matched_by = _resolve_subject(
            workspace_id=workspace_id,
            subject=subject,
            uow=uow,
        )
        if node is None:
            claims: tuple[AsOfClaim, ...] = ()
            matched = None
            similar = (
                _find_similar_candidates(
                    workspace_id=workspace_id,
                    subject=subject,
                    uow=uow,
                )
                if include_similar
                else ()
            )
        else:
            similar = ()
            claims = uow.knowledge_candidates.find_accepted_claims_history(
                workspace_id=workspace_id,
                subject_node_id=node.id,
                predicate=predicate,
            )
            matched = MatchedSubject(
                node_id=node.id,
                entity_type=node.entity_type or "",
                display_name=node.display_name,
                matched_by=matched_by,
            )

    logger.info(
        "knowledge_history_queried",
        workspace_id=workspace_id,
        subject=subject,
        matched_by=matched.matched_by if matched else None,
        matched_node_id=str(matched.node_id) if matched else None,
        queried_at=queried_at.isoformat(),
        predicate=predicate,
        claim_count=len(claims),
        similar_candidate_count=len(similar),
        top_similarity_score=similar[0].score if similar else None,
    )
    return AsOfQueryResult(
        subject=matched,
        as_of=queried_at,
        claims=claims,
        similar_candidates=similar,
    )


def query_claims_of_node(
    *,
    workspace_id: int,
    node_id: uuid.UUID,
    at: datetime | None = None,
    predicate: str | None = None,
    uow: KnowledgeReadUnitOfWork,
) -> AsOfQueryResult:
    """node id로 지목한 노드가 at 시점에 갖고 있던 claim을 읽는다.

    `query_claims_as_of`와 읽는 규칙은 완전히 같고 대상을 정하는 방법만
    다르다. 이름을 해소하지 않고 받은 identity를 그대로 쓴다. 그래서
    `matched_by`는 `node_id`이고, 이 값은 "어떻게 찾았는지"가 아니라
    "찾을 필요가 없었다"는 뜻이다.

    이것이 정확 매칭 재현성 원칙과 어긋나지 않는 이유는, 그 원칙이
    금지하는 것이 근사 매칭으로 대상을 확정하는 일이기 때문이다. node
    id는 근사의 반대편 끝이다 — 같은 id는 언제나 같은 노드 하나다.
    유사 후보를 고른 소비자도 이 경로로 읽어야 한다. 후보의 이름을
    다시 넣으면 같은 alias를 가진 다른 노드로 착지할 수 있다.

    유사 후보는 어떤 경우에도 채우지 않는다. 대상을 이미 지목한
    조회라 "비슷한 것"을 함께 줄 자리가 없다.

    노드가 없거나 entity가 아니거나 active가 아니면 subject 없는 빈
    결과다. merged·retired 노드의 claim을 답의 근거로 실으면 이미
    접힌 identity가 되살아난다.
    """
    if at is not None and at.tzinfo is None:
        raise ValueError("at must include timezone information")
    as_of = datetime.now(timezone.utc) if at is None else at

    with uow:
        node = _load_active_entity(
            workspace_id=workspace_id,
            node_id=node_id,
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
            matched = _matched_node(node)

    logger.info(
        "knowledge_node_as_of_queried",
        workspace_id=workspace_id,
        node_id=str(node_id),
        found=matched is not None,
        as_of=as_of.isoformat(),
        predicate=predicate,
        claim_count=len(claims),
    )
    return AsOfQueryResult(subject=matched, as_of=as_of, claims=claims)


def query_claims_of_node_history(
    *,
    workspace_id: int,
    node_id: uuid.UUID,
    predicate: str | None = None,
    uow: KnowledgeReadUnitOfWork,
) -> AsOfQueryResult:
    """node id로 지목한 노드의 accepted였던 claim을 전부 읽는다.

    `query_claims_history`와 읽는 규칙은 같고 대상을 이름이 아니라 node
    id로 정한다. 나머지 계약은 `query_claims_of_node`와 같다.
    """
    queried_at = datetime.now(timezone.utc)

    with uow:
        node = _load_active_entity(
            workspace_id=workspace_id,
            node_id=node_id,
            uow=uow,
        )
        if node is None:
            claims: tuple[AsOfClaim, ...] = ()
            matched = None
        else:
            claims = uow.knowledge_candidates.find_accepted_claims_history(
                workspace_id=workspace_id,
                subject_node_id=node.id,
                predicate=predicate,
            )
            matched = _matched_node(node)

    logger.info(
        "knowledge_node_history_queried",
        workspace_id=workspace_id,
        node_id=str(node_id),
        found=matched is not None,
        queried_at=queried_at.isoformat(),
        predicate=predicate,
        claim_count=len(claims),
    )
    return AsOfQueryResult(subject=matched, as_of=queried_at, claims=claims)


def _load_active_entity(
    *,
    workspace_id: int,
    node_id: uuid.UUID,
    uow: KnowledgeReadUnitOfWork,
) -> KnowledgeNode | None:
    """node id로 살아 있는 entity 노드 하나를 집는다."""
    node = uow.knowledge_nodes.get_entity_by_id(
        workspace_id=workspace_id,
        node_id=node_id,
    )
    if node is None:
        return None
    if node.lifecycle_state is not NodeLifecycleState.ACTIVE:
        return None
    return node


def _matched_node(node: KnowledgeNode) -> MatchedSubject:
    """node id로 지목한 노드를 매칭 결과 모양으로 담는다."""
    return MatchedSubject(
        node_id=node.id,
        entity_type=node.entity_type or "",
        display_name=node.display_name,
        matched_by=MATCHED_BY_NODE_ID,
    )


def _resolve_subject(
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


def _find_similar_candidates(
    *,
    workspace_id: int,
    subject: str,
    uow: KnowledgeReadUnitOfWork,
) -> tuple[SubjectCandidate, ...]:
    """이름이 비슷한 노드를 후보로만 모은다.

    정확 매칭이 모두 빗나간 뒤에만 부른다. 여기서 나온 노드는 어떤
    경우에도 subject로 승격하지 않는다 — 승격시키는 순간 읽기 경로가
    근사 매칭이 되어 재현성이 깨지기 때문이다.
    """
    found = uow.knowledge_nodes.find_entity_candidates_by_similarity(
        workspace_id=workspace_id,
        normalized_query=normalize_name(subject),
        threshold=SIMILARITY_THRESHOLD,
        limit=SIMILARITY_CANDIDATE_LIMIT,
    )
    return tuple(
        SubjectCandidate(
            node_id=node.id,
            display_name=node.display_name,
            entity_type=node.entity_type,
            score=score,
        )
        for node, score in found
    )
