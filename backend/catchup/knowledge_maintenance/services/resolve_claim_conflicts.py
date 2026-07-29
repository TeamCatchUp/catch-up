"""같은 대상에 대한 주장끼리 값이 어긋나는지 판정한다.

비교는 사전이 값의 종류를 정해준 predicate에서만 한다. text 치역은
자유 서술이라 두 문장이 달라도 모순이라 부를 수 없고, 사전에 없는
predicate는 애초에 무엇을 비교해야 하는지 알 수 없기 때문이다.

같은 대상인지는 이름이 아니라 identity 근거로 판단한다. 이미 canonical
노드가 있으면 그 노드가, 아직 없으면 열려 있는 병합 계획서가 근거다.
근거가 없으면 비교하지 않는다. 이름만 같은 둘을 묶어 모순이라 부르면
검토 큐가 거짓 모순으로 채워지기 때문이다.

산출물은 proposal뿐이고 적용 명령은 만들지 않는다. 어느 값이 맞는지는
사람이 판단할 일이다.
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import Iterable
from collections.abc import Mapping
from dataclasses import dataclass
from types import TracebackType
from typing import Protocol
from typing import Self

from catchup.knowledge_maintenance.contracts.extraction import ExtractionVocabulary
from catchup.knowledge_maintenance.domain.claim_conflict import StoredClaimCandidate
from catchup.knowledge_maintenance.domain.claim_conflict import normalize_value
from catchup.knowledge_maintenance.domain.source_version import JsonValue
from catchup.knowledge_maintenance.ports.knowledge_candidates import (
    KnowledgeCandidateRepository,
)
from catchup.knowledge_maintenance.ports.mutation_proposals import (
    MutationProposalRepository,
)
from catchup.observability.logging import get_logger

logger = get_logger(__name__)

CONFLICT_DETECTOR = "catchup.claim_value_conflict"
CONFLICT_DETECTOR_VERSION = "1"


def conflict_idempotency_key(subject_key: str, predicate: str) -> str:
    """모순 검토 단위의 proposal key를 만든다.

    subject_key와 predicate를 그대로 이으면 255자 컬럼을 넘길 수 있어
    고정 길이 해시로 만든다. 사람이 읽을 값은 summary와
    resolver_metadata에 남는다.
    """
    raw = f"contradiction:{subject_key}:{predicate}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class ClaimConflictUnitOfWork(Protocol):
    """모순 판정이 쓰는 transaction 경계를 정의한다."""

    knowledge_candidates: KnowledgeCandidateRepository
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
class ClaimConflictResult:
    """모순 판정 한 번의 집계를 표현한다.

    Attributes:
        claims_scanned: 읽어들인 claim 후보 수를 나타낸다.
        claims_without_subject_key: identity 근거가 없어 뺀 수를 나타낸다.
        claims_unparseable: 값을 비교 키로 못 바꾼 수를 나타낸다.
        groups_compared: 실제로 값을 견준 그룹 수를 나타낸다.
        conflicts_found: 값이 두 종 이상으로 갈린 그룹 수를 나타낸다.
        proposals_created: 새로 쓴 모순 proposal 수를 나타낸다.
        proposals_abandoned: 구성이 달라져 접은 proposal 수를 나타낸다.
        duplicates_observed: 같은 값이 겹쳐 나온 수를 나타낸다.
    """

    claims_scanned: int = 0
    claims_without_subject_key: int = 0
    claims_unparseable: int = 0
    groups_compared: int = 0
    conflicts_found: int = 0
    proposals_created: int = 0
    proposals_abandoned: int = 0
    duplicates_observed: int = 0


def resolve_claim_conflicts(
    *,
    workspace_id: int,
    vocabulary: ExtractionVocabulary,
    uow: ClaimConflictUnitOfWork,
) -> ClaimConflictResult:
    """claim 값의 모순을 찾아 proposal로 남기고 집계를 돌려준다."""
    with uow:
        claims = uow.knowledge_candidates.find_claim_candidates(
            workspace_id=workspace_id,
        )
        duplicate_groups = (
            uow.mutation_proposals.find_pending_duplicate_groups(
                workspace_id=workspace_id,
            )
        )

        groups: dict[tuple[str, str], list[StoredClaimCandidate]] = {}
        without_key = 0
        for claim in claims:
            entry = vocabulary.predicate_entry(claim.predicate)
            if entry is None or entry.value_type == "text":
                # 사전 미등재와 text 치역은 비교하지 않는다.
                continue
            subject_key = _subject_key(claim, duplicate_groups)
            if subject_key is None:
                without_key += 1
                continue
            groups.setdefault(
                (subject_key, claim.predicate), []
            ).append(claim)

        unparseable = 0
        compared = 0
        conflicts = 0
        created = 0
        abandoned = 0
        duplicates = 0
        for (subject_key, predicate), members in sorted(groups.items()):
            parsed: list[tuple[StoredClaimCandidate, str]] = []
            for claim in members:
                normalized = normalize_value(claim.value_type, claim.value)
                if normalized is None:
                    unparseable += 1
                    continue
                parsed.append((claim, normalized))
            if len(parsed) < 2:
                continue
            compared += 1

            distinct = {normalized for _, normalized in parsed}
            duplicates += len(parsed) - len(distinct)
            if len(distinct) < 2:
                continue
            conflicts += 1

            parsed.sort(key=lambda item: (item[0].observed_at, item[0].id))
            member_hash = _member_hash(claim for claim, _ in parsed)
            key = conflict_idempotency_key(subject_key, predicate)
            existing = (
                uow.mutation_proposals.find_pending_by_idempotency_key(
                    workspace_id=workspace_id,
                    idempotency_key=key,
                )
            )
            if existing is not None:
                if existing.resolver_metadata.get("member_hash") == (
                    member_hash
                ):
                    continue
                # 구성이 달라진 순간 기존 계획서는 낡았다. 옛 구성의
                # 모순 목록을 검토 큐에 남겨두면 안 된다.
                uow.mutation_proposals.abandon(proposal_id=existing.id)
                abandoned += 1

            values: list[JsonValue] = [
                {
                    "claim_id": str(claim.id),
                    "value": _json_value(claim.value),
                    "normalized": normalized,
                    "observed_at": claim.observed_at.isoformat(),
                    "statement": claim.statement,
                }
                for claim, normalized in parsed
            ]
            uow.mutation_proposals.add_contradiction_proposal(
                workspace_id=workspace_id,
                idempotency_key=key,
                trigger_claim_candidate_id=parsed[0][0].id,
                detector=CONFLICT_DETECTOR,
                detector_version=CONFLICT_DETECTOR_VERSION,
                summary=(
                    f"'{predicate}' 값이 {len(distinct)}종으로 갈린다: "
                    f"claim {len(parsed)}건"
                ),
                resolver_metadata={
                    "subject_key": subject_key,
                    "predicate": predicate,
                    "values": values,
                    "member_hash": member_hash,
                },
            )
            created += 1
            logger.info(
                "claim_conflict_recorded",
                workspace_id=workspace_id,
                subject_key=subject_key,
                predicate=predicate,
                distinct_values=len(distinct),
                claim_count=len(parsed),
            )

        uow.commit()

    result = ClaimConflictResult(
        claims_scanned=len(claims),
        claims_without_subject_key=without_key,
        claims_unparseable=unparseable,
        groups_compared=compared,
        conflicts_found=conflicts,
        proposals_created=created,
        proposals_abandoned=abandoned,
        duplicates_observed=duplicates,
    )
    logger.info(
        "claim_conflict_completed",
        workspace_id=workspace_id,
        claims_scanned=result.claims_scanned,
        claims_without_subject_key=result.claims_without_subject_key,
        claims_unparseable=result.claims_unparseable,
        groups_compared=result.groups_compared,
        conflicts_found=result.conflicts_found,
        proposals_created=result.proposals_created,
        proposals_abandoned=result.proposals_abandoned,
        duplicates_observed=result.duplicates_observed,
    )
    return result


def _subject_key(
    claim: StoredClaimCandidate,
    duplicate_groups: Mapping[uuid.UUID, uuid.UUID],
) -> str | None:
    """주장이 가리키는 대상의 비교 키를 만든다.

    canonical 노드가 있으면 그것이 가장 강한 근거다. 아직 노드가 없으면
    열려 있는 병합 계획서가 같은 대상이라는 유일한 근거가 된다.
    """
    if claim.subject_node_id is not None:
        return f"node:{claim.subject_node_id}"
    if claim.subject_resolved_node_id is not None:
        return f"node:{claim.subject_resolved_node_id}"
    if claim.subject_entity_candidate_id is not None:
        proposal_id = duplicate_groups.get(claim.subject_entity_candidate_id)
        if proposal_id is not None:
            return f"proposal:{proposal_id}"
    return None


def _member_hash(claims: Iterable[StoredClaimCandidate]) -> str:
    """그룹 구성의 지문을 만든다. 멤버가 달라지면 값이 달라진다."""
    joined = ",".join(sorted(str(claim.id) for claim in claims))
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def _json_value(value: object) -> JsonValue:
    """원본 값을 JSON으로 남길 수 있는 형태로 바꾼다."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    return str(value)
