from __future__ import annotations

import hashlib
import uuid
from dataclasses import replace
from datetime import datetime
from datetime import timedelta
from datetime import timezone

from structlog.testing import capture_logs

from catchup.knowledge_maintenance.contracts.extraction import ExtractionVocabulary
from catchup.knowledge_maintenance.contracts.extraction import PredicateEntry
from catchup.knowledge_maintenance.domain.claim_conflict import StoredClaimCandidate
from catchup.knowledge_maintenance.domain.knowledge_candidate import (
    StoredMutationProposal,
)
from catchup.knowledge_maintenance.services.resolve_claim_conflicts import (
    conflict_idempotency_key,
)
from catchup.knowledge_maintenance.services.resolve_claim_conflicts import (
    resolve_claim_conflicts,
)

NOW = datetime(2026, 7, 29, 9, 0, tzinfo=timezone.utc)
WORKSPACE = 1

VOCABULARY = ExtractionVocabulary(
    snapshot_id="v1",
    predicate_entries=(
        PredicateEntry(
            name="rate_limit",
            definition="분당 허용 호출 수를 나타낸다.",
            value_type="number",
        ),
        PredicateEntry(
            name="release_date",
            definition="배포일을 나타낸다.",
            value_type="date",
        ),
        PredicateEntry(
            name="description",
            definition="자유 서술을 나타낸다.",
            value_type="text",
        ),
    ),
)

ENUM_VOCABULARY = ExtractionVocabulary(
    snapshot_id="v2",
    predicate_entries=(
        PredicateEntry(
            name="plan_tier",
            definition="요금제 단계를 나타낸다.",
            value_type="enum",
            enum_values=("free", "pro"),
        ),
    ),
)


def _claim(
    *,
    predicate: str = "rate_limit",
    value: object = 60,
    value_type: str = "number",
    node_id: uuid.UUID | None = None,
    candidate_id: uuid.UUID | None = None,
    resolved_node_id: uuid.UUID | None = None,
    statement: str = "",
    minutes: int = 0,
    valid_to: datetime | None = None,
) -> StoredClaimCandidate:
    return StoredClaimCandidate(
        id=uuid.uuid4(),
        subject_entity_candidate_id=candidate_id,
        subject_node_id=node_id,
        subject_resolved_node_id=resolved_node_id,
        predicate=predicate,
        value_type=value_type,
        value=value,
        statement=statement or f"{predicate}는 {value}이다",
        observed_at=NOW + timedelta(minutes=minutes),
        valid_to=valid_to,
    )


class FakeClaimRepository:
    def __init__(self, claims: list[StoredClaimCandidate]) -> None:
        self.claims = list(claims)

    def find_claim_candidates(self, *, workspace_id: int):
        del workspace_id
        return tuple(self.claims)


