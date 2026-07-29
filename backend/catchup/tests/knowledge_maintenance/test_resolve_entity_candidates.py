from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import datetime
from datetime import timedelta
from datetime import timezone

from catchup.knowledge_maintenance.domain.entity_resolution import IdentityVerdict
from catchup.knowledge_maintenance.domain.entity_resolution import normalize_name
from catchup.knowledge_maintenance.domain.knowledge_candidate import (
    EntityResolutionStatus,
)
from catchup.knowledge_maintenance.domain.knowledge_candidate import ExtractionMethod
from catchup.knowledge_maintenance.domain.knowledge_candidate import (
    StoredEntityCandidate,
)
from catchup.knowledge_maintenance.domain.knowledge_candidate import (
    StoredMutationProposal,
)
from catchup.knowledge_maintenance.domain.knowledge_node import KnowledgeNode
from catchup.knowledge_maintenance.domain.knowledge_node import NodeKind
from catchup.knowledge_maintenance.services.resolve_entity_candidates import (
    group_idempotency_key,
)
from catchup.knowledge_maintenance.services.resolve_entity_candidates import (
    resolve_entity_candidates,
)

NOW = datetime(2026, 7, 29, 9, 0, tzinfo=timezone.utc)
WORKSPACE = 1


def _candidate(
    *,
    name: str,
    entity_type: str = "channel_talk_user",
    method: ExtractionMethod = ExtractionMethod.DETERMINISTIC,
    external_key: str | None = None,
    minutes: int = 0,
) -> StoredEntityCandidate:
    attributes: dict[str, object] = {}
    if external_key is not None:
        attributes["external_key"] = external_key
    return StoredEntityCandidate(
        id=uuid.uuid4(),
        run_id=uuid.uuid4(),
        local_key="m1" if method is ExtractionMethod.DETERMINISTIC else "e1",
        proposed_type=entity_type,
        proposed_name=name,
        extraction_method=method,
        raw_payload={"attributes": attributes},
        source_type="channel_talk",
        created_at=NOW + timedelta(minutes=minutes),
    )


class FakeCandidateRepository:
    def __init__(self, candidates: list[StoredEntityCandidate]) -> None:
        self.candidates = list(candidates)
        self.resolved: dict[uuid.UUID, tuple[EntityResolutionStatus, uuid.UUID]] = {}

    def find_pending_entity_candidates(self, *, workspace_id: int):
        del workspace_id
        return tuple(
            candidate
            for candidate in self.candidates
            if candidate.id not in self.resolved
        )

    def mark_entity_resolved(self, *, candidate_id, status, resolved_node_id):
        self.resolved[candidate_id] = (status, resolved_node_id)


class FakeNodeRepository:
    def __init__(self) -> None:
        self.nodes: dict[str, KnowledgeNode] = {}
        self.aliases: list[tuple[uuid.UUID, str]] = []

    def get_entity_by_canonical_key(self, *, workspace_id, canonical_key):
        del workspace_id
        return self.nodes.get(canonical_key)

    def create_entity_node(
        self, *, workspace_id, entity_type, canonical_key, display_name
    ):
        node = KnowledgeNode(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            node_kind=NodeKind.ENTITY,
            entity_type=entity_type,
            canonical_key=canonical_key,
            display_name=display_name,
        )
        self.nodes[canonical_key] = node
        return node

    def add_alias(
        self, *, workspace_id, node_id, alias, normalized_alias, source
    ):
        del workspace_id, alias, source
        if (node_id, normalized_alias) not in self.aliases:
            self.aliases.append((node_id, normalized_alias))


class FakeProposalRepository:
    def __init__(self) -> None:
        self.proposals: dict[str, dict] = {}
        self.abandoned: list[uuid.UUID] = []

    def find_pending_by_idempotency_key(self, *, workspace_id, idempotency_key):
        del workspace_id
        found = self.proposals.get(idempotency_key)
        if found is None or found["status"] != "pending":
            return None
        return StoredMutationProposal(
            id=found["id"],
            idempotency_key=idempotency_key,
            status=found["status"],
            resolver_metadata=found["resolver_metadata"],
        )

    def abandon(self, *, proposal_id):
        self.abandoned.append(proposal_id)
        for record in self.proposals.values():
            if record["id"] == proposal_id:
                record["status"] = "abandoned"

    def add_duplicate_proposal(self, **kwargs):
        proposal_id = uuid.uuid4()
        self.proposals[kwargs["idempotency_key"]] = {
            "id": proposal_id,
            "status": "pending",
            "resolver_metadata": dict(kwargs["resolver_metadata"]),
            "kwargs": kwargs,
        }
        return proposal_id


