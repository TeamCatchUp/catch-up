from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import datetime
from datetime import timedelta
from datetime import timezone

from structlog.testing import capture_logs

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
from catchup.knowledge_maintenance.domain.knowledge_node import NodeLifecycleState
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
    """노드 저장소를 흉내 낸다.

    canonical_key는 비어 있을 수 있고 같은 alias가 여러 노드에 걸릴 수
    있으므로 실 DB처럼 노드를 id로 담고, alias 조회는 node id 순 첫
    번째만 돌려준다.
    """

    def __init__(self) -> None:
        self.nodes: dict[uuid.UUID, KnowledgeNode] = {}
        self.aliases: list[tuple[uuid.UUID, str]] = []
        self.alias_sources: list[tuple[uuid.UUID, str, str]] = []

    def get_entity_by_canonical_key(self, *, workspace_id, canonical_key):
        del workspace_id
        matched = [
            node
            for node in self.nodes.values()
            if node.canonical_key == canonical_key
        ]
        return min(matched, key=lambda node: node.id) if matched else None

    def find_entity_by_normalized_alias(
        self, *, workspace_id, normalized_alias, entity_type=None
    ):
        del workspace_id
        matched = [
            self.nodes[node_id]
            for node_id, alias in self.aliases
            if alias == normalized_alias
            and self.nodes[node_id].node_kind is NodeKind.ENTITY
            and (
                entity_type is None
                or self.nodes[node_id].entity_type == entity_type
            )
        ]
        return min(matched, key=lambda node: node.id) if matched else None

    def create_entity_node(
        self,
        *,
        workspace_id,
        entity_type,
        canonical_key,
        display_name,
        attributes=None,
    ):
        node = KnowledgeNode(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            node_kind=NodeKind.ENTITY,
            entity_type=entity_type,
            canonical_key=canonical_key,
            display_name=display_name,
            attributes=dict(attributes or {}),
        )
        self.nodes[node.id] = node
        return node

    def find_entity_by_actor_key(
        self, *, workspace_id, entity_type, key_kind, value
    ):
        del workspace_id
        matched = [
            node
            for node in self.nodes.values()
            if node.entity_type == entity_type
            and node.lifecycle_state is NodeLifecycleState.ACTIVE
            and value in (node.attributes.get("actor") or {}).get(key_kind, [])
        ]
        return min(matched, key=lambda node: node.id) if matched else None

    def set_entity_attributes(self, *, workspace_id, node_id, attributes):
        del workspace_id
        node = replace(self.nodes[node_id], attributes=dict(attributes))
        self.nodes[node_id] = node
        return node

    def replace_node(self, node: KnowledgeNode) -> None:
        """테스트가 노드 상태를 바꿔 끼운다."""
        self.nodes[node.id] = node

    def add_alias(
        self, *, workspace_id, node_id, alias, normalized_alias, source
    ):
        del workspace_id, alias
        if (node_id, normalized_alias) not in self.aliases:
            self.aliases.append((node_id, normalized_alias))
            self.alias_sources.append((node_id, normalized_alias, source))


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


def _promoted_node(
    uow: FakeUnitOfWork,
    *,
    name: str,
    entity_type: str,
    node_id: uuid.UUID | None = None,
) -> KnowledgeNode:
    """사람이 승인해 만들어진 canonical_key 없는 노드를 재현한다.

    node_id를 주면 그 id로 만든다. alias 조회의 tie-break가 id 순이라
    어느 노드가 앞서는지 고정해야 하는 테스트가 쓴다.
    """
    node = KnowledgeNode(
        id=node_id if node_id is not None else uuid.uuid4(),
        workspace_id=WORKSPACE,
        node_kind=NodeKind.ENTITY,
        entity_type=entity_type,
        canonical_key=None,
        display_name=name,
    )
    uow.knowledge_nodes.replace_node(node)
    uow.knowledge_nodes.add_alias(
        workspace_id=WORKSPACE,
        node_id=node.id,
        alias=name,
        normalized_alias=normalize_name(name),
        source="system",
    )
    return node


def test_llm_candidate_reattaches_to_alias_of_keyless_node() -> None:
    """canonical_key 없는 노드에도 같은 이름 후보가 흡수된다."""
    uow = FakeUnitOfWork(
        [
            _candidate(
                name="결제 기능",
                entity_type="feature",
                method=ExtractionMethod.LLM,
            )
        ]
    )
    existing = _promoted_node(uow, name="결제 기능", entity_type="feature")

    result = resolve_entity_candidates(
        workspace_id=WORKSPACE, judge=None, uow=uow
    )

    assert result.nodes_created == 0
    assert result.candidates_merged == 1
    only = next(iter(uow.knowledge_candidates.resolved.values()))
    assert only == (EntityResolutionStatus.MERGED, existing.id)
    # alias는 이미 있으므로 재부착이 행을 늘리지 않는다.
    assert uow.knowledge_nodes.aliases == [
        (existing.id, normalize_name("결제 기능"))
    ]


def test_alias_hit_with_other_type_is_not_absorbed() -> None:
    """이름만 같고 type이 다르면 흡수하지 않는다."""
    uow = FakeUnitOfWork(
        [
            _candidate(
                name="결제 기능",
                entity_type="feature",
                method=ExtractionMethod.LLM,
            )
        ]
    )
    _promoted_node(uow, name="결제 기능", entity_type="system")

    result = resolve_entity_candidates(
        workspace_id=WORKSPACE, judge=None, uow=uow
    )

    assert result.candidates_merged == 0
    assert uow.knowledge_candidates.resolved == {}