class FakeProposalRepository:
    """proposal 저장소를 DB 제약까지 흉내 내어 대신한다.

    `(workspace_id, idempotency_key)` UNIQUE를 dict 키로 재현한다. 같은
    키의 계류·접힘 행은 되살려 갈아끼우되 결정 흔적을 지우고, 이미
    결정된 행(approved·applied·rejected)은 보존한 채 id만 돌려준다. 실
    DB의 `add_contradiction_proposal`이 그렇게 동작하기 때문이다.
    """

    DECIDED = ("approved", "applied", "rejected")

    def __init__(
        self,
        duplicate_groups: dict[uuid.UUID, uuid.UUID] | None = None,
    ) -> None:
        self.rows: dict[str, dict] = {}
        self.duplicate_groups = dict(duplicate_groups or {})
        self.abandoned: list[uuid.UUID] = []

    def _stored(self, idempotency_key: str, found: dict):
        return StoredMutationProposal(
            id=found["id"],
            idempotency_key=idempotency_key,
            status=found["status"],
            resolver_metadata=found["resolver_metadata"],
        )

    def find_pending_by_idempotency_key(
        self, *, workspace_id, idempotency_key
    ):
        del workspace_id
        found = self.rows.get(idempotency_key)
        if found is None or found["status"] != "pending":
            return None
        return self._stored(idempotency_key, found)

    def find_decided_by_idempotency_key(
        self, *, workspace_id, idempotency_key
    ):
        del workspace_id
        found = self.rows.get(idempotency_key)
        if found is None or found["status"] not in self.DECIDED:
            return None
        return self._stored(idempotency_key, found)

    def abandon(self, *, proposal_id):
        self.abandoned.append(proposal_id)
        for record in self.rows.values():
            if record["id"] == proposal_id:
                record["status"] = "abandoned"

    def find_pending_duplicate_groups(self, *, workspace_id):
        del workspace_id
        return dict(self.duplicate_groups)

    def find_pending_contradiction_proposals(self, *, workspace_id):
        del workspace_id
        return tuple(
            (
                record["id"],
                key,
                record["resolver_metadata"].get("predicate"),
            )
            for key, record in self.rows.items()
            if record["status"] == "pending"
            and record["kind"] == "contradiction"
        )

    def add_contradiction_proposal(self, **kwargs):
        key = kwargs["idempotency_key"]
        existing = self.rows.get(key)
        if existing is not None and existing["status"] in self.DECIDED:
            # 사람의 결정은 판정 재실행이 덮을 수 없다. 실 repo와 같이
            # 행·명령을 보존한 채 id만 돌려준다.
            return existing["id"]
        proposal_id = existing["id"] if existing else uuid.uuid4()
        self.rows[key] = {
            "id": proposal_id,
            "status": "pending",
            "kind": "contradiction",
            "resolver_metadata": dict(kwargs["resolver_metadata"]),
            "kwargs": kwargs,
            # 되살아난 안건은 새 검토 사건이다. 결정 흔적과 명령을 비운다.
            "reviewer": None,
            "reviewed_at": None,
            "operations": [],
        }
        return proposal_id


class FakeUnitOfWork:
    def __init__(
        self,
        claims: list[StoredClaimCandidate],
        duplicate_groups: dict[uuid.UUID, uuid.UUID] | None = None,
    ) -> None:
        self.knowledge_candidates = FakeClaimRepository(claims)
        self.mutation_proposals = FakeProposalRepository(duplicate_groups)
        self.committed = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return None

    def commit(self) -> None:
        self.committed = True


def test_conflicting_numbers_create_one_proposal() -> None:
    """같은 subject·predicate의 다른 숫자 값이 proposal 하나로 남는다."""
    node_id = uuid.uuid4()
    later = _claim(
        value=120,
        resolved_node_id=node_id,
        candidate_id=uuid.uuid4(),
        statement="rate limit은 120이다",
        minutes=10,
    )
    earlier = _claim(
        value=60,
        resolved_node_id=node_id,
        candidate_id=uuid.uuid4(),
        statement="rate limit은 60이다",
        minutes=0,
    )
    uow = FakeUnitOfWork([later, earlier])

    result = resolve_claim_conflicts(
        workspace_id=WORKSPACE,
        vocabulary=VOCABULARY,
        uow=uow,
    )

    assert result.claims_scanned == 2
    assert result.groups_compared == 1
    assert result.conflicts_found == 1
    assert result.proposals_created == 1
    assert result.proposals_abandoned == 0
    assert result.duplicates_observed == 0
    assert uow.committed is True

    key = conflict_idempotency_key(f"node:{node_id}", "rate_limit")
    row = uow.mutation_proposals.rows[key]
    metadata = row["resolver_metadata"]
    assert metadata["subject_key"] == f"node:{node_id}"
    assert metadata["predicate"] == "rate_limit"
    values = metadata["values"]
    assert [item["value"] for item in values] == [60, 120]
    assert values[0]["claim_id"] == str(earlier.id)
    assert values[0]["statement"] == "rate limit은 60이다"
    assert values[1]["statement"] == "rate limit은 120이다"
    assert values[0]["normalized"] != values[1]["normalized"]
    assert "member_hash" in metadata
    assert row["kwargs"]["trigger_claim_candidate_id"] == earlier.id


def test_converged_values_leave_no_conflict_and_no_duplicates() -> None:
    """값이 수렴하는 두 claim은 모순도 중복 지표도 남기지 않는다."""
    node_id = uuid.uuid4()
    uow = FakeUnitOfWork(
        [
            _claim(value=60, node_id=node_id, minutes=0),
            _claim(value=60.0, node_id=node_id, minutes=5),
        ]
    )

    result = resolve_claim_conflicts(
        workspace_id=WORKSPACE,
        vocabulary=VOCABULARY,
        uow=uow,
    )

    assert result.duplicates_observed == 0
    assert result.conflicts_found == 0
    assert result.proposals_created == 0
    assert uow.mutation_proposals.rows == {}


