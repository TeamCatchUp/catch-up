from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import datetime
from datetime import timedelta
from datetime import timezone

from structlog.testing import capture_logs

from catchup.knowledge_maintenance.domain.entity_resolution import IdentityGroup
from catchup.knowledge_maintenance.domain.entity_resolution import IdentityPartition
from catchup.knowledge_maintenance.domain.entity_resolution import IdentityVerdict
from catchup.knowledge_maintenance.domain.entity_resolution import (
    PartitionContractError,
)
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
from catchup.knowledge_maintenance.ports.knowledge_nodes import ActiveEntityAlias
from catchup.knowledge_maintenance.ports.mutation_proposals import (
    MergeProposalAlreadyDecided,
)
from catchup.knowledge_maintenance.ports.name_embedder import NameEmbeddingError
from catchup.knowledge_maintenance.services.resolve_entity_candidates import (
    SYSTEM_REVIEWER,
)
from catchup.knowledge_maintenance.services.resolve_entity_candidates import (
    block_idempotency_key,
)
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
        self.alias_rows: list[tuple[uuid.UUID, str, str]] = []

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
        matched = [
            node
            for node in self.nodes.values()
            if node.workspace_id == workspace_id
            and node.entity_type == entity_type
            and node.lifecycle_state is NodeLifecycleState.ACTIVE
            and value in (node.attributes.get("actor") or {}).get(key_kind, [])
        ]
        # 실 조회는 created_at·id 순 첫 번째를 준다. fake가 만든 노드는
        # created_at이 비어 있으므로 같은 값으로 놓고 id 순으로 가른다.
        return (
            min(matched, key=lambda node: (node.created_at or NOW, node.id))
            if matched
            else None
        )

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
        del workspace_id
        if (node_id, normalized_alias) not in self.aliases:
            self.aliases.append((node_id, normalized_alias))
            self.alias_sources.append((node_id, normalized_alias, source))
            self.alias_rows.append((node_id, alias, normalized_alias))

    def list_active_entity_aliases(self, *, workspace_id):
        del workspace_id
        return [
            ActiveEntityAlias(
                node_id=node_id,
                entity_type=self.nodes[node_id].entity_type,
                alias=alias,
                normalized_alias=normalized_alias,
            )
            for node_id, alias, normalized_alias in sorted(
                self.alias_rows, key=lambda row: (row[0], row[2])
            )
            if self.nodes[node_id].node_kind is NodeKind.ENTITY
            and self.nodes[node_id].lifecycle_state is NodeLifecycleState.ACTIVE
            and self.nodes[node_id].entity_type is not None
        ]


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
            "reviewer": None,
            "resolver_metadata": dict(kwargs["resolver_metadata"]),
            "kwargs": kwargs,
        }
        return proposal_id

    def mark_merge_approved(self, *, workspace_id, proposal_id, reviewer):
        del workspace_id
        for record in self.proposals.values():
            if record["id"] != proposal_id:
                continue
            if record["status"] != "pending":
                raise MergeProposalAlreadyDecided(str(proposal_id))
            record["status"] = "approved"
            record["reviewer"] = reviewer
            return
        raise MergeProposalAlreadyDecided(str(proposal_id))


class FakeResolutionEventRepository:
    """사람의 되돌림 기록 조회를 흉내 낸다.

    `suppressed`가 참이면 어떤 구성을 물어도 되돌림이 있다고 답한다.
    물어본 member_hash를 남겨 두어 서비스가 어느 구성을 조회했는지
    테스트가 확인한다.
    """

    def __init__(self, *, suppressed: bool = False) -> None:
        self.suppressed = suppressed
        self.queried: list[str] = []

    def has_human_unmerge(self, *, workspace_id, member_hash):
        del workspace_id
        self.queried.append(member_hash)
        return self.suppressed


class FakeUnitOfWork:
    def __init__(self, candidates: list[StoredEntityCandidate]) -> None:
        self.knowledge_candidates = FakeCandidateRepository(candidates)
        self.knowledge_nodes = FakeNodeRepository()
        self.mutation_proposals = FakeProposalRepository()
        self.resolution_events = FakeResolutionEventRepository()
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