class FakeUnitOfWork:
    def __init__(self, candidates: list[StoredEntityCandidate]) -> None:
        self.knowledge_candidates = FakeCandidateRepository(candidates)
        self.knowledge_nodes = FakeNodeRepository()
        self.mutation_proposals = FakeProposalRepository()
        self.committed = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return None

    def commit(self) -> None:
        self.committed = True


def test_same_external_key_candidates_share_one_node() -> None:
    """같은 외부 ID의 후보들은 노드 하나로 모인다."""
    first = _candidate(name="캐치업 팀", external_key="manager-1")
    second = _candidate(name="캐치업 팀", external_key="manager-1", minutes=1)
    uow = FakeUnitOfWork([first, second])

    result = resolve_entity_candidates(
        workspace_id=WORKSPACE, judge=None, uow=uow
    )

    assert result.nodes_created == 1
    assert result.candidates_accepted == 1
    assert result.candidates_merged == 1
    statuses = uow.knowledge_candidates.resolved
    assert statuses[first.id][0] is EntityResolutionStatus.ACCEPTED
    assert statuses[second.id][0] is EntityResolutionStatus.MERGED
    assert statuses[first.id][1] == statuses[second.id][1]
    assert uow.committed


def test_different_external_keys_get_separate_nodes() -> None:
    """외부 ID가 다르면 이름이 같아도 다른 노드다."""
    uow = FakeUnitOfWork(
        [
            _candidate(name="캐치업 팀", external_key="manager-1"),
            _candidate(name="캐치업 팀", external_key="manager-2"),
        ]
    )

    result = resolve_entity_candidates(
        workspace_id=WORKSPACE, judge=None, uow=uow
    )

    assert result.nodes_created == 2
    assert result.candidates_accepted == 2


def test_llm_candidate_merges_into_existing_canonical_key() -> None:
    """기존 canonical key와 정확히 일치하는 LLM 후보는 병합된다."""
    uow = FakeUnitOfWork(
        [
            _candidate(
                name="Slack",
                entity_type="platform",
                method=ExtractionMethod.LLM,
            )
        ]
    )
    existing = uow.knowledge_nodes.create_entity_node(
        workspace_id=WORKSPACE,
        entity_type="platform",
        canonical_key=f"platform:{normalize_name('Slack')}",
        display_name="Slack",
    )

    result = resolve_entity_candidates(
        workspace_id=WORKSPACE, judge=None, uow=uow
    )

    # 노드는 셋업이 미리 만든 것뿐이고, 서비스는 신규 발급하지 않는다.
    assert result.nodes_created == 0
    assert result.candidates_merged == 1
    resolved = uow.knowledge_candidates.resolved
    only = next(iter(resolved.values()))
    assert only == (EntityResolutionStatus.MERGED, existing.id)


def test_llm_candidate_with_new_name_stays_pending() -> None:
    """처음 보는 LLM 후보는 canonical로 창설하지 않는다."""
    uow = FakeUnitOfWork(
        [
            _candidate(
                name="결제 기능",
                entity_type="feature",
                method=ExtractionMethod.LLM,
            )
        ]
    )

    result = resolve_entity_candidates(
        workspace_id=WORKSPACE, judge=None, uow=uow
    )

    assert result.nodes_created == 0
    assert result.candidates_accepted == 0
    assert uow.knowledge_candidates.resolved == {}


def test_deterministic_without_external_key_stays_pending() -> None:
    """외부 ID가 없는 결정론 후보는 건드리지 않는다."""
    uow = FakeUnitOfWork([_candidate(name="캐치업 팀", external_key=None)])

    result = resolve_entity_candidates(
        workspace_id=WORKSPACE, judge=None, uow=uow
    )

    assert result.nodes_created == 0
    assert uow.knowledge_candidates.resolved == {}


class FakeJudge:
    """정해진 판정을 돌려주고 호출을 기록한다."""

    def __init__(self, verdict: IdentityVerdict) -> None:
        self.verdict = verdict
        self.calls: list[tuple] = []

    def judge(self, group):
        self.calls.append(group)
        return self.verdict