def test_duplicates_counted_only_in_conflict_groups() -> None:
    """중복 관찰은 모순 그룹 안에서만 센다 — 수렴 그룹은 세지 않는다."""
    node = uuid.uuid4()
    claims = [
        # 수렴 그룹: 같은 값 2건 — 모순 아님, 중복도 세지 않는다.
        _claim(predicate="rate_limit", value=60, node_id=node),
        _claim(predicate="rate_limit", value=60, node_id=node, minutes=1),
        # 모순 그룹: 60, 60, 120 — 중복 1.
        _claim(predicate="rate_limit", value=60, node_id=uuid.uuid4()),
    ]
    conflict_node = claims[2].subject_node_id
    claims += [
        _claim(
            predicate="rate_limit",
            value=60,
            node_id=conflict_node,
            minutes=1,
        ),
        _claim(
            predicate="rate_limit",
            value=120,
            node_id=conflict_node,
            minutes=2,
        ),
    ]
    uow = FakeUnitOfWork(claims)
    result = resolve_claim_conflicts(
        workspace_id=WORKSPACE, vocabulary=VOCABULARY, uow=uow
    )
    assert result.conflicts_found == 1
    assert result.duplicates_observed == 1


def test_unlisted_or_text_predicate_is_ignored() -> None:
    """사전 미등재·text 치역 predicate는 비교하지 않는다."""
    node_id = uuid.uuid4()
    uow = FakeUnitOfWork(
        [
            _claim(predicate="unknown_predicate", value=1, node_id=node_id),
            _claim(predicate="unknown_predicate", value=2, node_id=node_id),
            _claim(
                predicate="description",
                value="빠르다",
                value_type="text",
                node_id=node_id,
            ),
            _claim(
                predicate="description",
                value="느리다",
                value_type="text",
                node_id=node_id,
            ),
        ]
    )

    result = resolve_claim_conflicts(
        workspace_id=WORKSPACE,
        vocabulary=VOCABULARY,
        uow=uow,
    )

    assert result.claims_scanned == 4
    assert result.groups_compared == 0
    assert result.conflicts_found == 0
    assert result.proposals_created == 0
    assert result.claims_without_subject_key == 0
    # 빠진 4건이 어디로 갔는지 출력만으로 복원돼야 한다.
    assert result.claims_not_comparable == 4


def test_subject_without_identity_evidence_is_excluded() -> None:
    """이름만 같고 해소·판정 근거가 없는 subject는 제외한다."""
    uow = FakeUnitOfWork(
        [
            _claim(value=60, candidate_id=uuid.uuid4()),
            _claim(value=120, candidate_id=uuid.uuid4()),
        ]
    )

    result = resolve_claim_conflicts(
        workspace_id=WORKSPACE,
        vocabulary=VOCABULARY,
        uow=uow,
    )

    assert result.claims_without_subject_key == 2
    assert result.groups_compared == 0
    assert result.conflicts_found == 0
    assert result.proposals_created == 0


def test_judge_same_group_counts_as_one_subject() -> None:
    """duplicate proposal 멤버인 두 후보의 claim이 한 그룹이 된다."""
    first_candidate = uuid.uuid4()
    second_candidate = uuid.uuid4()
    proposal_id = uuid.uuid4()
    uow = FakeUnitOfWork(
        [
            _claim(value=60, candidate_id=first_candidate, minutes=0),
            _claim(value=120, candidate_id=second_candidate, minutes=5),
        ],
        duplicate_groups={
            first_candidate: proposal_id,
            second_candidate: proposal_id,
        },
    )

    result = resolve_claim_conflicts(
        workspace_id=WORKSPACE,
        vocabulary=VOCABULARY,
        uow=uow,
    )

    assert result.claims_without_subject_key == 0
    assert result.groups_compared == 1
    assert result.conflicts_found == 1
    assert result.proposals_created == 1
    key = conflict_idempotency_key(
        f"proposal:{proposal_id}", "rate_limit"
    )
    metadata = uow.mutation_proposals.rows[key]["resolver_metadata"]
    assert metadata["subject_key"] == f"proposal:{proposal_id}"