def _same_verdict_judge() -> FakeJudge:
    return FakeJudge(
        IdentityVerdict(
            same=True,
            reason="같은 제품이다",
            proposed_type="integration",
            proposed_name="Slack",
        )
    )


def test_auto_merge_approves_proposal_as_system() -> None:
    """자동 확정을 켜면 방금 쓴 병합 안건이 시스템 승인으로 끝맺는다."""
    uow = FakeUnitOfWork(_slack_group())

    result = resolve_entity_candidates(
        workspace_id=WORKSPACE,
        judge=_same_verdict_judge(),
        uow=uow,
        auto_merge_enabled=True,
    )

    assert result.proposals_created == 1
    stored = uow.mutation_proposals.proposals[group_idempotency_key("slack")]
    assert stored["status"] == "approved"
    assert stored["reviewer"] == "system:auto_merge"
    assert SYSTEM_REVIEWER == "system:auto_merge"


def test_auto_merge_off_leaves_proposal_pending() -> None:
    """자동 확정을 끄면 지금까지처럼 검토 대기로 남는다."""
    uow = FakeUnitOfWork(_slack_group())

    resolve_entity_candidates(
        workspace_id=WORKSPACE, judge=_same_verdict_judge(), uow=uow
    )

    stored = uow.mutation_proposals.proposals[group_idempotency_key("slack")]
    assert stored["status"] == "pending"
    assert stored["reviewer"] is None
    assert uow.resolution_events.queried == []


def test_auto_merge_suppressed_when_human_unmerged_same_members() -> None:
    """사람이 되돌린 구성은 자동 확정 대상에서 빠지고 계류로 남는다."""
    uow = FakeUnitOfWork(_slack_group())
    uow.resolution_events = FakeResolutionEventRepository(suppressed=True)

    with capture_logs() as logs:
        resolve_entity_candidates(
            workspace_id=WORKSPACE,
            judge=_same_verdict_judge(),
            uow=uow,
            auto_merge_enabled=True,
        )

    stored = uow.mutation_proposals.proposals[group_idempotency_key("slack")]
    assert stored["status"] == "pending"
    assert stored["reviewer"] is None
    # 조회한 구성이 이번 안건의 구성과 같은지 본다.
    assert uow.resolution_events.queried == [
        stored["resolver_metadata"]["member_hash"]
    ]
    suppressed = [
        entry for entry in logs if entry["event"] == "auto_merge_suppressed"
    ]
    assert len(suppressed) == 1
    assert suppressed[0]["workspace_id"] == WORKSPACE
    assert suppressed[0]["member_hash"] == (
        stored["resolver_metadata"]["member_hash"]
    )


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


def _actor_candidate(
    *,
    external_key: str,
    email: str | None,
    name: str = "팀원A",
    minutes: int = 0,
) -> StoredEntityCandidate:
    """행위자 후보 하나를 만든다. 저장 단계가 쓰는 attributes 모양이다."""
    attributes: dict[str, object] = {
        "external_key": external_key,
        "actor": {
            "source_entity_type": "channel_talk_user",
            "user_type": "member",
        },
    }
    if email is not None:
        attributes["email"] = email
    return StoredEntityCandidate(
        id=uuid.uuid4(),
        run_id=uuid.uuid4(),
        local_key="m1",
        proposed_type="customer",
        proposed_name=name,
        extraction_method=ExtractionMethod.DETERMINISTIC,
        raw_payload={"attributes": attributes},
        source_type="channel_talk",
        created_at=NOW + timedelta(minutes=minutes),
    )


def _actor_nodes(uow: FakeUnitOfWork) -> list[KnowledgeNode]:
    return [
        node
        for node in uow.knowledge_nodes.nodes.values()
        if node.entity_type == "customer"
    ]


