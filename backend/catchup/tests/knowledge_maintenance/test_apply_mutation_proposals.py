"""병합 Applier의 계약을 fake 저장소로 확인한다.

Applier는 결정 저널(approved)을 소비하는 결정론 실행기다. proposal
하나가 트랜잭션 하나이고, 실패는 격리되며, 재실행은 무동작이어야 한다.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from dataclasses import field
from types import TracebackType
from typing import Any
from typing import Self

from catchup.knowledge_maintenance.domain.knowledge_candidate import (
    EntityResolutionStatus,
)
from catchup.knowledge_maintenance.domain.knowledge_node import KnowledgeNode
from catchup.knowledge_maintenance.domain.knowledge_node import NodeKind
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

    def add_approved_merge(
        self,
        *,
        representative: uuid.UUID,
        members: tuple[uuid.UUID, ...],
        extra_operation: StoredOperation | None = None,
    ) -> uuid.UUID:
        proposal_id = uuid.uuid4()
        operations = [
            StoredOperation(
                sequence=1,
                operation_type="create_entity",
                entity_candidate_id=representative,
                claim_candidate_id=None,
                operation_data={
                    "proposed_type": "feature",
                    "proposed_name": "결제 기능",
                },
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
            "operations": tuple(operations),
            "applied_at": None,
        }
        return proposal_id


@dataclass
class FakeMutationRepo:
    state: FakeState

    def find_approved_proposals_with_operations(
        self, *, workspace_id: int
    ) -> list[tuple[uuid.UUID, tuple[StoredOperation, ...]]]:
        return [
            (proposal_id, row["operations"])
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


@dataclass
class FakeCandidateRepo:
    state: FakeState

    def get_entity_resolution(
        self, *, candidate_id: uuid.UUID
    ) -> tuple[str, uuid.UUID | None] | None:
        row = self.state.candidates.get(candidate_id)
        if row is None:
            return None
        return (row["resolution_status"], row["resolved_node_id"])

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
    ) -> None:
        row = self.state.candidates[candidate_id]
        if row["resolved_node_id"] is not None:
            raise AssertionError("이미 해소된 후보를 다시 해소하면 안 된다")
        row["resolution_status"] = status.value
        row["resolved_node_id"] = resolved_node_id


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
    ) -> KnowledgeNode:
        node = KnowledgeNode(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            node_kind=NodeKind.ENTITY,
            entity_type=entity_type,
            canonical_key=canonical_key,
            display_name=display_name,
        )
        self.state.nodes.append(node)
        return node


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

    def __enter__(self) -> Self:
        import copy

        self._snapshot = {
            "proposals": copy.deepcopy(self.state.proposals),
            "candidates": copy.deepcopy(self.state.candidates),
            "claim_rows": copy.deepcopy(self.state.claim_rows),
            "nodes": list(self.state.nodes),
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


def test_resolved_representative_is_reused() -> None:
    state = FakeState()
    existing_node = uuid.uuid4()
    representative = state.add_candidate(
        status="merged", resolved_node_id=existing_node
    )
    member = state.add_candidate()
    state.add_approved_merge(representative=representative, members=(member,))

    result, _ = _run(state)

    assert result.candidates_already_resolved == 1
    assert result.candidates_resolved == 1
    assert len(state.nodes) == 0
    assert state.candidates[member]["resolved_node_id"] == existing_node


def test_resolved_member_is_skipped() -> None:
    state = FakeState()
    representative = state.add_candidate()
    already = state.add_candidate(
        status="merged", resolved_node_id=uuid.uuid4()
    )
    state.add_approved_merge(
        representative=representative, members=(already,)
    )

    result, _ = _run(state)

    assert result.candidates_already_resolved == 1
    assert result.candidates_resolved == 1
    assert len(state.nodes) == 1


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


def test_supersede_without_claim_fails_that_proposal() -> None:
    """대상 claim이 없는 명령은 그 판정만 실패시킨다."""
    state = FakeState()
    winner = state.add_claim(status="accepted")
    _supersede_proposal(state, winner=winner, losers=(uuid.uuid4(),))

    result, _ = _run(state)

    assert result.proposals_failed == 1
    assert result.proposals_applied == 0