def test_unparseable_value_is_skipped_and_counted() -> None:
    """파싱 실패 값은 비교에서 빠지고 지표로 남는다."""
    node_id = uuid.uuid4()
    uow = FakeUnitOfWork(
        [
            _claim(value="약 60회", node_id=node_id, minutes=0),
            _claim(value=120, node_id=node_id, minutes=5),
        ]
    )

    result = resolve_claim_conflicts(
        workspace_id=WORKSPACE,
        vocabulary=VOCABULARY,
        uow=uow,
    )

    assert result.claims_unparseable == 1
    assert result.conflicts_found == 0
    assert result.proposals_created == 0
    assert uow.mutation_proposals.rows == {}


def test_member_change_abandons_and_replaces() -> None:
    """claim 구성이 바뀌면 기존 proposal을 접고 새로 쓴다."""
    node_id = uuid.uuid4()
    first = _claim(value=60, node_id=node_id, minutes=0)
    second = _claim(value=120, node_id=node_id, minutes=5)
    uow = FakeUnitOfWork([first, second])
    resolve_claim_conflicts(
        workspace_id=WORKSPACE,
        vocabulary=VOCABULARY,
        uow=uow,
    )
    key = conflict_idempotency_key(f"node:{node_id}", "rate_limit")
    original_id = uow.mutation_proposals.rows[key]["id"]

    third = _claim(value=240, node_id=node_id, minutes=9)
    uow.knowledge_candidates.claims.append(third)
    result = resolve_claim_conflicts(
        workspace_id=WORKSPACE,
        vocabulary=VOCABULARY,
        uow=uow,
    )

    assert result.proposals_abandoned == 1
    assert result.proposals_created == 1
    assert uow.mutation_proposals.abandoned == [original_id]
    row = uow.mutation_proposals.rows[key]
    assert row["status"] == "pending"
    # UNIQUE(workspace_id, idempotency_key) 때문에 같은 행을 되살린다.
    assert row["id"] == original_id
    assert len(row["resolver_metadata"]["values"]) == 3


def test_value_correction_changes_member_hash() -> None:
    """같은 멤버라도 정규화 값이 정정되면 member_hash가 달라진다."""
    node_id = uuid.uuid4()
    first = _claim(value=60, node_id=node_id, minutes=0)
    second = _claim(value=120, node_id=node_id, minutes=5)
    uow = FakeUnitOfWork([first, second])
    resolve_claim_conflicts(
        workspace_id=WORKSPACE,
        vocabulary=VOCABULARY,
        uow=uow,
    )
    key = conflict_idempotency_key(f"node:{node_id}", "rate_limit")
    hash_before = uow.mutation_proposals.rows[key]["resolver_metadata"][
        "member_hash"
    ]

    # 같은 claim 행의 값이 정정되어 다시 들어온다.
    uow.knowledge_candidates.claims = [first, replace(second, value=90)]
    resolve_claim_conflicts(
        workspace_id=WORKSPACE,
        vocabulary=VOCABULARY,
        uow=uow,
    )

    hash_after = uow.mutation_proposals.rows[key]["resolver_metadata"][
        "member_hash"
    ]
    assert hash_before != hash_after


def test_rerun_with_same_members_skips() -> None:
    """member_hash가 같으면 재실행이 proposal을 반복하지 않는다."""
    node_id = uuid.uuid4()
    uow = FakeUnitOfWork(
        [
            _claim(value=60, node_id=node_id, minutes=0),
            _claim(value=120, node_id=node_id, minutes=5),
        ]
    )
    resolve_claim_conflicts(
        workspace_id=WORKSPACE,
        vocabulary=VOCABULARY,
        uow=uow,
    )

    with capture_logs() as logs:
        result = resolve_claim_conflicts(
            workspace_id=WORKSPACE,
            vocabulary=VOCABULARY,
            uow=uow,
        )

    assert result.conflicts_found == 1
    assert result.proposals_created == 0
    assert result.proposals_abandoned == 0
    assert uow.mutation_proposals.abandoned == []
    assert len(uow.mutation_proposals.rows) == 1
    completed = [
        entry
        for entry in logs
        if entry["event"] == "claim_conflict_completed"
    ]
    assert completed and completed[0]["proposals_created"] == 0