def test_actor_candidates_with_same_email_share_one_node() -> None:
    """external_key가 달라도 이메일이 같으면 노드 하나로 모인다."""
    uow = FakeUnitOfWork(
        [
            _actor_candidate(external_key="ext-1", email="neo@x.com"),
            _actor_candidate(external_key="ext-2", email="neo@x.com", minutes=1),
        ]
    )

    result = resolve_entity_candidates(
        workspace_id=WORKSPACE,
        judge=None,
        uow=uow,
    )

    assert result.nodes_created == 1
    (node,) = _actor_nodes(uow)
    assert node.canonical_key == "channel_talk:customer:email:neo@x.com"
    assert node.attributes["actor"]["external_keys"] == ["ext-1", "ext-2"]
    assert result.candidates_accepted == 1
    assert result.candidates_merged == 1


def test_actor_without_email_falls_back_to_external_key() -> None:
    """이메일이 없으면 external_key가 동일성 키다."""
    uow = FakeUnitOfWork(
        [
            _actor_candidate(external_key="ext-7", email=None, name="엘리 708"),
            _actor_candidate(
                external_key="ext-7",
                email=None,
                name="엘리 708",
                minutes=1,
            ),
        ]
    )

    result = resolve_entity_candidates(
        workspace_id=WORKSPACE,
        judge=None,
        uow=uow,
    )

    assert result.nodes_created == 1
    (node,) = _actor_nodes(uow)
    assert node.canonical_key == "channel_talk:customer:external:ext-7"


def test_email_seen_later_attaches_to_external_key_node() -> None:
    """뒤늦게 이메일이 보이면 external_key로 만든 노드에 붙는다."""
    uow = FakeUnitOfWork(
        [
            _actor_candidate(external_key="ext-7", email=None),
            _actor_candidate(external_key="ext-7", email="late@x.com", minutes=1),
        ]
    )

    resolve_entity_candidates(workspace_id=WORKSPACE, judge=None, uow=uow)

    (node,) = _actor_nodes(uow)
    assert node.attributes["actor"]["emails"] == ["late@x.com"]


def test_actor_falls_back_to_canonical_key_before_creating() -> None:
    """행위자 키가 빗나가도 canonical_key가 같으면 새로 만들지 않는다.

    행위자 키 조회는 active 노드만 보지만 canonical_key 유일 index는
    lifecycle을 가리지 않는다. 그 틈으로 create를 부르면 index 위반으로
    해소 전체가 깨진다.
    """
    uow = FakeUnitOfWork(
        [_actor_candidate(external_key="ext-1", email="neo@x.com")]
    )
    existing = uow.knowledge_nodes.create_entity_node(
        workspace_id=WORKSPACE,
        entity_type="customer",
        canonical_key="channel_talk:customer:email:neo@x.com",
        display_name="팀원A",
        attributes={},
    )

    result = resolve_entity_candidates(
        workspace_id=WORKSPACE,
        judge=None,
        uow=uow,
    )

    assert list(uow.knowledge_nodes.nodes) == [existing.id]
    assert result.nodes_created == 0
    assert result.candidates_merged == 1
    node = uow.knowledge_nodes.nodes[existing.id]
    assert node.attributes["actor"]["emails"] == ["neo@x.com"]
    assert node.attributes["actor"]["external_keys"] == ["ext-1"]


def test_actor_resolution_never_calls_judge() -> None:
    """행위자 후보는 LLM 판정에 절대 올라가지 않는다."""
    judge = FakeJudge(
        IdentityVerdict(
            same=True,
            reason="쓰이면 안 된다",
            proposed_type="customer",
            proposed_name="팀원A",
        )
    )
    uow = FakeUnitOfWork(
        [
            _actor_candidate(external_key="a", email="a@x.com"),
            _actor_candidate(external_key="b", email="a@x.com", minutes=1),
        ]
    )

    resolve_entity_candidates(workspace_id=WORKSPACE, judge=judge, uow=uow)

    assert judge.calls == []


_DIMENSION = 16
# 같은 대상의 다른 표기끼리 주는 벡터다. 서로 완전히 같아 임계값을 넘고,
# 아래 자리 벡터들과는 겹치는 축이 없어 0이 된다.
_NEAR_VECTORS = {
    "google workspace": (1.0, 1.0) + (0.0,) * (_DIMENSION - 2),
    "결제": (0.0, 0.0, 1.0, 1.0) + (0.0,) * (_DIMENSION - 4),
}


