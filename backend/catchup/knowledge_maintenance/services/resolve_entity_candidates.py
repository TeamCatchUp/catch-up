"""pending entity 후보를 canonical identity로 해소한다.

두 단계로 나뉜다. 성격이 다른 두 산출물을 낸다.

결정론 단계는 즉시 적용한다. 외부 ID가 같으면 같은 대상이라는 판정은
틀릴 수 없고, 사람이 봐도 거절할 이유가 없다. metadata 후보를 canonical
노드로 발급·병합하고, 이미 존재하는 canonical key와 정확히 일치하거나
같은 종류의 이름 alias에 정확히 걸리는 LLM 후보를 그 노드에 병합한다.
alias까지 보는 이유는 사람이 승인해 만든 노드에는 canonical key가 없어
key 조회만으로는 같은 이름이 다시 와도 영영 닿지 못하기 때문이다. LLM
후보의 신규 canonical 발급은 하지 않는다 — 후보 단계의 병합은 UPDATE 몇
줄이지만 canonical 창설 후 병합은 lifecycle과 FK 정리가 따르므로, 창설을
늦출수록 병합이 싸다.

fuzzy 단계는 proposal만 쓴다. 같은 정규화 이름인데 후보가 여럿인 그룹을
LLM이 판정하고, 같다고 하면 KnowledgeMutationProposal로 남긴다. 적용은
승인 트랜잭션의 일이다.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from types import TracebackType
from typing import Protocol
from typing import Self

from catchup.knowledge_maintenance.domain.entity_resolution import (
    deterministic_canonical_key,
)
from catchup.knowledge_maintenance.domain.entity_resolution import normalize_name
from catchup.knowledge_maintenance.domain.knowledge_candidate import (
    EntityResolutionStatus,
)
from catchup.knowledge_maintenance.domain.knowledge_candidate import ExtractionMethod
from catchup.knowledge_maintenance.domain.knowledge_candidate import (
    StoredEntityCandidate,
)
from catchup.knowledge_maintenance.domain.knowledge_node import KnowledgeNode
from catchup.knowledge_maintenance.domain.knowledge_node import NodeKind
from catchup.knowledge_maintenance.domain.knowledge_node import NodeLifecycleState
from catchup.knowledge_maintenance.ports.identity_judge import IdentityJudge
from catchup.knowledge_maintenance.ports.identity_judge import JudgeCandidate
from catchup.knowledge_maintenance.ports.knowledge_candidates import (
    KnowledgeCandidateRepository,
)
from catchup.knowledge_maintenance.ports.knowledge_nodes import KnowledgeNodeRepository
from catchup.knowledge_maintenance.ports.mutation_proposals import (
    MutationProposalRepository,
)
from catchup.observability.logging import get_logger

logger = get_logger(__name__)

JUDGE_DETECTOR = "catchup.name_group_judge"
JUDGE_DETECTOR_VERSION = "1"


def group_idempotency_key(normalized_name: str) -> str:
    """이름 그룹의 proposal key를 만든다.

    정규화 이름을 그대로 쓰면 255자 컬럼을 넘칠 수 있어 고정 길이
    해시로 만든다. 사람이 읽을 이름은 summary와 resolver_metadata에
    남는다.
    """
    return hashlib.sha256(normalized_name.encode("utf-8")).hexdigest()


class ResolutionUnitOfWork(Protocol):
    """resolution이 쓰는 transaction 경계를 정의한다."""

    knowledge_candidates: KnowledgeCandidateRepository
    knowledge_nodes: KnowledgeNodeRepository
    mutation_proposals: MutationProposalRepository

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    def commit(self) -> None: ...


@dataclass(frozen=True, slots=True)
class ResolutionResult:
    """resolution 한 번의 집계를 표현한다.

    Attributes:
        nodes_created: 새로 발급한 canonical 노드 수를 나타낸다.
        candidates_accepted: 노드 발급의 주체가 된 후보 수를 나타낸다.
        candidates_merged: 기존 노드에 흡수된 후보 수를 나타낸다.
        proposals_created: 새로 쓴 병합 proposal 수를 나타낸다.
        proposals_abandoned: 멤버가 달라져 접은 proposal 수를 나타낸다.
        groups_judged: LLM이 판정한 그룹 수를 나타낸다.
        groups_failed: 판정에 실패해 건너뛴 그룹 수를 나타낸다.
    """

    nodes_created: int = 0
    candidates_accepted: int = 0
    candidates_merged: int = 0
    proposals_created: int = 0
    proposals_abandoned: int = 0
    groups_judged: int = 0
    groups_failed: int = 0


def resolve_entity_candidates(
    *,
    workspace_id: int,
    judge: IdentityJudge | None,
    uow: ResolutionUnitOfWork,
) -> ResolutionResult:
    """pending entity 후보를 해소하고 집계를 돌려준다.

    judge가 None이면 결정론 단계만 수행한다.
    """
    with uow:
        pending = uow.knowledge_candidates.find_pending_entity_candidates(
            workspace_id=workspace_id,
        )

        nodes_created = 0
        accepted = 0
        merged = 0

        deterministic = [
            candidate
            for candidate in pending
            if candidate.extraction_method is ExtractionMethod.DETERMINISTIC
        ]
        llm = [
            candidate
            for candidate in pending
            if candidate.extraction_method is ExtractionMethod.LLM
        ]

        for candidate in deterministic:
            external_key = _external_key(candidate)
            if external_key is None:
                logger.info(
                    "entity_candidate_missing_external_key",
                    workspace_id=workspace_id,
                    candidate_id=str(candidate.id),
                )
                continue
            key = deterministic_canonical_key(
                candidate.source_type,
                candidate.proposed_type,
                external_key,
            )
            node = uow.knowledge_nodes.get_entity_by_canonical_key(
                workspace_id=workspace_id,
                canonical_key=key,
            )
            if node is None:
                node = uow.knowledge_nodes.create_entity_node(
                    workspace_id=workspace_id,
                    entity_type=candidate.proposed_type,
                    canonical_key=key,
                    display_name=candidate.proposed_name,
                )
                nodes_created += 1
                status = EntityResolutionStatus.ACCEPTED
                accepted += 1
            else:
                status = EntityResolutionStatus.MERGED
                merged += 1
            uow.knowledge_candidates.mark_entity_resolved(
                candidate_id=candidate.id,
                status=status,
                resolved_node_id=node.id,
            )
            uow.knowledge_nodes.add_alias(
                workspace_id=workspace_id,
                node_id=node.id,
                alias=candidate.proposed_name,
                normalized_alias=normalize_name(candidate.proposed_name),
                source="source",
            )

        remaining_llm = []
        for candidate in llm:
            key = (
                f"{candidate.proposed_type}:"
                f"{normalize_name(candidate.proposed_name)}"
            )
            node = uow.knowledge_nodes.get_entity_by_canonical_key(
                workspace_id=workspace_id,
                canonical_key=key,
            )
            if node is None:
                node = _reattachable_node(
                    workspace_id=workspace_id,
                    candidate=candidate,
                    uow=uow,
                )
            if node is None:
                remaining_llm.append(candidate)
                continue
            uow.knowledge_candidates.mark_entity_resolved(
                candidate_id=candidate.id,
                status=EntityResolutionStatus.MERGED,
                resolved_node_id=node.id,
            )
            uow.knowledge_nodes.add_alias(
                workspace_id=workspace_id,
                node_id=node.id,
                alias=candidate.proposed_name,
                normalized_alias=normalize_name(candidate.proposed_name),
                source="extractor",
            )
            merged += 1

        fuzzy = _FuzzyCounts()
        if judge is not None:
            fuzzy = _judge_name_groups(
                workspace_id=workspace_id,
                candidates=remaining_llm,
                judge=judge,
                uow=uow,
            )

        uow.commit()

    result = ResolutionResult(
        nodes_created=nodes_created,
        candidates_accepted=accepted,
        candidates_merged=merged,
        proposals_created=fuzzy.created,
        proposals_abandoned=fuzzy.abandoned,
        groups_judged=fuzzy.judged,
        groups_failed=fuzzy.failed,
    )
    logger.info(
        "entity_resolution_completed",
        workspace_id=workspace_id,
        nodes_created=result.nodes_created,
        candidates_accepted=result.candidates_accepted,
        candidates_merged=result.candidates_merged,
        proposals_created=result.proposals_created,
        proposals_abandoned=result.proposals_abandoned,
        groups_judged=result.groups_judged,
        groups_failed=result.groups_failed,
    )
    return result


@dataclass(frozen=True, slots=True)
class _FuzzyCounts:
    """fuzzy 단계의 집계를 표현한다."""

    created: int = 0
    abandoned: int = 0
    judged: int = 0
    failed: int = 0


def _external_key(candidate: StoredEntityCandidate) -> str | None:
    """후보의 raw_payload에서 외부 ID를 꺼낸다."""
    attributes = candidate.raw_payload.get("attributes")
    if not isinstance(attributes, dict):
        return None
    external_key = attributes.get("external_key")
    if not isinstance(external_key, str) or not external_key.strip():
        return None
    return external_key


def _reattachable_node(
    *,
    workspace_id: int,
    candidate: StoredEntityCandidate,
    uow: ResolutionUnitOfWork,
) -> KnowledgeNode | None:
    """이름 alias로 후보를 흡수할 기존 노드를 찾는다.

    canonical_key 조회만으로는 사람이 승인해 만든 노드에 후보가 절대
    닿지 못한다. 그 노드는 외부 ID가 없어 canonical_key가 비어 있고,
    가진 단서는 이름 alias뿐이기 때문이다. 그래서 key가 빗나가면 정규화
    이름 alias 정확 일치를 한 번 더 본다.

    다만 alias는 identity가 아니다. 이름 키에는 type이 들어 있지 않아
    같은 이름의 다른 종류가 걸릴 수 있으므로, 노드의 entity_type이 후보
    proposed_type과 같을 때만 흡수한다 — 과병합은 후보를 pending으로
    남겨두는 것보다 되돌리기가 훨씬 비싸다. 흡수된·퇴역한 노드도
    흡수처가 아니다. 조건을 못 넘기면 None을 주어 fuzzy 판정 대상으로
    남긴다.

    type 거르기는 조회에 넘긴다. alias 조회는 1건만 돌려주므로 여기서
    뒤늦게 type을 보면, 같은 이름의 다른 type 노드가 id 순으로 앞설 때
    정작 맞는 노드가 영영 발견되지 않는다. 돌아온 1건에 대한 type 검사는
    이중 방어로 남긴다.

    한계: 같은 이름·같은 type의 active 노드가 둘 이상이면 흡수처가
    uuid 순 첫 번째로 임의 고정된다. 지금은 사람 승인이 만든 노드에만
    생기는 드문 상황이라 두고 있으나, 승격이 자동화되면 이 tie-break가
    사실상의 병합 정책이 되므로 별도 과제로 다뤄야 한다.
    """
    node = uow.knowledge_nodes.find_entity_by_normalized_alias(
        workspace_id=workspace_id,
        normalized_alias=normalize_name(candidate.proposed_name),
        entity_type=candidate.proposed_type,
    )
    if node is None:
        return None
    if node.node_kind is not NodeKind.ENTITY:
        return None
    if node.lifecycle_state is not NodeLifecycleState.ACTIVE:
        return None
    if node.entity_type != candidate.proposed_type:
        logger.info(
            "entity_alias_reattach_type_mismatch",
            workspace_id=workspace_id,
            candidate_id=str(candidate.id),
            node_id=str(node.id),
            node_entity_type=node.entity_type,
            proposed_type=candidate.proposed_type,
        )
        return None
    return node


def _judge_name_groups(
    *,
    workspace_id: int,
    candidates: list[StoredEntityCandidate],
    judge: IdentityJudge,
    uow: ResolutionUnitOfWork,
) -> _FuzzyCounts:
    """같은 정규화 이름 그룹을 판정하고 proposal을 쓴다."""
    groups: dict[str, list[StoredEntityCandidate]] = {}
    for candidate in candidates:
        groups.setdefault(
            normalize_name(candidate.proposed_name), []
        ).append(candidate)

    created = 0
    abandoned = 0
    judged = 0
    failed = 0
    for normalized_name, members in sorted(groups.items()):
        if len(members) < 2:
            continue
        members = sorted(members, key=lambda c: (c.created_at, c.id))
        member_hash = _member_hash(members)
        key = group_idempotency_key(normalized_name)

        existing = uow.mutation_proposals.find_pending_by_idempotency_key(
            workspace_id=workspace_id,
            idempotency_key=key,
        )
        if existing is not None:
            if existing.resolver_metadata.get("member_hash") == member_hash:
                continue
            # 멤버가 달라진 순간 기존 계획서는 낡았다. 새 판정이 무엇이든
            # 옛 구성의 병합안을 검토 큐에 남겨두면 안 된다.
            uow.mutation_proposals.abandon(proposal_id=existing.id)
            abandoned += 1

        try:
            verdict = judge.judge(
                tuple(
                    JudgeCandidate(
                        candidate_id=member.id,
                        proposed_type=member.proposed_type,
                        proposed_name=member.proposed_name,
                        excerpt=member.observation_excerpt,
                    )
                    for member in members
                )
            )
        except Exception as error:
            failed += 1
            logger.warning(
                "identity_judge_failed",
                workspace_id=workspace_id,
                group=normalized_name,
                error=f"{type(error).__name__}: {error}",
            )
            continue
        judged += 1

        # same=false는 proposal이 남지 않아 이 로그가 유일한 기록이다.
        # 판정 근거는 감사 대상이므로 결과와 무관하게 남긴다.
        logger.info(
            "identity_group_judged",
            workspace_id=workspace_id,
            group=normalized_name,
            member_count=len(members),
            same=verdict.same,
            reason=verdict.reason,
        )

        if not verdict.same:
            continue

        representative = members[0]
        uow.mutation_proposals.add_duplicate_proposal(
            workspace_id=workspace_id,
            idempotency_key=key,
            trigger_entity_candidate_id=representative.id,
            detector=JUDGE_DETECTOR,
            detector_version=JUDGE_DETECTOR_VERSION,
            summary=(
                f"같은 이름 '{normalized_name}' 후보 {len(members)}건 병합: "
                f"{verdict.reason}"
            ),
            resolver_metadata={
                "group_name": normalized_name,
                "member_ids": [str(member.id) for member in members],
                "member_hash": member_hash,
                "reason": verdict.reason,
            },
            representative_candidate_id=representative.id,
            merge_candidate_ids=tuple(
                member.id for member in members[1:]
            ),
            proposed_type=verdict.proposed_type or "",
            proposed_name=verdict.proposed_name or "",
        )
        created += 1

    return _FuzzyCounts(
        created=created,
        abandoned=abandoned,
        judged=judged,
        failed=failed,
    )


def _member_hash(members: list[StoredEntityCandidate]) -> str:
    """그룹 구성의 지문을 만든다. 멤버가 달라지면 값이 달라진다."""
    joined = ",".join(sorted(str(member.id) for member in members))
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()