def test_converged_values_abandon_stale_proposal() -> None:
    """값이 한 종으로 수렴하면 낡은 proposal을 회수한다."""
    node_id = uuid.uuid4()
    first = _claim(value=60, node_id=node_id, minutes=0)
    second = _claim(value=120, node_id=node_id, minutes=5)
    uow = FakeUnitOfWork([first, second])
    resolve_claim_conflicts(
        workspace_id=WORKSPACE,
        vocabulary=VOCABULARY,
        uow=uow,
    )
    key = conflict_idempotency_key(f"node:{node_id}", "rate_limit")
    proposal_id = uow.mutation_proposals.rows[key]["id"]

    uow.knowledge_candidates.claims = [first, replace(second, value=60)]
    result = resolve_claim_conflicts(
        workspace_id=WORKSPACE,
        vocabulary=VOCABULARY,
        uow=uow,
    )

    assert result.conflicts_found == 0
    assert result.proposals_created == 0
    assert result.proposals_abandoned == 1
    assert uow.mutation_proposals.abandoned == [proposal_id]
    assert uow.mutation_proposals.rows[key]["status"] == "abandoned"


def test_disappeared_claims_abandon_stale_proposal() -> None:
    """비교할 claim이 사라지면 남아 있던 proposal을 접는다."""
    node_id = uuid.uuid4()
    uow = FakeUnitOfWork(
        [
            _claim(value=60, node_id=node_id, minutes=0),
            _claim(value=120, node_id=node_id, minutes=5),
        ]
    )
    resolve_claim_conflicts(
        workspace_id=WORKSPACE,
        vocabulary=VOCABULARY,
        uow=uow,
    )
    key = conflict_idempotency_key(f"node:{node_id}", "rate_limit")

    uow.knowledge_candidates.claims = []
    result = resolve_claim_conflicts(
        workspace_id=WORKSPACE,
        vocabulary=VOCABULARY,
        uow=uow,
    )

    assert result.proposals_abandoned == 1
    assert uow.mutation_proposals.rows[key]["status"] == "abandoned"


def test_subject_key_migration_abandons_old_key() -> None:
    """subject 키가 이주하면 옛 키를 접고 새 키로 다시 쓴다."""
    first_candidate = uuid.uuid4()
    second_candidate = uuid.uuid4()
    group_proposal = uuid.uuid4()
    first = _claim(value=60, candidate_id=first_candidate, minutes=0)
    second = _claim(value=120, candidate_id=second_candidate, minutes=5)
    uow = FakeUnitOfWork(
        [first, second],
        duplicate_groups={
            first_candidate: group_proposal,
            second_candidate: group_proposal,
        },
    )
    resolve_claim_conflicts(
        workspace_id=WORKSPACE,
        vocabulary=VOCABULARY,
        uow=uow,
    )
    old_key = conflict_idempotency_key(
        f"proposal:{group_proposal}", "rate_limit"
    )
    old_id = uow.mutation_proposals.rows[old_key]["id"]

    # 병합이 승인되면 후보가 노드로 해소되고 병합 계획서는 닫힌다.
    node_id = uuid.uuid4()
    uow.knowledge_candidates.claims = [
        replace(first, subject_resolved_node_id=node_id),
        replace(second, subject_resolved_node_id=node_id),
    ]
    uow.mutation_proposals.duplicate_groups = {}
    result = resolve_claim_conflicts(
        workspace_id=WORKSPACE,
        vocabulary=VOCABULARY,
        uow=uow,
    )

    new_key = conflict_idempotency_key(f"node:{node_id}", "rate_limit")
    assert result.proposals_created == 1
    assert result.proposals_abandoned == 1
    assert uow.mutation_proposals.abandoned == [old_id]
    assert uow.mutation_proposals.rows[old_key]["status"] == "abandoned"
    assert uow.mutation_proposals.rows[new_key]["status"] == "pending"


def _conflicted_uow(node_id: uuid.UUID) -> FakeUnitOfWork:
    """모순 proposal이 하나 열려 있는 상태를 만든다."""
    uow = FakeUnitOfWork(
        [
            _claim(value=60, node_id=node_id, minutes=0),
            _claim(value=120, node_id=node_id, minutes=5),
        ]
    )
    resolve_claim_conflicts(
        workspace_id=WORKSPACE,
        vocabulary=VOCABULARY,
        uow=uow,
    )
    return uow