class FakeNameEmbedder:
    """이름마다 정해진 벡터를 돌려준다.

    한 가족으로 지정한 이름들은 같은 벡터를 받아 한 블록으로 묶이고,
    나머지는 자기 자리만 1인 벡터를 받아 어느 것과도 닮지 않는다.
    """

    def __init__(self, families: dict[str, tuple[str, ...]] | None = None) -> None:
        self.family_by_name: dict[str, str] = {}
        for family, names in (families or {}).items():
            for name in names:
                self.family_by_name[name] = family
        self.calls: list[list[str]] = []
        self._axes: dict[str, int] = {}

    def embed(self, names):
        self.calls.append(list(names))
        return tuple(self._vector(name) for name in names)

    def _vector(self, name: str) -> tuple[float, ...]:
        family = self.family_by_name.get(name)
        if family is not None:
            return _NEAR_VECTORS[family]
        axis = self._axes.setdefault(name, 4 + len(self._axes))
        return tuple(
            1.0 if index == axis else 0.0 for index in range(_DIMENSION)
        )


class FailingNameEmbedder:
    def embed(self, names):
        del names
        raise NameEmbeddingError("임베딩 호출이 실패했다")


class FakePartitionJudge:
    """이름 앞 두 낱말이 같으면 한 정체라고 답한다."""

    def __init__(self, *, failing_types: tuple[str, ...] = ()) -> None:
        self.blocks: list = []
        self._failing_types = failing_types

    def judge(self, group):
        raise AssertionError("분할 경로는 예·아니오 판정을 부르지 않는다")

    def partition(self, block):
        self.blocks.append(block)
        if block.entity_type in self._failing_types:
            raise PartitionContractError("배정되지 않은 멤버가 있다")
        grouped: dict[str, list] = {}
        for member in block.members:
            grouped.setdefault(
                " ".join(member.name.split()[:2]), []
            ).append(member)
        return IdentityPartition(
            groups=tuple(
                IdentityGroup(
                    canonical_name="정규 이름 제안",
                    canonical_type=block.entity_type,
                    member_ids=tuple(
                        member.member_id for member in members
                    ),
                    reason="표기만 다른 같은 대상이다",
                )
                for _, members in sorted(grouped.items())
            )
        )


def _google_candidates() -> list[StoredEntityCandidate]:
    return [
        _candidate(
            name="Google Workspace 연동",
            entity_type="feature_request",
            method=ExtractionMethod.LLM,
        ),
        _candidate(
            name="Google Workspace 연동 지원",
            entity_type="feature_request",
            method=ExtractionMethod.LLM,
            minutes=1,
        ),
    ]


def _google_embedder() -> FakeNameEmbedder:
    return FakeNameEmbedder(
        families={
            "google workspace": (
                "Google Workspace 연동",
                "Google Workspace 연동 지원",
                "Google Workspace 커넥터",
            )
        }
    )


def test_similar_names_land_in_one_block_and_one_proposal() -> None:
    """표기가 다른 같은 대상이 한 블록으로 묶여 병합 제안이 된다."""
    judge = FakePartitionJudge()
    members = _google_candidates()
    uow = FakeUnitOfWork(members)

    result = resolve_entity_candidates(
        workspace_id=WORKSPACE,
        judge=judge,
        uow=uow,
        name_embedder=_google_embedder(),
    )

    assert result.blocks_formed == 1
    assert result.blocks_judged == 1
    assert result.blocks_failed == 0
    assert result.proposals_created == 1
    assert result.singletons_promoted == 0
    # 후보는 pending 유지 — 확정은 승인 트랜잭션의 일이다.
    assert uow.knowledge_candidates.resolved == {}

    key = block_idempotency_key(
        [f"candidate:{member.id}" for member in members]
    )
    kwargs = uow.mutation_proposals.proposals[key]["kwargs"]
    assert kwargs["representative_candidate_id"] == members[0].id
    assert kwargs["merge_candidate_ids"] == (members[1].id,)
    assert kwargs["merge_into_node_id"] is None
    assert kwargs["proposed_type"] == "feature_request"
    # 모델이 지은 이름은 제안 값으로만 남고 검토 문장에는 안 실린다.
    assert kwargs["proposed_name"] == "정규 이름 제안"
    assert "정규 이름 제안" not in kwargs["summary"]


