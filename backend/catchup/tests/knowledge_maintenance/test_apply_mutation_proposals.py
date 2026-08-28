"""병합 Applier의 계약을 fake 저장소로 확인한다.

Applier는 결정 저널(approved)을 소비하는 결정론 실행기다. proposal
하나가 트랜잭션 하나이고, 실패는 격리되며, 재실행은 무동작이어야 한다.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from dataclasses import field
from types import TracebackType
from typing import Any
from typing import Self

from structlog.testing import capture_logs

from catchup.knowledge_maintenance.domain.entity_resolution import normalize_name
from catchup.knowledge_maintenance.domain.knowledge_candidate import (
    EntityResolutionConflict,
)
from catchup.knowledge_maintenance.domain.knowledge_candidate import (
    EntityResolutionStatus,
)
from catchup.knowledge_maintenance.domain.knowledge_node import KnowledgeNode
from catchup.knowledge_maintenance.domain.knowledge_node import NodeKind
from catchup.knowledge_maintenance.domain.knowledge_node import NodeLifecycleState
from catchup.knowledge_maintenance.ports.mutation_proposals import ApprovedProposal
from catchup.knowledge_maintenance.ports.mutation_proposals import StoredOperation
from catchup.knowledge_maintenance.services.apply_mutation_proposals import (
    apply_mutation_proposals,
)

WORKSPACE_ID = 1


@dataclass
class FakeState:
    """proposal·후보·노드를 한 곳에 둔 공유 상태다."""

    proposals: dict[uuid.UUID, dict[str, Any]] = field(default_factory=dict)
    candidates: dict[uuid.UUID, dict[str, Any]] = field(default_factory=dict)
    claim_rows: dict[uuid.UUID, dict[str, Any]] = field(default_factory=dict)
    nodes: list[KnowledgeNode] = field(default_factory=list)
    aliases: list[dict[str, Any]] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)
    # 사전 검사가 후보를 읽은 직후 그 후보를 다른 노드로 옮겨 두는 자리다.
    # 검사와 UPDATE 사이에 남이 끼어든 상황을 만든다.
    move_after_precheck: dict[uuid.UUID, uuid.UUID] = field(
        default_factory=dict
    )

    def add_claim(
        self,
        *,
        status: str = "accepted",
        valid_from: str | None = "2026-07-01T00:00:00+00:00",
        valid_to: str | None = None,
    ) -> uuid.UUID:
        claim_id = uuid.uuid4()
        self.claim_rows[claim_id] = {
            "resolution_status": status,
            "valid_from": valid_from,
            "valid_to": valid_to,
        }
        return claim_id

    def add_candidate(
        self,
        *,
        status: str = "pending",
        resolved_node_id: uuid.UUID | None = None,
    ) -> uuid.UUID:
        candidate_id = uuid.uuid4()
        self.candidates[candidate_id] = {
            "resolution_status": status,
            "resolved_node_id": resolved_node_id,
        }
        return candidate_id

    def add_node(
        self,
        *,
        lifecycle_state: NodeLifecycleState = NodeLifecycleState.ACTIVE,
    ) -> KnowledgeNode:
        """이미 서 있는 entity 노드를 하나 심는다."""
        node = KnowledgeNode(
            id=uuid.uuid4(),
            workspace_id=WORKSPACE_ID,
            node_kind=NodeKind.ENTITY,
            entity_type="feature",
            canonical_key=None,
            display_name="결제",
            lifecycle_state=lifecycle_state,
            merged_into_node_id=(
                uuid.uuid4()
                if lifecycle_state is NodeLifecycleState.MERGED
                else None
            ),
        )
        self.nodes.append(node)
        return node

    def add_approved_merge(
        self,
        *,
        representative: uuid.UUID,
        members: tuple[uuid.UUID, ...],
        extra_operation: StoredOperation | None = None,
        merge_into_node_id: uuid.UUID | None = None,
        reviewer: str = "cli",
        resolver_metadata: Mapping[str, Any] | None = None,
    ) -> uuid.UUID:
        proposal_id = uuid.uuid4()
        operation_data: dict[str, Any] = {
            "proposed_type": "feature",
            "proposed_name": "결제 기능",
        }
        if merge_into_node_id is not None:
            operation_data["merge_into_node_id"] = str(merge_into_node_id)
        operations = [
            StoredOperation(
                sequence=1,
                operation_type="create_entity",
                entity_candidate_id=representative,
                claim_candidate_id=None,
                operation_data=operation_data,
            )
        ]
        for offset, member in enumerate(members, start=2):
            operations.append(
                StoredOperation(
                    sequence=offset,
                    operation_type="merge_entity",
                    entity_candidate_id=member,
                    claim_candidate_id=None,
                    operation_data={"merge_into_sequence": 1},
                )
            )
        if extra_operation is not None:
            operations.append(extra_operation)
        self.proposals[proposal_id] = {
            "status": "approved",
            "proposal_kind": "duplicate",
            "reviewer": reviewer,
            "detector": "catchup.entity_duplicate",
            "detector_version": "1",
            "resolver_metadata": dict(
                {
                    "member_hash": "hash-1",
                    "member_names": ["결제", "결제 기능"],
                    "reason": "같은 대상이다",
                }
                if resolver_metadata is None
                else resolver_metadata
            ),
            "operations": tuple(operations),
            "applied_at": None,
        }
        return proposal_id


@dataclass
class FakeMutationRepo:
    state: FakeState

    def find_approved_proposals_with_operations(
        self, *, workspace_id: int
    ) -> list[ApprovedProposal]:
        return [
            ApprovedProposal(
                proposal_id=proposal_id,
                proposal_kind=row.get("proposal_kind", "duplicate"),
                reviewer=row.get("reviewer", "cli"),
                detector=row.get("detector", "catchup.entity_duplicate"),
                detector_version=row.get("detector_version", "1"),
                resolver_metadata=row.get("resolver_metadata", {}),
                operations=row["operations"],
            )
            for proposal_id, row in self.state.proposals.items()
            if row["status"] == "approved"
        ]

    def mark_applied(
        self, *, workspace_id: int, proposal_id: uuid.UUID
    ) -> None:
        row = self.state.proposals[proposal_id]
        if row["status"] != "approved":
            raise AssertionError("approved에서만 applied로 갈 수 있다")
        row["status"] = "applied"
        row["applied_at"] = "now"

    def mark_stale(self, *, workspace_id: int, proposal_id: uuid.UUID) -> None:
        row = self.state.proposals[proposal_id]
        if row["status"] != "approved":
            raise AssertionError("approved만 stale이 될 수 있다")
        row["status"] = "stale"


@dataclass
class FakeCandidateRepo:
    state: FakeState

    def get_entity_resolution(
        self, *, candidate_id: uuid.UUID
    ) -> tuple[str, uuid.UUID | None] | None:
        row = self.state.candidates.get(candidate_id)
        if row is None:
            return None
        current = (row["resolution_status"], row["resolved_node_id"])
        moved_to = self.state.move_after_precheck.pop(candidate_id, None)
        if moved_to is not None:
            row["resolution_status"] = EntityResolutionStatus.MERGED.value
            row["resolved_node_id"] = moved_to
        return current

    def get_claim_validity(
        self, *, claim_id: uuid.UUID
    ) -> tuple[str, Any, Any] | None:
        row = self.state.claim_rows.get(claim_id)
        if row is None:
            return None
        return (
            row["resolution_status"],
            row["valid_from"],
            row["valid_to"],
        )

    def close_claim(self, *, claim_id: uuid.UUID, valid_to: Any) -> None:
        row = self.state.claim_rows[claim_id]
        if row["valid_to"] is not None:
            raise AssertionError("이미 닫힌 구간을 다시 닫으면 안 된다")
        row["valid_to"] = valid_to

    def reject_claim(self, *, claim_id: uuid.UUID) -> None:
        row = self.state.claim_rows[claim_id]
        if row["resolution_status"] != "pending":
            raise AssertionError("pending만 탈락시킬 수 있다")
        row["resolution_status"] = "rejected"

    def accept_claims(self, *, claim_ids) -> int:
        accepted = 0
        for claim_id in claim_ids:
            row = self.state.claim_rows.get(claim_id)
            if row is not None and row["resolution_status"] == "pending":
                row["resolution_status"] = "accepted"
                accepted += 1
        return accepted

    def mark_entity_resolved(
        self,
        *,
        candidate_id: uuid.UUID,
        status: EntityResolutionStatus,
        resolved_node_id: uuid.UUID,
        expected_node_id: uuid.UUID | None,
    ) -> None:
        row = self.state.candidates[candidate_id]
        if row["resolved_node_id"] != expected_node_id:
            raise EntityResolutionConflict(
                f"후보의 해소 상태가 바뀌었다: {candidate_id}"
            )
        if expected_node_id is None and row["resolution_status"] != "pending":
            raise EntityResolutionConflict(
                f"후보가 더는 pending이 아니다: {candidate_id}"
            )
        row["resolution_status"] = status.value
        row["resolved_node_id"] = resolved_node_id

    def list_entity_candidate_ids_resolved_to(
        self, *, workspace_id: int, node_id: uuid.UUID
    ) -> tuple[uuid.UUID, ...]:
        return tuple(
            sorted(
                candidate_id
                for candidate_id, row in self.state.candidates.items()
                if row["resolved_node_id"] == node_id
            )
        )


@dataclass
class FakeNodeRepo:
    state: FakeState

    def create_entity_node(
        self,
        *,
        workspace_id: int,
        entity_type: str,
        canonical_key: str | None,
        display_name: str,
        attributes: Mapping[str, object] | None = None,
    ) -> KnowledgeNode:
        node = KnowledgeNode(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            node_kind=NodeKind.ENTITY,
            entity_type=entity_type,
            canonical_key=canonical_key,
            display_name=display_name,
            attributes=dict(attributes or {}),
        )
        self.state.nodes.append(node)
        return node

    def get_entity_by_id(
        self,
        *,
        workspace_id: int,
        node_id: uuid.UUID,
    ) -> KnowledgeNode | None:
        for node in self.state.nodes:
            if node.workspace_id == workspace_id and node.id == node_id:
                return node
        return None

    def lock_entity_node(
        self,
        *,
        workspace_id: int,
        node_id: uuid.UUID,
    ) -> KnowledgeNode | None:
        # 가짜 저장소에는 잠금이 없으므로 읽기와 같다. 실 어댑터는 같은
        # 행을 FOR UPDATE로 잠근 채 돌려준다.
        return self.get_entity_by_id(workspace_id=workspace_id, node_id=node_id)

    def add_alias(
        self,
        *,
        workspace_id: int,
        node_id: uuid.UUID,
        alias: str,
        normalized_alias: str,
        source: str,
    ) -> bool:
        # 실 DB의 (workspace_id, node_id, normalized_alias) UNIQUE를
        # 흉내 낸다. 중복이면 넣지 않고 거짓을 주는 것이 실 어댑터 계약이다.
        for row in self.state.aliases:
            if (
                row["workspace_id"] == workspace_id
                and row["node_id"] == node_id
                and row["normalized_alias"] == normalized_alias
            ):
                return False
        self.state.aliases.append(
            {
                "workspace_id": workspace_id,
                "node_id": node_id,
                "alias": alias,
                "normalized_alias": normalized_alias,
                "source": source,
            }
        )
        return True


@dataclass
class FakeResolutionEventRepo:
    """저널에 덧붙인 event를 공유 상태에 쌓아 둔다."""

    state: FakeState

    def record(
        self,
        *,
        workspace_id: int,
        event_id: uuid.UUID,
        event_type: str,
        decider: str,
        decider_id: str | None,
        node_id: uuid.UUID,
        member_hash: str,
        member_snapshot: Mapping[str, Any],
        basis: Mapping[str, Any],
        reverses_event_id: uuid.UUID | None = None,
    ) -> None:
        self.state.events.append(
            {
                "workspace_id": workspace_id,
                "event_id": event_id,
                "event_type": event_type,
                "decider": decider,
                "decider_id": decider_id,
                "node_id": node_id,
                "member_hash": member_hash,
                "member_snapshot": dict(member_snapshot),
                "basis": dict(basis),
                "reverses_event_id": reverses_event_id,
            }
        )


@dataclass
class FakeUnitOfWork:
    state: FakeState
    committed: int = 0
    rolled_back: int = 0
    _snapshot: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        self.mutation_proposals = FakeMutationRepo(self.state)
        self.knowledge_candidates = FakeCandidateRepo(self.state)
        self.knowledge_nodes = FakeNodeRepo(self.state)
        self.resolution_events = FakeResolutionEventRepo(self.state)

    def __enter__(self) -> Self:
        import copy

        self._snapshot = {
            "proposals": copy.deepcopy(self.state.proposals),
            "candidates": copy.deepcopy(self.state.candidates),
            "claim_rows": copy.deepcopy(self.state.claim_rows),
            "nodes": list(self.state.nodes),
            "aliases": copy.deepcopy(self.state.aliases),
            "events": list(self.state.events),
        }
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._snapshot is not None and self.committed == 0:
            # commit 없이 나가면 실 UoW처럼 전부 되감는다.
            self.state.proposals.clear()
            self.state.proposals.update(self._snapshot["proposals"])
            self.state.candidates.clear()
            self.state.candidates.update(self._snapshot["candidates"])
            self.state.claim_rows.clear()
            self.state.claim_rows.update(self._snapshot["claim_rows"])
            self.state.nodes[:] = self._snapshot["nodes"]
            self.state.aliases[:] = self._snapshot["aliases"]
            self.state.events[:] = self._snapshot["events"]
            self.rolled_back += 1

    def commit(self) -> None:
        self.committed += 1
        self._snapshot = None


def _run(state: FakeState):
    uows: list[FakeUnitOfWork] = []

    def factory() -> FakeUnitOfWork:
        uow = FakeUnitOfWork(state)
        uows.append(uow)
        return uow

    result = apply_mutation_proposals(factory, workspace_id=WORKSPACE_ID)
    return result, uows


def test_applies_create_and_merge() -> None:
    state = FakeState()
    representative = state.add_candidate()
    member = state.add_candidate()
    proposal_id = state.add_approved_merge(
        representative=representative, members=(member,)
    )

    result, _ = _run(state)

    assert result.proposals_applied == 1
    assert result.proposals_failed == 0
    assert result.candidates_resolved == 2
    assert len(state.nodes) == 1
    node = state.nodes[0]
    assert node.entity_type == "feature"
    assert node.display_name == "결제 기능"
    rep_row = state.candidates[representative]
    member_row = state.candidates[member]
    assert rep_row["resolution_status"] == "accepted"
    assert rep_row["resolved_node_id"] == node.id
    assert member_row["resolution_status"] == "merged"
    assert member_row["resolved_node_id"] == node.id
    assert state.proposals[proposal_id]["status"] == "applied"
    assert state.proposals[proposal_id]["applied_at"] is not None


def test_created_node_gets_name_alias() -> None:
    """새 노드는 제안된 이름으로 불릴 수 있어야 한다."""
    state = FakeState()
    representative = state.add_candidate()
    state.add_approved_merge(representative=representative, members=())

    _run(state)

    node = state.nodes[0]
    assert node.canonical_key is None
    assert state.aliases == [
        {
            "workspace_id": WORKSPACE_ID,
            "node_id": node.id,
            "alias": "결제 기능",
            "normalized_alias": normalize_name("결제 기능"),
            "source": "system",
        }
    ]


def test_alias_is_not_duplicated_on_rerun() -> None:
    """적용을 다시 돌려도 alias 행이 불어나지 않는다."""
    state = FakeState()
    representative = state.add_candidate()
    state.add_approved_merge(representative=representative, members=())

    _run(state)
    node_id = state.nodes[0].id
    # 같은 노드에 같은 이름을 다시 기록해도 무동작이어야 한다.
    FakeNodeRepo(state).add_alias(
        workspace_id=WORKSPACE_ID,
        node_id=node_id,
        alias="결제 기능",
        normalized_alias=normalize_name("결제 기능"),
        source="system",
    )
    _run(state)

    assert len(state.aliases) == 1


def test_unknown_operation_fails_only_that_proposal() -> None:
    state = FakeState()
    good_rep = state.add_candidate()
    good_member = state.add_candidate()
    good_id = state.add_approved_merge(
        representative=good_rep, members=(good_member,)
    )

    bad_rep = state.add_candidate()
    bad_id = state.add_approved_merge(
        representative=bad_rep,
        members=(),
        extra_operation=StoredOperation(
            sequence=9,
            operation_type="invalidate_claim",
            entity_candidate_id=None,
            claim_candidate_id=None,
            operation_data={},
        ),
    )

    result, _ = _run(state)

    assert result.proposals_applied == 1
    assert result.proposals_failed == 1
    assert state.proposals[good_id]["status"] == "applied"
    # 실패한 proposal은 approved로 남아 재시도할 수 있고, 그 proposal이
    # 만들던 노드·해소는 전부 되감겨야 한다.
    assert state.proposals[bad_id]["status"] == "approved"
    assert state.candidates[bad_rep]["resolved_node_id"] is None
    assert len(state.nodes) == 1


def test_rerun_is_noop() -> None:
    state = FakeState()
    representative = state.add_candidate()
    member = state.add_candidate()
    state.add_approved_merge(representative=representative, members=(member,))

    apply_mutation_proposals(
        lambda: FakeUnitOfWork(state), workspace_id=WORKSPACE_ID
    )
    result = apply_mutation_proposals(
        lambda: FakeUnitOfWork(state), workspace_id=WORKSPACE_ID
    )

    assert result.proposals_applied == 0
    assert result.proposals_failed == 0
    assert result.candidates_resolved == 0
    assert len(state.nodes) == 1


def test_apply_single_proposal_only_touches_target() -> None:
    """안건 하나를 지정하면 그 안건만 적용되고 다른 승인은 남는다."""
    state = FakeState()
    target_rep = state.add_candidate()
    target_id = state.add_approved_merge(
        representative=target_rep, members=()
    )
    other_rep = state.add_candidate()
    other_id = state.add_approved_merge(representative=other_rep, members=())

    result = apply_mutation_proposals(
        lambda: FakeUnitOfWork(state),
        workspace_id=WORKSPACE_ID,
        proposal_id=target_id,
    )

    assert result.proposals_applied == 1
    assert result.candidates_resolved == 1
    assert state.proposals[target_id]["status"] == "applied"
    # 지정되지 않은 승인은 결정 저널에 그대로 남아 다음 적용을 기다린다.
    assert state.proposals[other_id]["status"] == "approved"
    assert state.candidates[other_rep]["resolved_node_id"] is None
    assert len(state.nodes) == 1


def test_apply_unknown_proposal_applies_nothing() -> None:
    """승인 목록에 없는 안건을 지정하면 0건 적용으로 끝난다.

    실패로 세지 않는다. 없는 안건은 적용이 실패한 것이 아니라 적용할
    것이 없는 것이고, 404를 낼지는 라우터가 적용 건수로 판단한다.
    """
    state = FakeState()
    representative = state.add_candidate()
    approved_id = state.add_approved_merge(
        representative=representative, members=()
    )

    result = apply_mutation_proposals(
        lambda: FakeUnitOfWork(state),
        workspace_id=WORKSPACE_ID,
        proposal_id=uuid.uuid4(),
    )

    assert result.proposals_applied == 0
    assert result.proposals_failed == 0
    assert state.proposals[approved_id]["status"] == "approved"
    assert len(state.nodes) == 0


def _completion_log(logs: list[dict[str, Any]]) -> dict[str, Any]:
    """적용 한 번의 마무리 감사 기록 하나를 골라낸다."""
    entries = [log for log in logs if log["event"] == "mutation_apply_completed"]
    assert len(entries) == 1
    return entries[0]


def test_apply_all_logs_no_scope_even_with_many_approved() -> None:
    """전체 적용은 승인이 여러 건이어도 범위를 비워 기록한다.

    이 필드는 감사 기록에서 "전체 적용"과 "한 건 골라 적용"을 가르는
    유일한 표시다. 마지막으로 처리한 안건의 id가 새면 전체 적용이
    한 건 적용처럼 남는다.
    """
    state = FakeState()
    first = state.add_approved_merge(
        representative=state.add_candidate(), members=()
    )
    second = state.add_approved_merge(
        representative=state.add_candidate(), members=()
    )

    with capture_logs() as logs:
        result = apply_mutation_proposals(
            lambda: FakeUnitOfWork(state), workspace_id=WORKSPACE_ID
        )

    assert result.proposals_applied == 2
    entry = _completion_log(logs)
    assert entry["scoped_proposal_id"] is None
    assert entry["proposals_applied"] == 2
    assert state.proposals[first]["status"] == "applied"
    assert state.proposals[second]["status"] == "applied"


def test_apply_single_proposal_logs_that_scope() -> None:
    """한 건을 지정하면 그 id가 문자열로 기록된다."""
    state = FakeState()
    target_id = state.add_approved_merge(
        representative=state.add_candidate(), members=()
    )
    state.add_approved_merge(
        representative=state.add_candidate(), members=()
    )

    with capture_logs() as logs:
        result = apply_mutation_proposals(
            lambda: FakeUnitOfWork(state),
            workspace_id=WORKSPACE_ID,
            proposal_id=target_id,
        )

    assert result.proposals_applied == 1
    entry = _completion_log(logs)
    assert entry["scoped_proposal_id"] == str(target_id)


def _supersede_proposal(
    state: FakeState,
    *,
    winner: uuid.UUID,
    losers: tuple[uuid.UUID, ...],
    valid_to: str = "2026-07-20T00:00:00+00:00",
) -> uuid.UUID:
    """승인된 모순 판정 하나를 명령까지 갖춰 만든다."""
    proposal_id = uuid.uuid4()
    state.proposals[proposal_id] = {
        "status": "approved",
        "proposal_kind": "contradiction",
        "reviewer": "cli",
        "detector": "catchup.claim_conflict",
        "detector_version": "1",
        "resolver_metadata": {},
        "operations": tuple(
            StoredOperation(
                sequence=index,
                operation_type="supersede_claim",
                entity_candidate_id=None,
                claim_candidate_id=loser,
                operation_data={
                    "winner_claim_id": str(winner),
                    "valid_to": valid_to,
                },
            )
            for index, loser in enumerate(losers, start=1)
        ),
        "applied_at": None,
    }
    return proposal_id


def test_supersede_closes_accepted_loser() -> None:
    """받아들여진 패자는 상태를 지키고 구간만 닫힌다."""
    state = FakeState()
    winner = state.add_claim(status="accepted")
    loser = state.add_claim(status="accepted")
    _supersede_proposal(state, winner=winner, losers=(loser,))

    result, _ = _run(state)

    assert result.claims_superseded == 1
    assert result.claims_invalidated == 0
    row = state.claim_rows[loser]
    assert row["resolution_status"] == "accepted"
    assert row["valid_to"] == "2026-07-20T00:00:00+00:00"


def test_supersede_rejects_pending_loser() -> None:
    """지식이 된 적 없는 패자는 구간 없이 탈락한다."""
    state = FakeState()
    winner = state.add_claim(status="accepted")
    loser = state.add_claim(status="pending")
    _supersede_proposal(state, winner=winner, losers=(loser,))

    result, _ = _run(state)

    assert result.claims_invalidated == 1
    assert result.claims_superseded == 0
    row = state.claim_rows[loser]
    assert row["resolution_status"] == "rejected"
    assert row["valid_to"] is None


def test_supersede_skips_already_closed_and_rejected() -> None:
    """이미 닫혔거나 탈락한 패자는 건드리지 않는다."""
    state = FakeState()
    winner = state.add_claim(status="accepted")
    closed = state.add_claim(status="accepted", valid_to="2026-06-01")
    rejected = state.add_claim(status="rejected")
    _supersede_proposal(state, winner=winner, losers=(closed, rejected))

    result, _ = _run(state)

    assert result.claims_already_closed == 2
    assert result.claims_superseded == 0
    assert result.claims_invalidated == 0
    assert state.claim_rows[closed]["valid_to"] == "2026-06-01"


def test_supersede_promotes_pending_winner() -> None:
    """아직 후보인 승자는 이 판정으로 확정된다."""
    state = FakeState()
    winner = state.add_claim(status="pending")
    loser = state.add_claim(status="accepted")
    _supersede_proposal(state, winner=winner, losers=(loser,))

    _run(state)

    assert state.claim_rows[winner]["resolution_status"] == "accepted"


def test_supersede_is_idempotent() -> None:
    """재실행은 아무것도 바꾸지 않는다."""
    state = FakeState()
    winner = state.add_claim(status="accepted")
    loser = state.add_claim(status="accepted")
    _supersede_proposal(state, winner=winner, losers=(loser,))

    _run(state)
    second, _ = _run(state)

    assert second.proposals_applied == 0
    assert second.claims_superseded == 0


def test_supersede_skips_superseded_loser() -> None:
    """승인 뒤 재추출이 은퇴시킨 패자는 닫지도 탈락시키지도 않는다.

    은퇴한 후보는 지식이 된 적이 없다. 여기에 valid_to를 찍으면 "한때
    참이었다"가 없던 일로 만들어진다.
    """
    state = FakeState()
    winner = state.add_claim(status="accepted")
    loser = state.add_claim(status="superseded")
    _supersede_proposal(state, winner=winner, losers=(loser,))

    result, _ = _run(state)

    assert result.proposals_applied == 1
    assert result.claims_skipped_superseded == 1
    assert result.claims_superseded == 0
    assert result.claims_invalidated == 0
    assert result.claims_already_closed == 0
    row = state.claim_rows[loser]
    assert row["resolution_status"] == "superseded"
    assert row["valid_to"] is None


def test_supersede_without_claim_fails_that_proposal() -> None:
    """대상 claim이 없는 명령은 그 판정만 실패시킨다."""
    state = FakeState()
    winner = state.add_claim(status="accepted")
    _supersede_proposal(state, winner=winner, losers=(uuid.uuid4(),))

    result, _ = _run(state)

    assert result.proposals_failed == 1
    assert result.proposals_applied == 0


def test_merge_into_existing_node_reuses_that_node() -> None:
    """기존 노드로 붙이는 결정은 노드를 새로 만들지 않는다."""
    state = FakeState()
    existing = state.add_node()
    representative = state.add_candidate()
    member = state.add_candidate()
    state.add_approved_merge(
        representative=representative,
        members=(member,),
        merge_into_node_id=existing.id,
    )

    result, _ = _run(state)

    assert result.proposals_applied == 1
    assert result.candidates_resolved == 2
    # 심어 둔 노드 하나 그대로다.
    assert [node.id for node in state.nodes] == [existing.id]
    assert state.candidates[representative] == {
        "resolution_status": EntityResolutionStatus.MERGED,
        "resolved_node_id": existing.id,
    }
    assert state.candidates[member]["resolved_node_id"] == existing.id
    # 이번에 확인된 이름으로도 그 노드를 부를 수 있어야 한다.
    assert state.aliases == [
        {
            "workspace_id": WORKSPACE_ID,
            "node_id": existing.id,
            "alias": "결제 기능",
            "normalized_alias": normalize_name("결제 기능"),
            "source": "system",
        }
    ]


def test_merge_into_node_records_human_resolution_event() -> None:
    """사람이 승인한 병합은 붙인 노드로 event 한 건을 남긴다."""
    state = FakeState()
    existing = state.add_node()
    representative = state.add_candidate()
    member = state.add_candidate()
    state.add_approved_merge(
        representative=representative,
        members=(member,),
        merge_into_node_id=existing.id,
        reviewer="cli",
        resolver_metadata={
            "member_hash": "hash-merge",
            "member_names": ["결제", "결제 기능"],
            "reason": "같은 대상이다",
        },
    )

    result, _ = _run(state)

    assert result.proposals_applied == 1
    assert len(state.events) == 1
    event = state.events[0]
    assert event["event_type"] == "merge_into_node"
    assert event["decider"] == "human"
    assert event["decider_id"] == "cli"
    assert event["node_id"] == existing.id
    assert event["member_hash"] == "hash-merge"
    assert event["reverses_event_id"] is None
    snapshot = event["member_snapshot"]
    assert snapshot["representative_candidate_id"] == str(representative)
    assert snapshot["member_candidate_ids"] == [str(member)]
    assert snapshot["member_names"] == ["결제", "결제 기능"]
    assert snapshot["proposed_name"] == "결제 기능"
    assert snapshot["proposed_type"] == "feature"
    assert snapshot["merge_into_node_id"] == str(existing.id)
    assert snapshot["aliases_added"] == ["결제 기능"]
    assert snapshot["applied_members"] == [
        {"candidate_id": str(representative), "name": "결제"},
        {"candidate_id": str(member), "name": "결제 기능"},
    ]
    assert event["basis"]["detector"] == "catchup.entity_duplicate"
    assert event["basis"]["detector_version"] == "1"
    assert event["basis"]["reason"] == "같은 대상이다"


def test_merge_into_node_with_existing_alias_records_no_alias() -> None:
    """이미 같은 이름이 붙어 있던 노드로의 병합은 별칭을 제 것으로 적지 않는다.

    시도만 적으면 같은 이름의 두 번째 병합이 앞 병합의 별칭을 자기 것으로
    적고, 그 되돌림이 앞 병합이 붙인 이름을 지운다.
    """
    state = FakeState()
    existing = state.add_node()
    FakeNodeRepo(state).add_alias(
        workspace_id=WORKSPACE_ID,
        node_id=existing.id,
        alias="결제 기능",
        normalized_alias=normalize_name("결제 기능"),
        source="system",
    )
    representative = state.add_candidate()
    member = state.add_candidate()
    state.add_approved_merge(
        representative=representative,
        members=(member,),
        merge_into_node_id=existing.id,
        resolver_metadata={"member_hash": "hash-merge"},
    )

    result, _ = _run(state)

    assert result.proposals_applied == 1
    assert len(state.aliases) == 1
    assert state.events[0]["member_snapshot"]["aliases_added"] == []


def test_resolution_event_basis_carries_model_and_prompt_version() -> None:
    """판정 근거에 실린 모델과 프롬프트 판본이 event basis까지 간다."""
    state = FakeState()
    representative = state.add_candidate()
    member = state.add_candidate()
    state.add_approved_merge(
        representative=representative,
        members=(member,),
        resolver_metadata={
            "member_hash": "hash-merge",
            "model_id": "fake-judge-model",
            "prompt_version": "partition_entity_block.j2@fake",
        },
    )

    _run(state)

    basis = state.events[0]["basis"]
    assert basis["model_id"] == "fake-judge-model"
    assert basis["prompt_version"] == "partition_entity_block.j2@fake"


def test_new_node_merge_records_system_resolution_event() -> None:
    """자동 승인은 사람 없이 정해진 확정으로 남는다."""
    state = FakeState()
    representative = state.add_candidate()
    member = state.add_candidate()
    state.add_approved_merge(
        representative=representative,
        members=(member,),
        reviewer="system:auto_merge",
    )

    result, _ = _run(state)

    assert result.proposals_applied == 1
    assert len(state.events) == 1
    event = state.events[0]
    assert event["event_type"] == "merge_create_node"
    assert event["decider"] == "system"
    assert event["decider_id"] is None
    assert event["node_id"] == state.nodes[0].id
    assert event["member_snapshot"]["merge_into_node_id"] is None


def test_merge_without_member_hash_fails_that_proposal() -> None:
    """member_hash가 없는 병합은 저널 없이 적용되지 않는다."""
    state = FakeState()
    representative = state.add_candidate()
    member = state.add_candidate()
    proposal_id = state.add_approved_merge(
        representative=representative,
        members=(member,),
        resolver_metadata={"reason": "같은 대상이다"},
    )

    result, _ = _run(state)

    assert result.proposals_applied == 0
    assert result.proposals_failed == 1
    assert state.events == []
    assert state.proposals[proposal_id]["status"] == "approved"
    assert state.candidates[representative]["resolved_node_id"] is None
    assert state.candidates[member]["resolved_node_id"] is None
    assert state.nodes == []


def test_contradiction_apply_records_no_resolution_event() -> None:
    """모순 판정의 적용은 해소 저널을 건드리지 않는다."""
    state = FakeState()
    winner = state.add_claim(status="accepted")
    loser = state.add_claim(status="accepted")
    _supersede_proposal(state, winner=winner, losers=(loser,))

    result, _ = _run(state)

    assert result.proposals_applied == 1
    assert state.events == []




def _assert_stale_and_untouched(
    state: FakeState, proposal_id: uuid.UUID, result
) -> None:
    """stale 안건은 아무것도 바꾸지 않는다. 노드도 event도 생기지 않고 후보도 그대로다."""
    assert result.proposals_stale == 1
    assert result.proposals_applied == 0
    assert result.proposals_failed == 0
    assert state.proposals[proposal_id]["status"] == "stale"
    assert state.events == []


def test_resolved_representative_makes_the_proposal_stale() -> None:
    """대표가 승인 뒤 다른 노드에 해소돼 있으면 안건 전체가 stale이다.

    대표만 건너뛰고 나머지를 그 노드로 붙이면 사람이나 judge가 승인한
    "이 구성끼리 같다"가 "저 노드와 같다"로 바뀐다.
    """
    state = FakeState()
    existing = state.add_node()
    representative = state.add_candidate(
        status="merged", resolved_node_id=existing.id
    )
    member = state.add_candidate()
    proposal_id = state.add_approved_merge(
        representative=representative, members=(member,)
    )

    result, _ = _run(state)

    _assert_stale_and_untouched(state, proposal_id, result)
    assert state.candidates[member]["resolved_node_id"] is None
    assert len(state.nodes) == 1


def test_resolved_member_makes_the_proposal_stale() -> None:
    state = FakeState()
    foreign = state.add_node()
    representative = state.add_candidate()
    member = state.add_candidate(status="merged", resolved_node_id=foreign.id)
    proposal_id = state.add_approved_merge(
        representative=representative, members=(member,)
    )

    result, _ = _run(state)

    _assert_stale_and_untouched(state, proposal_id, result)
    assert state.candidates[representative]["resolved_node_id"] is None
    assert len(state.nodes) == 1


def test_superseded_member_makes_the_proposal_stale() -> None:
    """재추출이 멤버를 은퇴시켰으면 그 구성은 더 이상 존재하지 않는다."""
    state = FakeState()
    representative = state.add_candidate()
    member = state.add_candidate(status="superseded")
    proposal_id = state.add_approved_merge(
        representative=representative, members=(member,)
    )

    result, _ = _run(state)

    _assert_stale_and_untouched(state, proposal_id, result)


def test_candidate_moved_after_precheck_makes_the_proposal_stale() -> None:
    """사전 검사 뒤 후보가 다른 노드로 옮겨졌으면 안건이 stale이다.

    검사와 UPDATE가 원자적이지 않아 그 사이에 다른 결정이 같은 후보를
    가져갈 수 있다. 저장소가 기대한 상태와 다르면 갱신하지 않고
    EntityResolutionConflict를 내므로, 적용은 그 안건을 stale로 끝낸다.
    """
    state = FakeState()
    existing = state.add_node()
    other = state.add_node()
    representative = state.add_candidate()
    member = state.add_candidate()
    state.move_after_precheck[representative] = other.id
    proposal_id = state.add_approved_merge(
        representative=representative,
        members=(member,),
        merge_into_node_id=existing.id,
    )

    result, _ = _run(state)

    _assert_stale_and_untouched(state, proposal_id, result)
    # 새 노드는 서지 않고 후보도 이 안건 때문에 옮겨지지 않는다. 가짜
    # UoW가 트랜잭션 전체를 되감으므로 끼어든 갱신도 함께 되감긴다.
    assert len(state.nodes) == 2
    assert state.candidates[representative]["resolved_node_id"] is None
    assert state.candidates[member]["resolved_node_id"] is None


def test_merge_into_inactive_node_makes_the_proposal_stale() -> None:
    """승인 뒤 대상 노드가 흡수·퇴역했으면 실행할 수 없다. 노드를 새로 만들지 않는다."""
    state = FakeState()
    target = state.add_node(lifecycle_state=NodeLifecycleState.MERGED)
    representative = state.add_candidate()
    proposal_id = state.add_approved_merge(
        representative=representative, members=(), merge_into_node_id=target.id
    )

    result, _ = _run(state)

    _assert_stale_and_untouched(state, proposal_id, result)
    assert state.candidates[representative]["resolved_node_id"] is None
    assert [node.id for node in state.nodes] == [target.id]


def test_merge_into_missing_node_makes_the_proposal_stale() -> None:
    """대상 노드가 아예 없으면 안건은 stale이다. 노드를 새로 만들지 않는다."""
    state = FakeState()
    representative = state.add_candidate()
    proposal_id = state.add_approved_merge(
        representative=representative,
        members=(),
        merge_into_node_id=uuid.uuid4(),
    )

    result, _ = _run(state)

    _assert_stale_and_untouched(state, proposal_id, result)
    assert state.candidates[representative]["resolved_node_id"] is None
    assert state.nodes == []


def test_missing_candidate_row_fails_that_proposal() -> None:
    """후보 행이 없는 안건은 결함이라 stale이 아니라 실패로 남는다."""
    state = FakeState()
    representative = state.add_candidate()
    proposal_id = state.add_approved_merge(
        representative=representative, members=()
    )
    del state.candidates[representative]

    result, _ = _run(state)

    assert result.proposals_failed == 1
    assert result.proposals_applied == 0
    assert result.proposals_stale == 0
    assert state.proposals[proposal_id]["status"] == "approved"
    assert state.nodes == []
    assert state.events == []


def test_stale_proposal_does_not_block_the_next_one() -> None:
    """stale 안건은 자기 트랜잭션에서 끝나고 다음 안건은 정상 적용된다."""
    state = FakeState()
    foreign = state.add_node()
    stale_rep = state.add_candidate(
        status="merged", resolved_node_id=foreign.id
    )
    stale_member = state.add_candidate()
    stale_id = state.add_approved_merge(
        representative=stale_rep, members=(stale_member,)
    )
    representative = state.add_candidate()
    member = state.add_candidate()
    state.add_approved_merge(
        representative=representative,
        members=(member,),
        resolver_metadata={
            "member_hash": "hash-2",
            "member_names": ["결제", "결제 기능"],
        },
    )

    result, _ = _run(state)

    assert result.proposals_stale == 1
    assert result.proposals_applied == 1
    assert state.proposals[stale_id]["status"] == "stale"
    assert len(state.events) == 1


def test_resolution_event_records_node_candidate_ids_after() -> None:
    """event에는 적용 직후 그 노드를 가리키는 후보 전부가 적힌다.

    기존 노드에 붙이는 병합이면 원래 붙어 있던 후보도 함께 들어간다.
    되돌림은 이 목록과 현재를 견줘 그 뒤 노드에 아무 일도 없었는지 본다.
    """
    state = FakeState()
    target = state.add_node()
    earlier = state.add_candidate(status="merged", resolved_node_id=target.id)
    representative = state.add_candidate()
    member = state.add_candidate()
    state.add_approved_merge(
        representative=representative,
        members=(member,),
        merge_into_node_id=target.id,
    )

    result, _ = _run(state)

    assert result.proposals_applied == 1
    snapshot = state.events[0]["member_snapshot"]
    assert snapshot["node_candidate_ids_after"] == sorted(
        str(candidate_id)
        for candidate_id in (earlier, representative, member)
    )
    assert snapshot["applied_members"] == [
        {"candidate_id": str(representative), "name": "결제"},
        {"candidate_id": str(member), "name": "결제 기능"},
    ]