def test_predicate_removed_from_dictionary_keeps_proposal() -> None:
    """사전에서 빠진 predicate의 proposal은 회수하지 않는다."""
    node_id = uuid.uuid4()
    uow = _conflicted_uow(node_id)
    key = conflict_idempotency_key(f"node:{node_id}", "rate_limit")
    shrunk = ExtractionVocabulary(
        snapshot_id="v2",
        predicate_entries=(
            PredicateEntry(
                name="release_date",
                definition="배포일을 나타낸다.",
                value_type="date",
            ),
        ),
    )

    result = resolve_claim_conflicts(
        workspace_id=WORKSPACE,
        vocabulary=shrunk,
        uow=uow,
    )

    assert result.proposals_abandoned == 0
    assert uow.mutation_proposals.abandoned == []
    assert uow.mutation_proposals.rows[key]["status"] == "pending"


def test_predicate_turned_text_keeps_proposal() -> None:
    """치역이 text로 바뀐 predicate의 proposal도 남긴다."""
    node_id = uuid.uuid4()
    uow = _conflicted_uow(node_id)
    key = conflict_idempotency_key(f"node:{node_id}", "rate_limit")
    loosened = ExtractionVocabulary(
        snapshot_id="v2",
        predicate_entries=(
            PredicateEntry(
                name="rate_limit",
                definition="분당 허용 호출 수를 서술한다.",
                value_type="text",
            ),
        ),
    )

    result = resolve_claim_conflicts(
        workspace_id=WORKSPACE,
        vocabulary=loosened,
        uow=uow,
    )

    assert result.proposals_abandoned == 0
    assert uow.mutation_proposals.rows[key]["status"] == "pending"


def test_legacy_vocabulary_skips_recall_with_warning() -> None:
    """사전 항목이 없는 v1 스냅샷은 회수를 통째로 건너뛴다."""
    node_id = uuid.uuid4()
    uow = _conflicted_uow(node_id)
    key = conflict_idempotency_key(f"node:{node_id}", "rate_limit")
    legacy = ExtractionVocabulary(
        snapshot_id="v1",
        predicates=("rate_limit", "release_date"),
    )

    with capture_logs() as logs:
        result = resolve_claim_conflicts(
            workspace_id=WORKSPACE,
            vocabulary=legacy,
            uow=uow,
        )

    assert result.proposals_abandoned == 0
    assert uow.mutation_proposals.rows[key]["status"] == "pending"
    skipped = [
        entry
        for entry in logs
        if entry["event"] == "claim_conflict_recall_skipped"
    ]
    assert skipped and skipped[0]["log_level"] == "warning"


def test_dictionary_value_type_wins_over_claim_report() -> None:
    """claim이 잘못 신고한 value_type 대신 사전 치역으로 비교한다."""
    node_id = uuid.uuid4()
    uow = FakeUnitOfWork(
        [
            _claim(value=60, value_type="text", node_id=node_id, minutes=0),
            _claim(value=120, value_type="text", node_id=node_id, minutes=5),
        ]
    )

    result = resolve_claim_conflicts(
        workspace_id=WORKSPACE,
        vocabulary=VOCABULARY,
        uow=uow,
    )

    assert result.groups_compared == 1
    assert result.conflicts_found == 1
    assert result.proposals_created == 1


def test_closed_claim_leaves_the_comparison() -> None:
    """구간이 닫힌 주장은 비교에서 빠지고 모순도 사라진다."""
    node_id = uuid.uuid4()
    alive = _claim(
        value=60,
        resolved_node_id=node_id,
        candidate_id=uuid.uuid4(),
    )
    closed = _claim(
        value=120,
        resolved_node_id=node_id,
        candidate_id=uuid.uuid4(),
        minutes=10,
        valid_to=NOW + timedelta(days=1),
    )
    uow = FakeUnitOfWork([alive, closed])

    result = resolve_claim_conflicts(
        workspace_id=WORKSPACE,
        vocabulary=VOCABULARY,
        uow=uow,
    )

    assert result.claims_scanned == 2
    assert result.claims_closed == 1
    # 값이 한 종만 남아 견줄 그룹이 되지 못한다.
    assert result.conflicts_found == 0
    assert result.proposals_created == 0


