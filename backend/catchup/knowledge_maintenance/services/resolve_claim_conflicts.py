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
from collections.abc import Callable
from collections.abc import Iterable
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from datetime import timezone
from types import TracebackType
from typing import Protocol
from typing import Self

from catchup.knowledge_maintenance.contracts.extraction import ExtractionVocabulary
from catchup.knowledge_maintenance.contracts.extraction import PredicateEntry
from catchup.knowledge_maintenance.domain.claim_conflict import StoredClaimCandidate
from catchup.knowledge_maintenance.domain.claim_conflict import dates_compatible
from catchup.knowledge_maintenance.domain.claim_conflict import normalize_value
from catchup.knowledge_maintenance.domain.source_version import JsonValue
from catchup.knowledge_maintenance.domain.temporal import claim_not_closed_at
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


def conflict_idempotency_key(
    subject_key: str,
    predicate: str,
    member_hash: str | None = None,
) -> str:
    """모순 검토 단위의 proposal key를 만든다.

    subject_key와 predicate를 그대로 이으면 255자 컬럼을 넘길 수 있어
    고정 길이 해시로 만든다. 사람이 읽을 값은 summary와
    resolver_metadata에 남는다.

    member_hash가 있으면 key에 섞는다. 같은 subject·predicate에 이미
    결정이 내려진 뒤 다른 구성의 모순이 생겼을 때, 결정된 행을 덮지
    않고 새 검토 사건을 여는 데 쓴다.
    """
    raw = f"contradiction:{subject_key}:{predicate}"
    if member_hash is not None:
        raw = f"{raw}:{member_hash}"
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
        claims_not_comparable: 사전 미등재나 text 치역이라 비교하지 않은
            수를 나타낸다.
        claims_closed: 구간이 닫혀 더 이상 비교하지 않는 수를 나타낸다.
        claims_unparseable: 값을 비교 키로 못 바꾼 수를 나타낸다.
        groups_compared: 실제로 값을 견준 그룹 수를 나타낸다.
        conflicts_found: 값이 두 종 이상으로 갈린 그룹 수를 나타낸다.
        proposals_created: 새로 쓴 모순 proposal 수를 나타낸다.
        proposals_abandoned: 구성이 달라지거나 모순이 사라져 접은
            proposal 수를 나타낸다.
        duplicates_observed: 모순 그룹 안에서 같은 값이 겹쳐 관찰된
            수를 나타낸다. 리포트의 계류 모순 중복 지표와 같은
            정의이며, 차이는 스코프(이번 실행 vs 계류 중)뿐이다.
        date_precision_overlaps: 정밀도만 다른 날짜 겹침이라 모순으로
            세지 않은 그룹 수를 나타낸다.
    """

    claims_scanned: int = 0
    claims_without_subject_key: int = 0
    claims_not_comparable: int = 0
    claims_closed: int = 0
    claims_unparseable: int = 0
    groups_compared: int = 0
    conflicts_found: int = 0
    proposals_created: int = 0
    proposals_abandoned: int = 0
    duplicates_observed: int = 0
    date_precision_overlaps: int = 0


def resolve_claim_conflicts(
    *,
    workspace_id: int,
    vocabulary: ExtractionVocabulary,
    uow: ClaimConflictUnitOfWork,
    clock: Callable[[], datetime] | None = None,
) -> ClaimConflictResult:
    """claim 값의 모순을 찾아 proposal로 남기고 집계를 돌려준다."""
    now = (clock or _utcnow)()
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
        entries: dict[str, PredicateEntry] = {}
        without_key = 0
        not_comparable = 0
        closed = 0
        for claim in claims:
            if not claim_not_closed_at(claim.valid_to, now):
                # 사람이 이미 판정해 닫은 주장이다. 다시 비교하면
                # 해소된 모순이 영원히 되살아난다. 발효 예정
                # (valid_from이 미래)인 주장은 여기서 거르지 않는다 —
                # 판정 정의는 `domain.temporal`이 단독으로 갖는다.
                closed += 1
                continue
            entry = vocabulary.predicate_entry(claim.predicate)
            if entry is None or entry.value_type == "text":
                # 사전 미등재와 text 치역은 비교하지 않는다.
                not_comparable += 1
                continue
            entries[claim.predicate] = entry
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
        date_overlaps = 0
        active_keys: set[str] = set()
        for (subject_key, predicate), members in sorted(groups.items()):
            entry = entries[predicate]
            value_type = entry.value_type
            parsed: list[tuple[StoredClaimCandidate, str]] = []
            for claim in members:
                # 치역은 사전이 정한다. LLM이 신고한 value_type을 믿으면
                # 잘못 신고된 claim이 비교에서 조용히 빠진다.
                normalized = normalize_value(
                    value_type,
                    claim.value,
                    enum_values=entry.enum_values,
                )
                if normalized is None:
                    unparseable += 1
                    continue
                parsed.append((claim, normalized))
            if len(parsed) < 2:
                continue
            compared += 1

            distinct = {normalized for _, normalized in parsed}
            if len(distinct) < 2:
                continue
            if value_type == "date" and dates_compatible(distinct):
                # 정밀도만 다른 같은 시점이다. 모순이라 부르면 사람이
                # 같은 사실 사이에서 승자를 고르게 된다.
                date_overlaps += 1
                continue
            duplicates += len(parsed) - len(distinct)
            conflicts += 1

            parsed.sort(key=lambda item: (item[0].observed_at, item[0].id))
            member_hash = _member_hash(parsed)
            key = conflict_idempotency_key(subject_key, predicate)
            decided = (
                uow.mutation_proposals.find_decided_by_idempotency_key(
                    workspace_id=workspace_id,
                    idempotency_key=key,
                )
            )
            if decided is not None:
                if decided.resolver_metadata.get("member_hash") == (
                    member_hash
                ):
                    # 사람이 이 구성에 이미 결정을 내렸다. 같은 사실을
                    # 다시 묻지 않는다.
                    logger.info(
                        "claim_conflict_decision_standing",
                        workspace_id=workspace_id,
                        proposal_id=str(decided.id),
                        subject_key=subject_key,
                        predicate=predicate,
                    )
                    continue
                # 구성이 달라졌다. 결정된 행은 감사 기록이므로 덮지 않고
                # 멤버 지문을 섞은 key로 새 검토 사건을 연다. key가
                # 구성마다 결정론적이라 재실행이 같은 사건을 가리킨다.
                key = conflict_idempotency_key(
                    subject_key, predicate, member_hash
                )
                decided_variant = (
                    uow.mutation_proposals.find_decided_by_idempotency_key(
                        workspace_id=workspace_id,
                        idempotency_key=key,
                    )
                )
                if decided_variant is not None:
                    continue
            active_keys.add(key)
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
                    "citation_verified": claim.citation_verified,
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

        abandoned += _recall_stale_proposals(
            workspace_id=workspace_id,
            vocabulary=vocabulary,
            active_keys=active_keys,
            uow=uow,
        )

        uow.commit()

    result = ClaimConflictResult(
        claims_scanned=len(claims),
        claims_without_subject_key=without_key,
        claims_not_comparable=not_comparable,
        claims_closed=closed,
        claims_unparseable=unparseable,
        groups_compared=compared,
        conflicts_found=conflicts,
        proposals_created=created,
        proposals_abandoned=abandoned,
        duplicates_observed=duplicates,
        date_precision_overlaps=date_overlaps,
    )
    logger.info(
        "claim_conflict_completed",
        workspace_id=workspace_id,
        claims_scanned=result.claims_scanned,
        claims_without_subject_key=result.claims_without_subject_key,
        claims_not_comparable=result.claims_not_comparable,
        claims_closed=result.claims_closed,
        claims_unparseable=result.claims_unparseable,
        groups_compared=result.groups_compared,
        conflicts_found=result.conflicts_found,
        proposals_created=result.proposals_created,
        proposals_abandoned=result.proposals_abandoned,
        duplicates_observed=result.duplicates_observed,
        date_precision_overlaps=result.date_precision_overlaps,
    )
    return result


def _recall_stale_proposals(
    *,
    workspace_id: int,
    vocabulary: ExtractionVocabulary,
    active_keys: set[str],
    uow: ClaimConflictUnitOfWork,
) -> int:
    """이번 실행이 확인하지 못한 모순 계획서를 접고 그 수를 돌려준다.

    회수 범위를 "지금도 비교 대상인 predicate"로 좁힌다. 사전에서 빠진
    predicate의 claim은 애초에 그룹이 되지 못해 확인된 key도 남지
    않는다. 그것을 모순 소멸로 읽으면 어휘를 되돌리는 한 번의 실행이
    검토 큐를 통째로 비운다. 회수하지 않고 남기는 쪽이 안전하다.
    사람이 접는 것은 언제든 되지만 접힌 큐를 되살릴 수는 없다.
    """
    if not vocabulary.predicate_entries:
        # v1 스냅샷은 이름 목록만 있어 치역을 모른다. 모든 claim이 비교
        # 대상에서 빠지므로 회수 판정의 근거가 통째로 사라진다.
        logger.warning(
            "claim_conflict_recall_skipped",
            workspace_id=workspace_id,
            reason="vocabulary_without_predicate_entries",
            snapshot_id=vocabulary.snapshot_id,
        )
        return 0

    stale = uow.mutation_proposals.find_pending_contradiction_proposals(
        workspace_id=workspace_id,
    )
    abandoned = 0
    for proposal_id, idempotency_key, predicate in stale:
        if idempotency_key in active_keys:
            continue
        entry = (
            vocabulary.predicate_entry(predicate)
            if predicate is not None
            else None
        )
        if entry is None or entry.value_type == "text":
            logger.info(
                "claim_conflict_recall_deferred",
                workspace_id=workspace_id,
                proposal_id=str(proposal_id),
                predicate=predicate,
            )
            continue
        uow.mutation_proposals.abandon(proposal_id=proposal_id)
        abandoned += 1
        logger.info(
            "claim_conflict_recalled",
            workspace_id=workspace_id,
            proposal_id=str(proposal_id),
            predicate=predicate,
        )
    return abandoned


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


def _member_hash(
    members: Iterable[tuple[StoredClaimCandidate, str]],
) -> str:
    """그룹 구성의 지문을 만든다.

    멤버가 달라지거나 같은 멤버의 정규화 값이 달라지면 지문이
    달라진다. 값 정정은 사람이 다시 봐야 할 새 구성이기 때문이다.
    """
    joined = ",".join(
        sorted(
            f"{claim.id}:{normalized}" for claim, normalized in members
        )
    )
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def _json_value(value: object) -> JsonValue:
    """원본 값을 JSON으로 남길 수 있는 형태로 바꾼다."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    return str(value)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)