def test_auto_merge_approves_block_proposal_as_system() -> None:
    """블록 판정이 낸 병합 안건도 자동 확정을 켜면 시스템이 승인한다."""
    uow = FakeUnitOfWork(_google_candidates())

    resolve_entity_candidates(
        workspace_id=WORKSPACE,
        judge=FakePartitionJudge(),
        uow=uow,
        name_embedder=_google_embedder(),
        auto_merge_enabled=True,
    )

    (stored,) = uow.mutation_proposals.proposals.values()
    assert stored["status"] == "approved"
    assert stored["reviewer"] == SYSTEM_REVIEWER


def test_candidate_matching_existing_node_becomes_duplicate_proposal() -> None:
    """기존 노드 별칭과 닮은 후보는 그 노드로 붙이는 제안이 된다."""
    judge = FakePartitionJudge()
    candidate = _candidate(
        name="Google Workspace 연동 지원",
        entity_type="feature_request",
        method=ExtractionMethod.LLM,
    )
    uow = FakeUnitOfWork([candidate])
    existing = _promoted_node(
        uow, name="Google Workspace 연동", entity_type="feature_request"
    )

    result = resolve_entity_candidates(
        workspace_id=WORKSPACE,
        judge=judge,
        uow=uow,
        name_embedder=_google_embedder(),
    )

    assert result.blocks_formed == 1
    assert result.proposals_created == 1
    assert result.singletons_promoted == 0
    (stored,) = uow.mutation_proposals.proposals.values()
    kwargs = stored["kwargs"]
    assert kwargs["merge_into_node_id"] == existing.id
    assert kwargs["representative_candidate_id"] == candidate.id
    assert kwargs["merge_candidate_ids"] == ()
    assert stored["resolver_metadata"]["merge_into_node_id"] == str(existing.id)


def test_other_entity_type_is_not_blocked_together() -> None:
    """종류가 다르면 이름이 닮아도 한 판정대에 오르지 않는다."""
    judge = FakePartitionJudge()
    uow = FakeUnitOfWork(
        [
            _candidate(
                name="Google Workspace 연동",
                entity_type="feature_request",
                method=ExtractionMethod.LLM,
            ),
            _candidate(
                name="Google Workspace 연동 지원",
                entity_type="faq_question",
                method=ExtractionMethod.LLM,
                minutes=1,
            ),
        ]
    )

    result = resolve_entity_candidates(
        workspace_id=WORKSPACE,
        judge=judge,
        uow=uow,
        name_embedder=_google_embedder(),
    )

    assert judge.blocks == []
    assert result.blocks_formed == 0
    assert result.proposals_created == 0
    assert result.singletons_promoted == 2


def test_partition_failure_isolates_only_that_block() -> None:
    """분할 계약 위반은 그 블록만 접고 나머지는 계속 간다."""
    judge = FakePartitionJudge(failing_types=("feature_request",))
    failing = _google_candidates()
    passing = [
        _candidate(
            name="결제 기능",
            entity_type="feature",
            method=ExtractionMethod.LLM,
            minutes=2,
        ),
        _candidate(
            name="결제 기능 개선",
            entity_type="feature",
            method=ExtractionMethod.LLM,
            minutes=3,
        ),
    ]
    uow = FakeUnitOfWork([*failing, *passing])
    embedder = FakeNameEmbedder(
        families={
            "google workspace": (
                "Google Workspace 연동",
                "Google Workspace 연동 지원",
            ),
            "결제": ("결제 기능", "결제 기능 개선"),
        }
    )

    result = resolve_entity_candidates(
        workspace_id=WORKSPACE,
        judge=judge,
        uow=uow,
        name_embedder=embedder,
    )

    assert result.blocks_formed == 2
    assert result.blocks_judged == 1
    assert result.blocks_failed == 1
    assert result.proposals_created == 1
    # 판정을 못 받은 후보는 승격하지 않고 그대로 둔다.
    assert result.singletons_promoted == 0
    assert uow.knowledge_candidates.resolved == {}
    assert uow.committed


