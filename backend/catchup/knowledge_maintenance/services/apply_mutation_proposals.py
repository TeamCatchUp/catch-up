"""승인된 병합 안건의 적용 명령을 결정론적으로 실행한다.

결정(approved)과 적용(applied)은 다른 순간이다. 이 실행기는 결정
저널을 소비할 뿐 아무것도 판단하지 않는다 — 판단은 judge(판정)와
사람(결정)이 이미 끝냈다.

proposal 하나가 트랜잭션 하나다. 하나가 실패해도 다른 안건의 적용은
살아남아야 하고, 실패한 안건은 approved로 남아 재시도할 수 있어야
한다. 미지의 명령은 조용히 건너뛰지 않고 그 안건만 실패로 처리한다 —
새 명령 종류가 소리 없이 무시되면 결정과 현실이 어긋난다.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from types import TracebackType
from typing import Protocol
from typing import Self

from catchup.knowledge_maintenance.domain.entity_resolution import normalize_name
from catchup.knowledge_maintenance.domain.knowledge_candidate import (
    AssertionResolutionStatus,
)
from catchup.knowledge_maintenance.domain.knowledge_candidate import (
    EntityResolutionStatus,
)
from catchup.knowledge_maintenance.domain.knowledge_node import NodeLifecycleState
from catchup.knowledge_maintenance.ports.knowledge_candidates import (
    KnowledgeCandidateRepository,
)
from catchup.knowledge_maintenance.ports.knowledge_nodes import KnowledgeNodeRepository
from catchup.knowledge_maintenance.ports.mutation_proposals import (
    MutationProposalRepository,
)
from catchup.knowledge_maintenance.ports.mutation_proposals import StoredOperation
from catchup.observability.logging import get_logger

logger = get_logger(__name__)

SUPPORTED_OPERATIONS = ("create_entity", "merge_entity", "supersede_claim")


class ApplyOperationError(Exception):
    """적용할 수 없는 명령을 만났음을 알린다."""


class ApplyUnitOfWork(Protocol):
    """적용이 쓰는 transaction 경계를 정의한다."""

    mutation_proposals: MutationProposalRepository
    knowledge_candidates: KnowledgeCandidateRepository
    knowledge_nodes: KnowledgeNodeRepository

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    def commit(self) -> None: ...


@dataclass(frozen=True, slots=True)
class ApplyResult:
    """적용 한 번의 집계를 표현한다.

    Attributes:
        proposals_applied: 끝까지 적용된 안건 수를 나타낸다.
        proposals_failed: 실패해 approved로 남은 안건 수를 나타낸다.
        candidates_resolved: 이번에 새로 해소된 후보 수를 나타낸다.
        candidates_already_resolved: 이미 해소돼 있어 건너뛴 후보
            수를 나타낸다.
        claims_superseded: 구간을 닫은 claim 수를 나타낸다. 한때
            참이었던 주장이다.
        claims_invalidated: 지식이 되기 전에 탈락한 claim 수를
            나타낸다.
        claims_already_closed: 이미 닫혔거나 탈락해 건너뛴 claim
            수를 나타낸다.
        claims_skipped_superseded: 재추출이 은퇴시켜 건너뛴 claim 수를
            나타낸다. 지식이 된 적 없으므로 닫지도 탈락시키지도
            않는다.
    """

    proposals_applied: int
    proposals_failed: int
    candidates_resolved: int
    candidates_already_resolved: int
    claims_superseded: int = 0
    claims_invalidated: int = 0
    claims_already_closed: int = 0
    claims_skipped_superseded: int = 0


@dataclass
class _Tally:
    """proposal 하나를 적용하는 동안의 셈을 담는다."""

    resolved: int = 0
    already: int = 0
    superseded: int = 0
    invalidated: int = 0
    closed_already: int = 0
    skipped_superseded: int = 0


def apply_mutation_proposals(
    uow_factory: Callable[[], ApplyUnitOfWork],
    *,
    workspace_id: int,
    proposal_id: uuid.UUID | None = None,
) -> ApplyResult:
    """승인된 안건을 순서대로 적용한다.

    factory를 받는 이유는 proposal 단위 트랜잭션 때문이다. 한 uow에
    전부 태우면 마지막 안건의 실패가 앞선 적용까지 되돌린다.

    `proposal_id`를 주면 그 안건만 적용한다. 사람이 큐에서 한 건을
    골라 적용하는 경로다. 지정한 안건이 승인 목록에 없으면 아무것도
    적용하지 않고 0건으로 끝낸다 — 없는 안건과 적용에 실패한 안건은
    다른 일이므로 실패로 세지 않고, 404를 낼지는 적용 건수를 보는
    호출자가 정한다.
    """
    with uow_factory() as uow:
        approved = uow.mutation_proposals.find_approved_proposals_with_operations(
            workspace_id=workspace_id,
        )
    if proposal_id is not None:
        approved = [item for item in approved if item[0] == proposal_id]

    applied = 0
    failed = 0
    resolved = 0
    already = 0
    superseded = 0
    invalidated = 0
    closed_already = 0
    skipped_superseded = 0
    # 루프 변수를 파라미터와 다른 이름으로 둔다. 같은 이름을 쓰면
    # 루프가 파라미터를 덮어써서, 뒤에 나오는 감사 로그의
    # `scoped_proposal_id`가 "전체 적용"인지 "한 건 적용"인지를 잃는다.
    for approved_id, operations in approved:
        try:
            tally = _apply_one(
                uow_factory,
                workspace_id=workspace_id,
                proposal_id=approved_id,
                operations=operations,
            )
        except ApplyOperationError as error:
            failed += 1
            logger.error(
                "mutation_apply_failed",
                workspace_id=workspace_id,
                proposal_id=str(approved_id),
                reason=str(error),
            )
            continue
        applied += 1
        resolved += tally.resolved
        already += tally.already
        superseded += tally.superseded
        invalidated += tally.invalidated
        closed_already += tally.closed_already
        skipped_superseded += tally.skipped_superseded
        logger.info(
            "mutation_proposal_applied",
            workspace_id=workspace_id,
            proposal_id=str(approved_id),
            candidates_resolved=tally.resolved,
            candidates_already_resolved=tally.already,
        )

    result = ApplyResult(
        proposals_applied=applied,
        proposals_failed=failed,
        candidates_resolved=resolved,
        candidates_already_resolved=already,
        claims_superseded=superseded,
        claims_invalidated=invalidated,
        claims_already_closed=closed_already,
        claims_skipped_superseded=skipped_superseded,
    )
    logger.info(
        "mutation_apply_completed",
        workspace_id=workspace_id,
        # 한 건만 적용한 실행과 전체 적용을 감사 기록에서 구분한다.
        scoped_proposal_id=None if proposal_id is None else str(proposal_id),
        proposals_applied=result.proposals_applied,
        proposals_failed=result.proposals_failed,
        candidates_resolved=result.candidates_resolved,
        candidates_already_resolved=result.candidates_already_resolved,
        claims_superseded=result.claims_superseded,
        claims_invalidated=result.claims_invalidated,
        claims_already_closed=result.claims_already_closed,
        claims_skipped_superseded=result.claims_skipped_superseded,
    )
    return result


def _apply_one(
    uow_factory: Callable[[], ApplyUnitOfWork],
    *,
    workspace_id: int,
    proposal_id: uuid.UUID,
    operations: tuple[StoredOperation, ...],
) -> _Tally:
    """안건 하나를 자기 트랜잭션 안에서 적용한다."""
    unsupported = [
        operation.operation_type
        for operation in operations
        if operation.operation_type not in SUPPORTED_OPERATIONS
    ]
    if unsupported:
        raise ApplyOperationError(
            f"지원하지 않는 명령이다: {sorted(set(unsupported))}"
        )

    tally = _Tally()
    with uow_factory() as uow:
        nodes_by_sequence: dict[int, uuid.UUID] = {}
        for operation in sorted(operations, key=lambda item: item.sequence):
            if operation.operation_type == "create_entity":
                created = _apply_create(
                    uow,
                    workspace_id=workspace_id,
                    operation=operation,
                    tally=tally,
                )
                if created is not None:
                    nodes_by_sequence[operation.sequence] = created
            elif operation.operation_type == "merge_entity":
                _apply_merge(
                    uow,
                    operation=operation,
                    nodes_by_sequence=nodes_by_sequence,
                    tally=tally,
                )
            else:
                _apply_supersede(uow, operation=operation, tally=tally)
        uow.mutation_proposals.mark_applied(
            workspace_id=workspace_id,
            proposal_id=proposal_id,
        )
        uow.commit()
    return tally


def _apply_create(
    uow: ApplyUnitOfWork,
    *,
    workspace_id: int,
    operation: StoredOperation,
    tally: _Tally,
) -> uuid.UUID | None:
    """대표 후보로 canonical 노드를 만들거나 기존 노드를 재사용한다.

    대표가 재추출로 은퇴(`superseded`)했으면 노드를 만들지 않고 None을
    낸다. 이 대표를 가리키던 병합 명령은 대상 노드를 못 찾아 그 안건만
    실패로 남는데, 은퇴한 대표로 새 노드를 세우는 것보다 사람이 다시 보게
    두는 편이 안전하다.

    명령 재료에 `merge_into_node_id`가 있으면 노드를 만들지 않고 그 노드로
    대표를 붙인다. 이미 서 있는 노드와 같은 대상이라는 판정을 사람이
    승인한 경우다. 여기서 노드를 또 만들면 합치자는 결정이 도리어 대상을
    하나 더 세운다. 붙일 때 후보의 이름을 그 노드의 alias로 남긴다 —
    노드가 이번에 확인된 표기로도 불릴 수 있어야 다음 후보가 같은 자리로
    온다.

    새로 만든 노드에는 곧바로 이름 alias를 남긴다. 이 경로의 노드는
    외부 ID가 없어 canonical_key가 비므로, alias가 없으면 읽기 경로가
    (canonical_key -> normalized_alias 순으로 찾는다) 방금 만든 노드를
    어떤 이름으로도 못 찾는다. 노드를 만들면 그 이름으로 부를 수
    있어야 한다는 계약을 쓰기 쪽에서 지킨다. 기존 노드를 재사용하는
    분기는 이전 적용이나 다른 경로가 이미 그 계약을 지켰으므로 여기서
    alias를 더하지 않는다.
    """
    candidate_id = operation.entity_candidate_id
    if candidate_id is None:
        raise ApplyOperationError("create_entity에 후보가 없다")
    current = uow.knowledge_candidates.get_entity_resolution(
        candidate_id=candidate_id,
    )
    if current is None:
        raise ApplyOperationError(f"후보가 없다: {candidate_id}")
    status, resolved_node_id = current
    if resolved_node_id is not None:
        # 대표가 이미 해소됐으면 그 노드가 곧 병합 대상이다. 새 노드를
        # 만들면 같은 대상이 둘로 갈라진다.
        tally.already += 1
        return resolved_node_id
    if status == EntityResolutionStatus.SUPERSEDED:
        # 승인 이후 재추출이 대표를 은퇴시켰다. 은퇴한 후보를 accepted로
        # 되돌리면 사람 결정이 아닌 상태 변화를 결정처럼 남긴다.
        tally.already += 1
        return None

    proposed_name = str(operation.operation_data["proposed_name"])
    target_raw = operation.operation_data.get("merge_into_node_id")
    if target_raw is not None:
        return _merge_into_existing_node(
            uow,
            workspace_id=workspace_id,
            candidate_id=candidate_id,
            node_id_raw=target_raw,
            proposed_name=proposed_name,
            tally=tally,
        )

    node = uow.knowledge_nodes.create_entity_node(
        workspace_id=workspace_id,
        entity_type=str(operation.operation_data["proposed_type"]),
        canonical_key=None,
        display_name=proposed_name,
    )
    # add_alias는 같은 정규화 alias를 만나면 그냥 넘어가므로 적용을
    # 다시 돌려도 행이 불어나지 않는다.
    uow.knowledge_nodes.add_alias(
        workspace_id=workspace_id,
        node_id=node.id,
        alias=proposed_name,
        normalized_alias=normalize_name(proposed_name),
        source="system",
    )
    uow.knowledge_candidates.mark_entity_resolved(
        candidate_id=candidate_id,
        status=EntityResolutionStatus.ACCEPTED,
        resolved_node_id=node.id,
    )
    tally.resolved += 1
    return node.id


def _merge_into_existing_node(
    uow: ApplyUnitOfWork,
    *,
    workspace_id: int,
    candidate_id: uuid.UUID,
    node_id_raw: object,
    proposed_name: str,
    tally: _Tally,
) -> uuid.UUID:
    """대표 후보를 이미 서 있는 노드로 붙인다.

    노드가 없거나 살아 있지 않으면 이 안건만 실패로 남긴다. 승인 이후
    노드가 흡수·퇴역했다는 뜻이고, 그때 노드를 새로 만들면 사람이 승인한
    "저 노드와 같다"는 결정과 다른 일을 하게 된다.

    Raises:
        ApplyOperationError: 노드 id를 읽을 수 없거나, 노드가 없거나,
            살아 있지 않을 때 던진다.
    """
    try:
        node_id = uuid.UUID(str(node_id_raw))
    except ValueError as error:
        raise ApplyOperationError(
            f"병합 대상 노드 id를 읽을 수 없다: {node_id_raw}"
        ) from error

    node = uow.knowledge_nodes.get_entity_by_id(
        workspace_id=workspace_id,
        node_id=node_id,
    )
    if node is None:
        raise ApplyOperationError(f"병합 대상 노드가 없다: {node_id}")
    if node.lifecycle_state is not NodeLifecycleState.ACTIVE:
        raise ApplyOperationError(
            f"병합 대상 노드가 살아 있지 않다: {node_id}"
        )

    uow.knowledge_nodes.add_alias(
        workspace_id=workspace_id,
        node_id=node_id,
        alias=proposed_name,
        normalized_alias=normalize_name(proposed_name),
        source="system",
    )
    uow.knowledge_candidates.mark_entity_resolved(
        candidate_id=candidate_id,
        status=EntityResolutionStatus.MERGED,
        resolved_node_id=node_id,
    )
    tally.resolved += 1
    return node_id


def _apply_merge(
    uow: ApplyUnitOfWork,
    *,
    operation: StoredOperation,
    nodes_by_sequence: dict[int, uuid.UUID],
    tally: _Tally,
) -> None:
    """멤버 후보를 대표의 노드로 해소한다."""
    candidate_id = operation.entity_candidate_id
    if candidate_id is None:
        raise ApplyOperationError("merge_entity에 후보가 없다")
    target_sequence = operation.operation_data.get("merge_into_sequence")
    target_node_id = nodes_by_sequence.get(int(str(target_sequence)))
    if target_node_id is None:
        raise ApplyOperationError(
            f"병합 대상 sequence가 없다: {target_sequence}"
        )

    current = uow.knowledge_candidates.get_entity_resolution(
        candidate_id=candidate_id,
    )
    if current is None:
        raise ApplyOperationError(f"후보가 없다: {candidate_id}")
    status, resolved_node_id = current
    if resolved_node_id is not None:
        tally.already += 1
        return
    if status == EntityResolutionStatus.SUPERSEDED:
        # 재추출이 은퇴시킨 멤버는 병합하지 않는다. 은퇴한 후보를 merged로
        # 표시하면 사라진 후보가 지식에 붙은 것처럼 보인다.
        tally.already += 1
        return
    uow.knowledge_candidates.mark_entity_resolved(
        candidate_id=candidate_id,
        status=EntityResolutionStatus.MERGED,
        resolved_node_id=target_node_id,
    )
    tally.resolved += 1


def _apply_supersede(
    uow: ApplyUnitOfWork,
    *,
    operation: StoredOperation,
    tally: _Tally,
) -> None:
    """패자 claim을 닫거나 탈락시키고 승자를 확정한다.

    닫는 방식은 패자의 상태가 정한다. 한때 받아들여진 주장은 구간만
    닫아 "그때는 참이었다"를 남기고, 지식이 된 적 없는 후보는 구간
    없이 탈락시킨다. 사람에게 둘을 구분해 묻지 않는 이유가 여기 있다 —
    상태가 이미 답을 갖고 있다.
    """
    claim_id = operation.claim_candidate_id
    if claim_id is None:
        raise ApplyOperationError("supersede_claim에 대상 claim이 없다")
    current = uow.knowledge_candidates.get_claim_validity(claim_id=claim_id)
    if current is None:
        raise ApplyOperationError(f"claim이 없다: {claim_id}")

    status, _valid_from, valid_to = current
    if status == AssertionResolutionStatus.SUPERSEDED:
        # 승인 이후 재추출이 이 후보를 은퇴시켰다. 여기서 구간을 닫으면
        # 지식이 된 적 없는 주장이 "한때 참이었다"로 남는다. 사람 결정도
        # 아니므로 탈락시키지도 않고 그대로 둔다.
        tally.skipped_superseded += 1
    elif valid_to is not None or status == "rejected":
        tally.closed_already += 1
    elif status == "pending":
        uow.knowledge_candidates.reject_claim(claim_id=claim_id)
        tally.invalidated += 1
    else:
        uow.knowledge_candidates.close_claim(
            claim_id=claim_id,
            valid_to=operation.operation_data["valid_to"],
        )
        tally.superseded += 1

    winner_raw = operation.operation_data.get("winner_claim_id")
    if winner_raw is None:
        return
    try:
        winner_id = uuid.UUID(str(winner_raw))
    except ValueError as error:
        raise ApplyOperationError(
            f"승자 claim id를 읽을 수 없다: {winner_raw}"
        ) from error
    # 승자가 아직 후보면 이 판정으로 확정된다. 이미 확정돼 있으면
    # 이 호출은 0을 돌려주고 아무것도 바꾸지 않는다.
    uow.knowledge_candidates.accept_claims(claim_ids=[winner_id])