class FailingJudge:
    def judge(self, group):
        del group
        raise RuntimeError("판정 모델이 응답하지 않는다")


def _slack_group() -> list[StoredEntityCandidate]:
    return [
        _candidate(
            name="Slack",
            entity_type="platform",
            method=ExtractionMethod.LLM,
        ),
        _candidate(
            name="slack",
            entity_type="integration",
            method=ExtractionMethod.LLM,
            minutes=1,
        ),
    ]


def test_same_verdict_writes_one_proposal_per_group() -> None:
    """같다고 판정된 그룹은 proposal 하나로 남는다."""
    judge = FakeJudge(
        IdentityVerdict(
            same=True,
            reason="같은 제품이다",
            proposed_type="integration",
            proposed_name="Slack",
        )
    )
    uow = FakeUnitOfWork(_slack_group())

    result = resolve_entity_candidates(
        workspace_id=WORKSPACE, judge=judge, uow=uow
    )

    assert result.groups_judged == 1
    assert result.proposals_created == 1
    stored = uow.mutation_proposals.proposals[group_idempotency_key("slack")]
    kwargs = stored["kwargs"]
    assert kwargs["proposed_type"] == "integration"
    assert len(kwargs["merge_candidate_ids"]) == 1
    # 후보는 pending 유지 — 적용은 승인 트랜잭션의 일이다.
    assert uow.knowledge_candidates.resolved == {}


def test_rerun_with_same_members_skips_judge_and_keeps_proposal() -> None:
    """멤버가 같으면 재실행이 판정도 proposal도 반복하지 않는다."""
    judge = FakeJudge(
        IdentityVerdict(
            same=True,
            reason="같은 제품이다",
            proposed_type="integration",
            proposed_name="Slack",
        )
    )
    members = _slack_group()
    first_uow = FakeUnitOfWork(members)
    resolve_entity_candidates(
        workspace_id=WORKSPACE, judge=judge, uow=first_uow
    )

    second_uow = FakeUnitOfWork(members)
    second_uow.mutation_proposals = first_uow.mutation_proposals
    result = resolve_entity_candidates(
        workspace_id=WORKSPACE, judge=judge, uow=second_uow
    )

    assert result.groups_judged == 0
    assert result.proposals_created == 0
    assert len(judge.calls) == 1


def test_member_change_abandons_old_proposal() -> None:
    """멤버가 늘면 기존 pending을 접고 새로 쓴다."""
    judge = FakeJudge(
        IdentityVerdict(
            same=True,
            reason="같은 제품이다",
            proposed_type="integration",
            proposed_name="Slack",
        )
    )
    members = _slack_group()
    first_uow = FakeUnitOfWork(members)
    resolve_entity_candidates(
        workspace_id=WORKSPACE, judge=judge, uow=first_uow
    )
    old_id = first_uow.mutation_proposals.proposals[group_idempotency_key("slack")]["id"]

    grown = members + [
        _candidate(
            name="SLACK",
            entity_type="system",
            method=ExtractionMethod.LLM,
            minutes=2,
        )
    ]
    second_uow = FakeUnitOfWork(grown)
    second_uow.mutation_proposals = first_uow.mutation_proposals
    result = resolve_entity_candidates(
        workspace_id=WORKSPACE, judge=judge, uow=second_uow
    )

    assert result.proposals_abandoned == 1
    assert old_id in second_uow.mutation_proposals.abandoned
    assert result.proposals_created == 1


def test_different_verdict_writes_nothing() -> None:
    """다르다는 판정은 아무 기록도 남기지 않는다."""
    judge = FakeJudge(
        IdentityVerdict(same=False, reason="채널과 연동은 다른 대상이다")
    )
    uow = FakeUnitOfWork(_slack_group())

    result = resolve_entity_candidates(
        workspace_id=WORKSPACE, judge=judge, uow=uow
    )

    assert result.groups_judged == 1
    assert result.proposals_created == 0
    assert uow.mutation_proposals.proposals == {}