def test_rerun_of_same_block_opens_no_new_event() -> None:
    """블록 구성이 그대로면 재실행이 안건을 새로 열지 않는다."""
    judge = FakePartitionJudge()
    members = _google_candidates()
    first_uow = FakeUnitOfWork(members)
    resolve_entity_candidates(
        workspace_id=WORKSPACE,
        judge=judge,
        uow=first_uow,
        name_embedder=_google_embedder(),
    )

    second_uow = FakeUnitOfWork(members)
    second_uow.mutation_proposals = first_uow.mutation_proposals
    result = resolve_entity_candidates(
        workspace_id=WORKSPACE,
        judge=judge,
        uow=second_uow,
        name_embedder=_google_embedder(),
    )

    assert result.proposals_created == 0
    assert result.proposals_abandoned == 0
    assert second_uow.mutation_proposals.abandoned == []
    assert len(second_uow.mutation_proposals.proposals) == 1


def test_embedding_failure_falls_back_to_exact_name_groups() -> None:
    """임베딩이 실패하면 정확 일치 경로로 물러난다."""
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
        workspace_id=WORKSPACE,
        judge=judge,
        uow=uow,
        name_embedder=FailingNameEmbedder(),
    )

    assert result.blocks_formed == 0
    assert result.groups_judged == 1
    assert result.proposals_created == 1


def test_group_with_two_existing_nodes_abstains_from_merge() -> None:
    """기존 노드가 둘 이상 섞인 그룹은 병합하지 않고 계류한다."""
    judge = FakePartitionJudge()
    candidate = _candidate(
        name="Google Workspace 연동 지원",
        entity_type="feature_request",
        method=ExtractionMethod.LLM,
    )
    uow = FakeUnitOfWork([candidate])
    _promoted_node(
        uow, name="Google Workspace 연동", entity_type="feature_request"
    )
    _promoted_node(
        uow, name="Google Workspace 커넥터", entity_type="feature_request"
    )

    result = resolve_entity_candidates(
        workspace_id=WORKSPACE,
        judge=judge,
        uow=uow,
        name_embedder=_google_embedder(),
    )

    assert result.blocks_formed == 1
    assert result.blocks_judged == 1
    assert result.groups_abstained == 1
    assert result.proposals_created == 0
    assert uow.mutation_proposals.proposals == {}
    # 계류이므로 승격도 해소도 없다.
    assert result.singletons_promoted == 0
    assert uow.knowledge_candidates.resolved == {}
    assert len(uow.knowledge_nodes.nodes) == 2


def test_group_with_two_aliases_of_one_node_still_merges() -> None:
    """같은 노드의 별칭이 여럿이어도 노드가 하나면 병합 제안을 쓴다."""
    judge = FakePartitionJudge()
    candidate = _candidate(
        name="Google Workspace 연동 지원",
        entity_type="feature_request",
        method=ExtractionMethod.LLM,
    )
    uow = FakeUnitOfWork([candidate])
    existing = _promoted_node(
        uow, name="Google Workspace 연동", entity_type="feature_request"
    )
    uow.knowledge_nodes.add_alias(
        workspace_id=WORKSPACE,
        node_id=existing.id,
        alias="Google Workspace 커넥터",
        normalized_alias=normalize_name("Google Workspace 커넥터"),
        source="system",
    )

    result = resolve_entity_candidates(
        workspace_id=WORKSPACE,
        judge=judge,
        uow=uow,
        name_embedder=_google_embedder(),
    )

    assert result.groups_abstained == 0
    assert result.proposals_created == 1
    (stored,) = uow.mutation_proposals.proposals.values()
    assert stored["kwargs"]["merge_into_node_id"] == existing.id
