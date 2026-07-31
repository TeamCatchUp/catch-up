"""모순 승자 결정의 규칙을 fake 저장소로 확인한다.

사람이 답하는 것은 "어느 값이 맞나" 하나뿐이고, 나머지는 전부 기계가
유도한다 — 패자 목록, 구간을 닫을 시각, 적용 명령까지. 그래서 이
서비스의 검증은 승자가 정말 그 안건의 값 후보인지에 걸려 있다.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from dataclasses import field
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from types import TracebackType
from typing import Any
from typing import Self

import pytest

from catchup.knowledge_maintenance.ports.mutation_proposals import (
    MergeProposalAlreadyDecided,
)
from catchup.knowledge_maintenance.ports.mutation_proposals import (
    StoredContradictionProposal,
)
from catchup.knowledge_maintenance.ports.mutation_proposals import (
    StoredContradictionValue,
)
from catchup.knowledge_maintenance.services.review_contradiction_proposal import (
    ContradictionReviewError,
)
from catchup.knowledge_maintenance.services.review_contradiction_proposal import (
    review_contradiction_proposal,
)

WORKSPACE_ID = 1
DECIDED_AT = datetime(2026, 7, 31, 9, 0, tzinfo=UTC)
EARLY = datetime(2026, 7, 1, tzinfo=UTC)
LATER = datetime(2026, 7, 20, tzinfo=UTC)


@dataclass
class FakeState:
    proposals: dict[uuid.UUID, dict[str, Any]] = field(default_factory=dict)
    claims: dict[uuid.UUID, dict[str, Any]] = field(default_factory=dict)
    operations: dict[uuid.UUID, list[dict[str, Any]]] = field(
        default_factory=dict
    )

    def add_claim(
        self,
        *,
        status: str = "accepted",
        valid_from: datetime | None = EARLY,
        valid_to: datetime | None = None,
    ) -> uuid.UUID:
        claim_id = uuid.uuid4()
        self.claims[claim_id] = {
            "resolution_status": status,
            "valid_from": valid_from,
            "valid_to": valid_to,
        }
        return claim_id

    def add_contradiction(
        self,
        *,
        claim_ids: tuple[uuid.UUID, ...],
        status: str = "pending",
    ) -> uuid.UUID:
        proposal_id = uuid.uuid4()
        self.proposals[proposal_id] = {
            "id": proposal_id,
            "status": status,
            "predicate": "rate_limit_per_minute",
            "subject_key": "node:abc",
            "summary": "값이 2종으로 갈린다",
            "reviewer": None,
            "decision": None,
            "values": tuple(
                StoredContradictionValue(
                    claim_id=claim_id,
                    value=60 + index,
                    normalized=str(60 + index),
                    statement=f"주장 {index}",
                    observed_at="2026-07-29T00:00:00+00:00",
                )
                for index, claim_id in enumerate(claim_ids)
            ),
        }
        self.operations[proposal_id] = []
        return proposal_id


@dataclass
class FakeMutationRepo:
    state: FakeState

    def list_pending_contradictions(
        self, *, workspace_id: int
    ) -> list[StoredContradictionProposal]:
        return [
            StoredContradictionProposal(
                id=row["id"],
                predicate=row["predicate"],
                subject_key=row["subject_key"],
                summary=row["summary"],
                values=row["values"],
            )
            for row in self.state.proposals.values()
            if row["status"] == "pending"
        ]

    def record_contradiction_decision(
        self,
        *,
        workspace_id: int,
        proposal_id: uuid.UUID,
        decision: dict[str, Any],
        supersede_targets: list[tuple[uuid.UUID, dict[str, Any]]],
        reviewer: str,
    ) -> None:
        row = self.state.proposals.get(proposal_id)
        if row is None or row["status"] != "pending":
            raise MergeProposalAlreadyDecided(str(proposal_id))
        row["status"] = "approved"
        row["reviewer"] = reviewer
        row["decision"] = decision
        self.state.operations[proposal_id] = [
            {
                "sequence": index,
                "operation_type": "supersede_claim",
                "claim_candidate_id": claim_id,
                "operation_data": data,
            }
            for index, (claim_id, data) in enumerate(
                supersede_targets, start=1
            )
        ]


@dataclass
class FakeCandidateRepo:
    state: FakeState

    def get_claim_validity(
        self, *, claim_id: uuid.UUID
    ) -> tuple[str, datetime | None, datetime | None] | None:
        row = self.state.claims.get(claim_id)
        if row is None:
            return None
        return (
            row["resolution_status"],
            row["valid_from"],
            row["valid_to"],
        )


@dataclass
class FakeUnitOfWork:
    state: FakeState
    committed: int = 0

    def __post_init__(self) -> None:
        self.mutation_proposals = FakeMutationRepo(self.state)
        self.knowledge_candidates = FakeCandidateRepo(self.state)

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None

    def commit(self) -> None:
        self.committed += 1


def _resolve(
    uow: FakeUnitOfWork,
    proposal_id: uuid.UUID,
    winner_claim_id: uuid.UUID,
):
    return review_contradiction_proposal(
        uow,
        workspace_id=WORKSPACE_ID,
        proposal_id=proposal_id,
        winner_claim_id=winner_claim_id,
        reviewer="ba2slk",
        now=DECIDED_AT,
    )


def test_records_decision_and_supersede_operations() -> None:
    state = FakeState()
    winner = state.add_claim(valid_from=LATER)
    loser_one = state.add_claim(valid_from=EARLY)
    loser_two = state.add_claim(valid_from=EARLY)
    proposal_id = state.add_contradiction(
        claim_ids=(winner, loser_one, loser_two)
    )
    uow = FakeUnitOfWork(state)

    result = _resolve(uow, proposal_id, winner)

    row = state.proposals[proposal_id]
    assert row["status"] == "approved"
    assert row["reviewer"] == "ba2slk"
    assert result.winner_claim_id == winner
    assert set(result.loser_claim_ids) == {loser_one, loser_two}
    assert result.valid_to == LATER
    assert result.valid_to_source == "winner_valid_from"
    decision = row["decision"]
    assert decision["winner_claim_id"] == str(winner)
    assert set(decision["loser_claim_ids"]) == {
        str(loser_one),
        str(loser_two),
    }
    operations = state.operations[proposal_id]
    assert [operation["sequence"] for operation in operations] == [1, 2]
    assert {
        operation["claim_candidate_id"] for operation in operations
    } == {loser_one, loser_two}
    assert operations[0]["operation_data"]["valid_to"] == LATER.isoformat()
    assert uow.committed == 1


def test_winner_outside_proposal_is_refused() -> None:
    state = FakeState()
    first = state.add_claim()
    second = state.add_claim()
    stranger = state.add_claim()
    proposal_id = state.add_contradiction(claim_ids=(first, second))
    uow = FakeUnitOfWork(state)

    with pytest.raises(ContradictionReviewError):
        _resolve(uow, proposal_id, stranger)

    assert state.proposals[proposal_id]["status"] == "pending"
    assert state.operations[proposal_id] == []


def test_unknown_proposal_is_refused() -> None:
    state = FakeState()
    uow = FakeUnitOfWork(state)

    with pytest.raises(ContradictionReviewError):
        _resolve(uow, uuid.uuid4(), uuid.uuid4())


def test_decided_proposal_is_refused() -> None:
    state = FakeState()
    winner = state.add_claim()
    loser = state.add_claim()
    proposal_id = state.add_contradiction(
        claim_ids=(winner, loser), status="approved"
    )
    uow = FakeUnitOfWork(state)

    with pytest.raises(ContradictionReviewError):
        _resolve(uow, proposal_id, winner)


def test_valid_to_falls_back_when_winner_has_no_valid_from() -> None:
    state = FakeState()
    winner = state.add_claim(valid_from=None)
    loser = state.add_claim(valid_from=EARLY)
    proposal_id = state.add_contradiction(claim_ids=(winner, loser))
    uow = FakeUnitOfWork(state)

    result = _resolve(uow, proposal_id, winner)

    assert result.valid_to == DECIDED_AT
    assert result.valid_to_source == "decision_time"
    decision = state.proposals[proposal_id]["decision"]
    assert decision["valid_to_source"] == "decision_time"


def test_valid_to_falls_back_when_winner_precedes_loser() -> None:
    """승자가 패자보다 앞서면 구간이 뒤집히므로 결정 시각으로 닫는다."""
    state = FakeState()
    winner = state.add_claim(valid_from=EARLY)
    loser = state.add_claim(valid_from=LATER)
    proposal_id = state.add_contradiction(claim_ids=(winner, loser))
    uow = FakeUnitOfWork(state)

    result = _resolve(uow, proposal_id, winner)

    assert result.valid_to == DECIDED_AT
    assert result.valid_to_source == "decision_time"


def test_valid_to_uses_winner_when_it_follows_every_loser() -> None:
    state = FakeState()
    winner = state.add_claim(valid_from=LATER)
    loser = state.add_claim(valid_from=EARLY)
    other = state.add_claim(valid_from=EARLY + timedelta(days=1))
    proposal_id = state.add_contradiction(claim_ids=(winner, loser, other))
    uow = FakeUnitOfWork(state)

    result = _resolve(uow, proposal_id, winner)

    assert result.valid_to == LATER
    assert result.valid_to_source == "winner_valid_from"


def test_holding_changes_nothing() -> None:
    """보류는 이 서비스를 부르지 않는 것이라 상태가 그대로다."""
    state = FakeState()
    winner = state.add_claim()
    loser = state.add_claim()
    proposal_id = state.add_contradiction(claim_ids=(winner, loser))

    row = state.proposals[proposal_id]
    assert row["status"] == "pending"
    assert row["decision"] is None
    assert state.operations[proposal_id] == []


def test_blank_reviewer_is_refused() -> None:
    state = FakeState()
    winner = state.add_claim()
    loser = state.add_claim()
    proposal_id = state.add_contradiction(claim_ids=(winner, loser))
    uow = FakeUnitOfWork(state)

    with pytest.raises(ContradictionReviewError):
        review_contradiction_proposal(
            uow,
            workspace_id=WORKSPACE_ID,
            proposal_id=proposal_id,
            winner_claim_id=winner,
            reviewer="   ",
            now=DECIDED_AT,
        )