def _decide(repo: FakeProposalRepository, key: str) -> dict:
    """계류 안건에 사람의 결정을 흉내 내어 새긴다."""
    row = repo.rows[key]
    row["status"] = "approved"
    row["reviewer"] = "debug:test-user"
    row["reviewed_at"] = NOW
    row["resolver_metadata"]["decision"] = {"winner_claim_id": "w"}
    row["operations"] = [{"operation_type": "supersede_claim"}]
    return row


def test_decided_proposal_survives_rerun_with_same_members() -> None:
    """같은 구성의 재실행은 승인된 결정과 명령을 건드리지 않는다."""
    node_id = uuid.uuid4()
    claims = [
        _claim(value=60, node_id=node_id, minutes=0),
        _claim(value=120, node_id=node_id, minutes=10),
    ]
    uow = FakeUnitOfWork(claims)
    resolve_claim_conflicts(
        workspace_id=WORKSPACE, vocabulary=VOCABULARY, uow=uow
    )
    key = conflict_idempotency_key(f"node:{node_id}", "rate_limit")
    decided = _decide(uow.mutation_proposals, key)

    result = resolve_claim_conflicts(
        workspace_id=WORKSPACE, vocabulary=VOCABULARY, uow=uow
    )

    row = uow.mutation_proposals.rows[key]
    assert row["status"] == "approved"
    assert row["reviewer"] == "debug:test-user"
    assert row["resolver_metadata"]["decision"] == {"winner_claim_id": "w"}
    assert row["operations"] == decided["operations"]
    assert result.proposals_created == 0
    assert result.proposals_abandoned == 0
    assert len(uow.mutation_proposals.rows) == 1


def test_decided_proposal_with_legacy_hash_survives_rerun() -> None:
    """구 포맷 member_hash로 결정된 행도 같은 구성 재실행에서 안전하다."""
    node_id = uuid.uuid4()
    claims = [
        _claim(value=60, node_id=node_id, minutes=0),
        _claim(value=120, node_id=node_id, minutes=10),
    ]
    uow = FakeUnitOfWork(claims)
    resolve_claim_conflicts(
        workspace_id=WORKSPACE, vocabulary=VOCABULARY, uow=uow
    )
    key = conflict_idempotency_key(f"node:{node_id}", "rate_limit")
    decided = _decide(uow.mutation_proposals, key)
    # 배포 전 결정 행은 구 포맷(id만 이어붙인) 해시를 갖고 있었다.
    legacy_hash = hashlib.sha256(
        ",".join(sorted(str(claim.id) for claim in claims)).encode(
            "utf-8"
        )
    ).hexdigest()
    decided["resolver_metadata"]["member_hash"] = legacy_hash

    with capture_logs() as logs:
        result = resolve_claim_conflicts(
            workspace_id=WORKSPACE, vocabulary=VOCABULARY, uow=uow
        )

    assert result.proposals_created == 0
    assert result.proposals_abandoned == 0
    assert len(uow.mutation_proposals.rows) == 1
    standing = [
        entry
        for entry in logs
        if entry["event"] == "claim_conflict_decision_standing"
    ]
    assert len(standing) == 1


def test_decided_proposal_new_members_open_new_review_event() -> None:
    """구성이 달라지면 결정 행을 덮지 않고 새 검토 사건을 연다."""
    node_id = uuid.uuid4()
    claims = [
        _claim(value=60, node_id=node_id, minutes=0),
        _claim(value=120, node_id=node_id, minutes=10),
    ]
    uow = FakeUnitOfWork(claims)
    resolve_claim_conflicts(
        workspace_id=WORKSPACE, vocabulary=VOCABULARY, uow=uow
    )
    base_key = conflict_idempotency_key(f"node:{node_id}", "rate_limit")
    _decide(uow.mutation_proposals, base_key)

    # 새 claim이 진 값을 다시 주장한다 — TMS의 결정 재개다.
    uow.knowledge_candidates.claims.append(
        _claim(value=90, node_id=node_id, minutes=20)
    )
    result = resolve_claim_conflicts(
        workspace_id=WORKSPACE, vocabulary=VOCABULARY, uow=uow
    )

    rows = uow.mutation_proposals.rows
    assert rows[base_key]["status"] == "approved"
    assert rows[base_key]["resolver_metadata"]["decision"] == {
        "winner_claim_id": "w"
    }
    new_keys = [key for key in rows if key != base_key]
    assert len(new_keys) == 1
    new_row = rows[new_keys[0]]
    assert new_row["status"] == "pending"
    member_hash = new_row["resolver_metadata"]["member_hash"]
    assert new_keys[0] == conflict_idempotency_key(
        f"node:{node_id}", "rate_limit", member_hash
    )
    assert result.proposals_created == 1