def test_judge_failure_skips_group_and_continues() -> None:
    """판정 실패는 그 그룹만 건너뛴다."""
    uow = FakeUnitOfWork(_slack_group())

    result = resolve_entity_candidates(
        workspace_id=WORKSPACE, judge=FailingJudge(), uow=uow
    )

    assert result.groups_failed == 1
    assert result.proposals_created == 0
    assert uow.committed


def test_member_change_with_different_verdict_abandons_stale_proposal() -> None:
    """멤버가 달라진 뒤 다르다는 판정이 나와도 낡은 계획서는 접힌다."""
    same_judge = FakeJudge(
        IdentityVerdict(
            same=True,
            reason="같은 제품이다",
            proposed_type="integration",
            proposed_name="Slack",
        )
    )
    members = _slack_group()
    first_uow = FakeUnitOfWork(members)
    resolve_entity_candidates(
        workspace_id=WORKSPACE, judge=same_judge, uow=first_uow
    )
    key = group_idempotency_key("slack")
    old_id = first_uow.mutation_proposals.proposals[key]["id"]

    grown = members + [
        _candidate(
            name="SLACK",
            entity_type="channel",
            method=ExtractionMethod.LLM,
            minutes=2,
        )
    ]
    different_judge = FakeJudge(
        IdentityVerdict(same=False, reason="채널이 섞여 단정할 수 없다")
    )
    second_uow = FakeUnitOfWork(grown)
    second_uow.mutation_proposals = first_uow.mutation_proposals
    result = resolve_entity_candidates(
        workspace_id=WORKSPACE, judge=different_judge, uow=second_uow
    )

    assert result.proposals_abandoned == 1
    assert old_id in second_uow.mutation_proposals.abandoned
    assert result.proposals_created == 0
    assert (
        second_uow.mutation_proposals.find_pending_by_idempotency_key(
            workspace_id=WORKSPACE, idempotency_key=key
        )
        is None
    )


def test_idempotency_key_is_fixed_length_hash() -> None:
    """proposal key는 이름 길이와 무관하게 255자 안의 고정 길이다."""
    long_name = "매우 긴 기능 이름 " * 40  # 400자 이상
    judge = FakeJudge(
        IdentityVerdict(
            same=True,
            reason="같은 기능이다",
            proposed_type="feature",
            proposed_name="긴 기능",
        )
    )
    uow = FakeUnitOfWork(
        [
            _candidate(
                name=long_name,
                entity_type="feature",
                method=ExtractionMethod.LLM,
            ),
            _candidate(
                name=long_name,
                entity_type="product",
                method=ExtractionMethod.LLM,
                minutes=1,
            ),
        ]
    )

    result = resolve_entity_candidates(
        workspace_id=WORKSPACE, judge=judge, uow=uow
    )

    assert result.proposals_created == 1
    (key,) = uow.mutation_proposals.proposals.keys()
    assert len(key) == 64
    assert key == group_idempotency_key(normalize_name(long_name))


def test_judge_receives_observation_excerpt() -> None:
    """판정 입력에 원문 맥락이 실린다."""
    judge = FakeJudge(
        IdentityVerdict(same=False, reason="맥락이 달라 단정할 수 없다")
    )
    members = [
        _candidate(
            name="Slack",
            entity_type="platform",
            method=ExtractionMethod.LLM,
        ),
        _candidate(
            name="slack",
            entity_type="integration",
            method=ExtractionMethod.LLM,
            minutes=1,
        ),
    ]
    members = [
        replace(member, observation_excerpt="고객: Slack 연결이 끊겼어요.")
        for member in members
    ]
    uow = FakeUnitOfWork(members)

    resolve_entity_candidates(workspace_id=WORKSPACE, judge=judge, uow=uow)

    (group,) = judge.calls
    assert all(
        candidate.excerpt == "고객: Slack 연결이 끊겼어요."
        for candidate in group
    )


def test_single_member_group_is_not_judged() -> None:
    """혼자인 이름은 판정 대상이 아니다."""
    judge = FakeJudge(
        IdentityVerdict(same=False, reason="판정할 일이 없어야 한다")
    )
    uow = FakeUnitOfWork(
        [
            _candidate(
                name="결제 기능",
                entity_type="feature",
                method=ExtractionMethod.LLM,
            )
        ]
    )

    result = resolve_entity_candidates(
        workspace_id=WORKSPACE, judge=judge, uow=uow
    )

    assert result.groups_judged == 0
    assert judge.calls == []