def test_alias_reattach_finds_same_type_behind_other_type() -> None:
    """다른 type 노드가 id 순으로 앞서도 같은 type 노드로 흡수된다."""
    uow = FakeUnitOfWork(
        [
            _candidate(
                name="결제 기능",
                entity_type="feature",
                method=ExtractionMethod.LLM,
            )
        ]
    )
    front, behind = sorted([uuid.uuid4(), uuid.uuid4()])
    _promoted_node(
        uow, name="결제 기능", entity_type="system", node_id=front
    )
    target = _promoted_node(
        uow, name="결제 기능", entity_type="feature", node_id=behind
    )

    result = resolve_entity_candidates(
        workspace_id=WORKSPACE, judge=None, uow=uow
    )

    assert result.candidates_merged == 1
    only = next(iter(uow.knowledge_candidates.resolved.values()))
    assert only == (EntityResolutionStatus.MERGED, target.id)


def test_alias_hit_on_merged_node_is_not_absorbed() -> None:
    """흡수된 노드는 재부착 대상이 아니다."""
    uow = FakeUnitOfWork(
        [
            _candidate(
                name="결제 기능",
                entity_type="feature",
                method=ExtractionMethod.LLM,
            )
        ]
    )
    node = _promoted_node(uow, name="결제 기능", entity_type="feature")
    uow.knowledge_nodes.replace_node(
        replace(
            node,
            lifecycle_state=NodeLifecycleState.MERGED,
            merged_into_node_id=uuid.uuid4(),
        )
    )

    result = resolve_entity_candidates(
        workspace_id=WORKSPACE, judge=None, uow=uow
    )

    assert result.candidates_merged == 0
    assert uow.knowledge_candidates.resolved == {}


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


def test_false_verdict_logs_group_and_reason() -> None:
    """same=false 판정도 그룹 이름과 이유가 감사 로그에 남는다."""
    judge = FakeJudge(
        IdentityVerdict(
            same=False,
            reason="속성이 달라 다른 대상이다",
            proposed_type=None,
            proposed_name=None,
        )
    )
    uow = FakeUnitOfWork(_slack_group())

    with capture_logs() as logs:
        resolve_entity_candidates(workspace_id=WORKSPACE, judge=judge, uow=uow)

    judged = [entry for entry in logs if entry["event"] == "identity_group_judged"]
    assert len(judged) == 1
    assert judged[0]["group"] == "slack"
    assert judged[0]["same"] is False
    assert judged[0]["reason"] == "속성이 달라 다른 대상이다"


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


def test_single_member_group_is_promoted_to_node() -> None:
    """관찰이 하나뿐인 이름은 사람 없이 노드로 승격된다."""
    judge = FakeJudge(
        IdentityVerdict(same=False, reason="판정할 일이 없어야 한다")
    )
    candidate = _candidate(
        name="결제 기능",
        entity_type="feature",
        method=ExtractionMethod.LLM,
    )
    uow = FakeUnitOfWork([candidate])

    with capture_logs() as logs:
        result = resolve_entity_candidates(
            workspace_id=WORKSPACE, judge=judge, uow=uow
        )

    assert result.singletons_promoted == 1
    # 결정론 단계는 아무것도 발급하지 않았다.
    assert result.nodes_created == 0
    (node,) = uow.knowledge_nodes.nodes.values()
    assert node.entity_type == "feature"
    assert node.display_name == "결제 기능"
    # canonical_key는 비운다 — 재부착은 alias가 맡는다.
    assert node.canonical_key is None
    assert uow.knowledge_candidates.resolved == {
        candidate.id: (EntityResolutionStatus.ACCEPTED, node.id)
    }
    assert uow.knowledge_nodes.alias_sources == [
        (node.id, normalize_name("결제 기능"), "extractor")
    ]
    promoted = [
        entry for entry in logs if entry["event"] == "entity_singleton_promoted"
    ]
    assert len(promoted) == 1
    assert promoted[0]["candidate_id"] == str(candidate.id)
    assert promoted[0]["node_id"] == str(node.id)
    assert promoted[0]["normalized_name"] == normalize_name("결제 기능")


def test_promotion_leaves_multi_member_groups_to_judge() -> None:
    """복수 후보 그룹은 그대로 판정 경로를 탄다."""
    judge = FakeJudge(
        IdentityVerdict(
            same=True,
            reason="같은 제품이다",
            proposed_type="integration",
            proposed_name="Slack",
        )
    )
    alone = _candidate(
        name="결제 기능",
        entity_type="feature",
        method=ExtractionMethod.LLM,
        minutes=2,
    )
    uow = FakeUnitOfWork([*_slack_group(), alone])

    result = resolve_entity_candidates(
        workspace_id=WORKSPACE, judge=judge, uow=uow
    )

    assert result.singletons_promoted == 1
    assert result.groups_judged == 1
    assert result.proposals_created == 1
    # 판정은 복수 그룹에만 갔고, 그 후보들은 pending으로 남는다.
    (group,) = judge.calls
    assert {member.proposed_name for member in group} == {"Slack", "slack"}
    assert set(uow.knowledge_candidates.resolved) == {alone.id}


def test_promoted_candidate_is_not_promoted_again() -> None:
    """승격된 후보는 pending이 아니라 재실행이 노드를 더 만들지 않는다."""
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

    first = resolve_entity_candidates(
        workspace_id=WORKSPACE, judge=judge, uow=uow
    )
    second = resolve_entity_candidates(
        workspace_id=WORKSPACE, judge=judge, uow=uow
    )

    assert first.singletons_promoted == 1
    assert second.singletons_promoted == 0
    assert len(uow.knowledge_nodes.nodes) == 1
    assert len(uow.knowledge_nodes.aliases) == 1