def test_new_review_event_is_stable_across_reruns() -> None:
    """새 검토 사건은 재실행마다 생성·회수를 반복하지 않는다."""
    node_id = uuid.uuid4()
    claims = [
        _claim(value=60, node_id=node_id, minutes=0),
        _claim(value=120, node_id=node_id, minutes=10),
    ]
    uow = FakeUnitOfWork(claims)
    resolve_claim_conflicts(
        workspace_id=WORKSPACE, vocabulary=VOCABULARY, uow=uow
    )
    base_key = conflict_idempotency_key(f"node:{node_id}", "rate_limit")
    _decide(uow.mutation_proposals, base_key)
    uow.knowledge_candidates.claims.append(
        _claim(value=90, node_id=node_id, minutes=20)
    )
    resolve_claim_conflicts(
        workspace_id=WORKSPACE, vocabulary=VOCABULARY, uow=uow
    )

    result = resolve_claim_conflicts(
        workspace_id=WORKSPACE, vocabulary=VOCABULARY, uow=uow
    )

    assert result.proposals_created == 0
    assert result.proposals_abandoned == 0
    assert len(uow.mutation_proposals.rows) == 2


def test_partial_precision_date_overlap_is_not_conflict() -> None:
    node = uuid.uuid4()
    claims = [
        _claim(
            predicate="release_date",
            value="2026-09",
            value_type="date",
            node_id=node,
        ),
        _claim(
            predicate="release_date",
            value="2026-09-15",
            value_type="date",
            node_id=node,
            minutes=1,
        ),
    ]
    uow = FakeUnitOfWork(claims)
    result = resolve_claim_conflicts(
        workspace_id=WORKSPACE, vocabulary=VOCABULARY, uow=uow
    )
    assert result.conflicts_found == 0
    assert result.proposals_created == 0
    assert result.date_precision_overlaps == 1


def test_distinct_full_dates_still_conflict() -> None:
    node = uuid.uuid4()
    claims = [
        _claim(
            predicate="release_date",
            value="2026-09-15",
            value_type="date",
            node_id=node,
        ),
        _claim(
            predicate="release_date",
            value="2026-09-20",
            value_type="date",
            node_id=node,
            minutes=1,
        ),
    ]
    uow = FakeUnitOfWork(claims)
    result = resolve_claim_conflicts(
        workspace_id=WORKSPACE, vocabulary=VOCABULARY, uow=uow
    )
    assert result.conflicts_found == 1
    assert result.date_precision_overlaps == 0


def test_enum_value_outside_dictionary_counts_unparseable() -> None:
    node = uuid.uuid4()
    claims = [
        _claim(
            predicate="plan_tier",
            value="enterprise",
            value_type="enum",
            node_id=node,
        ),
        _claim(
            predicate="plan_tier",
            value="pro",
            value_type="enum",
            node_id=node,
            minutes=1,
        ),
    ]
    uow = FakeUnitOfWork(claims)
    result = resolve_claim_conflicts(
        workspace_id=WORKSPACE, vocabulary=ENUM_VOCABULARY, uow=uow
    )
    assert result.claims_unparseable == 1
    assert result.conflicts_found == 0
    assert result.proposals_created == 0


def test_values_carry_citation_verified() -> None:
    node = uuid.uuid4()
    claims = [
        _claim(predicate="rate_limit", value=60, node_id=node),
        replace(
            _claim(
                predicate="rate_limit",
                value=120,
                node_id=node,
                minutes=1,
            ),
            citation_verified=False,
        ),
    ]
    uow = FakeUnitOfWork(claims)
    resolve_claim_conflicts(
        workspace_id=WORKSPACE, vocabulary=VOCABULARY, uow=uow
    )
    key = conflict_idempotency_key(f"node:{node}", "rate_limit")
    values = uow.mutation_proposals.rows[key]["resolver_metadata"]["values"]
    assert values[0]["citation_verified"] is None
    assert values[1]["citation_verified"] is False
