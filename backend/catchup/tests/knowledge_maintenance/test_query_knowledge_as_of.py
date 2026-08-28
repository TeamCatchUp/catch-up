from __future__ import annotations

import uuid
from datetime import datetime
from datetime import timedelta
from datetime import timezone

from structlog.testing import capture_logs

from catchup.knowledge_maintenance.domain.knowledge_node import KnowledgeNode
from catchup.knowledge_maintenance.domain.knowledge_node import NodeKind
from catchup.knowledge_maintenance.domain.knowledge_node import NodeLifecycleState
from catchup.knowledge_maintenance.ports.knowledge_candidates import AsOfClaim
from catchup.knowledge_maintenance.services.query_knowledge_as_of import (
    MATCHED_BY_NODE_ID,
)
from catchup.knowledge_maintenance.services.query_knowledge_as_of import (
    SIMILARITY_CANDIDATE_LIMIT,
)
from catchup.knowledge_maintenance.services.query_knowledge_as_of import (
    SIMILARITY_THRESHOLD,
)
from catchup.knowledge_maintenance.services.query_knowledge_as_of import (
    query_claims_as_of,
)
from catchup.knowledge_maintenance.services.query_knowledge_as_of import (
    query_claims_history,
)
from catchup.knowledge_maintenance.services.query_knowledge_as_of import (
    query_claims_of_node,
)
from catchup.knowledge_maintenance.services.query_knowledge_as_of import (
    query_claims_of_node_history,
)

WORKSPACE = 1
AT = datetime(2026, 8, 1, 9, 0, tzinfo=timezone.utc)
JULY_1 = datetime(2026, 7, 1, tzinfo=timezone.utc)
JULY_15 = datetime(2026, 7, 15, tzinfo=timezone.utc)


def _node(
    *,
    canonical_key: str | None = None,
    display_name: str | None = "오픈 API",
) -> KnowledgeNode:
    return KnowledgeNode(
        id=uuid.uuid4(),
        workspace_id=WORKSPACE,
        node_kind=NodeKind.ENTITY,
        entity_type="feature",
        canonical_key=canonical_key,
        display_name=display_name,
    )


def _claim(
    predicate: str = "rate_limit",
    value: object = 60,
    *,
    valid_from: datetime | None = None,
    valid_to: datetime | None = None,
) -> AsOfClaim:
    return AsOfClaim(
        claim_id=uuid.uuid4(),
        predicate=predicate,
        value_type="number",
        value=value,
        statement=f"{predicate}은 {value}이다",
        valid_from=valid_from,
        valid_to=valid_to,
    )


class FakeNodeRepository:
    """canonical key와 정규화 alias의 정확 일치만 재현한다.

    실 DB의 두 조회 모두 UNIQUE·정확 일치 조회라, 부분 일치나 대소문자
    보정을 넣으면 서비스가 실제로 하지 않는 매칭을 통과시킨다.
    """

    def __init__(
        self,
        *,
        by_canonical_key: dict[str, KnowledgeNode] | None = None,
        by_alias: dict[str, KnowledgeNode] | None = None,
        by_id: dict[uuid.UUID, KnowledgeNode] | None = None,
    ) -> None:
        self.by_canonical_key = dict(by_canonical_key or {})
        self.by_alias = dict(by_alias or {})
        self.by_id = dict(by_id or {})
        self.canonical_key_calls: list[str] = []
        self.alias_calls: list[str] = []
        self.id_calls: list[uuid.UUID] = []
        self.similarity_calls: list[dict] = []

    def get_entity_by_id(
        self,
        *,
        workspace_id: int,
        node_id: uuid.UUID,
    ) -> KnowledgeNode | None:
        """node id 조회를 흉내 낸다. lifecycle은 거르지 않는다.

        실물 SQL도 거르지 않는다. 살아 있는 노드만 쓸지는 서비스가
        정하므로, fake가 미리 걸러 내면 그 판단을 검증할 수 없다.
        """
        del workspace_id
        self.id_calls.append(node_id)
        return self.by_id.get(node_id)

    def get_entity_by_canonical_key(
        self,
        *,
        workspace_id: int,
        canonical_key: str,
    ) -> KnowledgeNode | None:
        del workspace_id
        self.canonical_key_calls.append(canonical_key)
        return self.by_canonical_key.get(canonical_key)

    def find_entity_by_normalized_alias(
        self,
        *,
        workspace_id: int,
        normalized_alias: str,
        entity_type: str | None = None,
    ) -> KnowledgeNode | None:
        del workspace_id
        self.alias_calls.append(normalized_alias)
        found = self.by_alias.get(normalized_alias)
        if found is None:
            return None
        if entity_type is not None and found.entity_type != entity_type:
            return None
        return found

    def find_entity_candidates_by_similarity(
        self,
        *,
        workspace_id: int,
        normalized_query: str,
        threshold: float,
        limit: int,
    ) -> list[tuple[KnowledgeNode, float]]:
        """유사 후보 조회를 흉내 낸다. 점수 계산은 실물이 아니다.

        실물은 pg_bigm의 bigram 유사도이고 여기서는 공백 토큰 겹침
        비율이다. 점수의 절대값은 실 DB와 다르므로 서비스의 문턱값
        판단을 이 fake로 검증하면 안 된다. 대신 실 DB가 보장하는
        구조 규칙(노드 단위 MAX 1행, active만, threshold 이상,
        점수 내림차순·node id 오름차순, limit)은 그대로 지킨다.
        """
        del workspace_id
        self.similarity_calls.append(
            {
                "normalized_query": normalized_query,
                "threshold": threshold,
                "limit": limit,
            }
        )
        query_tokens = set(normalized_query.split())
        best: dict[uuid.UUID, tuple[KnowledgeNode, float]] = {}
        for alias, node in self.by_alias.items():
            if node.lifecycle_state is not NodeLifecycleState.ACTIVE:
                continue
            alias_tokens = set(alias.split())
            union = query_tokens | alias_tokens
            shared = len(query_tokens & alias_tokens)
            score = shared / len(union) if union else 0.0
            if score < threshold:
                continue
            found = best.get(node.id)
            if found is None or score > found[1]:
                best[node.id] = (node, score)

        ranked = sorted(best.values(), key=lambda item: (-item[1], item[0].id))
        return ranked[:limit]


class FakeClaimRepository:
    """as-of는 구간 술어를, history는 구간 무시를 그대로 흉내 낸다.

    실 DB에서 두 reader를 가르는 것은 구간 조건 하나뿐이다. fake가
    as-of에서도 구간을 안 거르면 닫힌 claim이 두 경로에서 똑같이 나와,
    history가 실제로 넓은지 검증하지 못한다.
    """

    def __init__(self, claims: tuple[AsOfClaim, ...] = ()) -> None:
        self.claims = claims
        self.calls: list[dict] = []
        self.history_calls: list[dict] = []

    def find_accepted_claims_as_of(
        self,
        *,
        workspace_id: int,
        subject_node_id: uuid.UUID,
        at: datetime,
        predicate: str | None = None,
    ) -> tuple[AsOfClaim, ...]:
        self.calls.append(
            {
                "workspace_id": workspace_id,
                "subject_node_id": subject_node_id,
                "at": at,
                "predicate": predicate,
            }
        )
        return tuple(
            claim
            for claim in self._filter_by_predicate(predicate)
            if (claim.valid_from is None or claim.valid_from <= at)
            and (claim.valid_to is None or claim.valid_to > at)
        )

    def find_accepted_claims_history(
        self,
        *,
        workspace_id: int,
        subject_node_id: uuid.UUID,
        predicate: str | None = None,
    ) -> tuple[AsOfClaim, ...]:
        self.history_calls.append(
            {
                "workspace_id": workspace_id,
                "subject_node_id": subject_node_id,
                "predicate": predicate,
            }
        )
        return tuple(
            sorted(
                self._filter_by_predicate(predicate),
                key=lambda claim: (
                    claim.valid_from is not None,
                    claim.valid_from or AT,
                ),
            )
        )

    def _filter_by_predicate(
        self, predicate: str | None
    ) -> tuple[AsOfClaim, ...]:
        if predicate is None:
            return self.claims
        return tuple(
            claim for claim in self.claims if claim.predicate == predicate
        )


class FakeUnitOfWork:
    def __init__(
        self,
        *,
        nodes: FakeNodeRepository | None = None,
        claims: FakeClaimRepository | None = None,
    ) -> None:
        self.knowledge_nodes = nodes or FakeNodeRepository()
        self.knowledge_candidates = claims or FakeClaimRepository()
        self.entered = 0

    def __enter__(self):
        self.entered += 1
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return None

    def commit(self) -> None:
        raise AssertionError("read path must not commit")


def test_matches_canonical_key_first() -> None:
    """canonical key와 alias 양쪽에 걸리면 canonical key가 이긴다."""
    canonical_node = _node(canonical_key="feature:오픈 api")
    alias_node = _node(canonical_key="feature:다른 것")
    uow = FakeUnitOfWork(
        nodes=FakeNodeRepository(
            by_canonical_key={"feature:오픈 api": canonical_node},
            by_alias={"feature:오픈 api": alias_node},
        ),
        claims=FakeClaimRepository((_claim(),)),
    )

    with capture_logs() as logs:
        result = query_claims_as_of(
            workspace_id=WORKSPACE,
            subject="feature:오픈 api",
            at=AT,
            uow=uow,
        )

    assert result.subject is not None
    assert result.subject.node_id == canonical_node.id
    assert result.subject.matched_by == "canonical_key"
    assert result.subject.entity_type == "feature"
    assert result.subject.display_name == "오픈 API"
    assert result.as_of == AT
    assert len(result.claims) == 1
    assert uow.knowledge_nodes.alias_calls == []

    entries = [
        log for log in logs if log["event"] == "knowledge_as_of_queried"
    ]
    assert len(entries) == 1
    assert entries[0]["workspace_id"] == WORKSPACE
    assert entries[0]["subject"] == "feature:오픈 api"
    assert entries[0]["matched_by"] == "canonical_key"
    assert entries[0]["claim_count"] == 1


def test_falls_back_to_alias() -> None:
    """canonical key가 없으면 정규화한 입력으로 alias를 찾는다."""
    alias_node = _node()
    uow = FakeUnitOfWork(
        nodes=FakeNodeRepository(by_alias={"캐치업 오픈 api": alias_node}),
        claims=FakeClaimRepository((_claim(), _claim("owner", "결제팀"))),
    )

    result = query_claims_as_of(
        workspace_id=WORKSPACE,
        subject="  캐치업   오픈 API  ",
        at=AT,
        uow=uow,
    )

    assert result.subject is not None
    assert result.subject.node_id == alias_node.id
    assert result.subject.matched_by == "alias"
    assert uow.knowledge_nodes.alias_calls == ["캐치업 오픈 api"]
    assert len(result.claims) == 2


def test_no_match_returns_empty() -> None:
    """둘 다 미스면 subject 없이 빈 claim과 as_of만 남는다."""
    uow = FakeUnitOfWork(claims=FakeClaimRepository((_claim(),)))

    with capture_logs() as logs:
        result = query_claims_as_of(
            workspace_id=WORKSPACE,
            subject="없는 이름",
            at=AT,
            uow=uow,
        )

    assert result.subject is None
    assert result.claims == ()
    assert result.as_of == AT
    assert uow.knowledge_candidates.calls == []

    entry = next(
        log for log in logs if log["event"] == "knowledge_as_of_queried"
    )
    assert entry["matched_by"] is None
    assert entry["claim_count"] == 0


def test_at_defaults_to_now() -> None:
    """at을 주지 않으면 호출 시각을 한 번 고정해 reader까지 그대로 쓴다."""
    node = _node(canonical_key="feature:오픈 api")
    uow = FakeUnitOfWork(
        nodes=FakeNodeRepository(
            by_canonical_key={"feature:오픈 api": node},
        ),
    )

    before = datetime.now(timezone.utc)
    result = query_claims_as_of(
        workspace_id=WORKSPACE,
        subject="feature:오픈 api",
        uow=uow,
    )
    after = datetime.now(timezone.utc)

    assert before - timedelta(seconds=1) <= result.as_of <= after
    assert result.as_of.tzinfo is not None
    assert uow.knowledge_candidates.calls[0]["at"] == result.as_of


def test_predicate_filter_passthrough() -> None:
    """predicate 인자는 걸러내지 않고 reader로 그대로 넘어간다."""
    node = _node(canonical_key="feature:오픈 api")
    uow = FakeUnitOfWork(
        nodes=FakeNodeRepository(
            by_canonical_key={"feature:오픈 api": node},
        ),
        claims=FakeClaimRepository((_claim(), _claim("owner", "결제팀"))),
    )

    result = query_claims_as_of(
        workspace_id=WORKSPACE,
        subject="feature:오픈 api",
        at=AT,
        predicate="owner",
        uow=uow,
    )

    assert uow.knowledge_candidates.calls[0]["predicate"] == "owner"
    assert [claim.predicate for claim in result.claims] == ["owner"]


def _history_uow(claims: tuple[AsOfClaim, ...]) -> FakeUnitOfWork:
    node = _node(canonical_key="feature:오픈 api")
    return FakeUnitOfWork(
        nodes=FakeNodeRepository(
            by_canonical_key={"feature:오픈 api": node},
        ),
        claims=FakeClaimRepository(claims),
    )


def test_history_includes_closed_claims_that_as_of_drops() -> None:
    """닫힌 claim은 as-of에선 빠지고 history에선 구간과 함께 나온다."""
    closed = _claim("rate_limit", 30, valid_from=JULY_1, valid_to=JULY_15)
    live = _claim("rate_limit", 60, valid_from=JULY_15)
    uow = _history_uow((closed, live))

    as_of = query_claims_as_of(
        workspace_id=WORKSPACE,
        subject="feature:오픈 api",
        at=AT,
        uow=uow,
    )
    history = query_claims_history(
        workspace_id=WORKSPACE,
        subject="feature:오픈 api",
        uow=uow,
    )

    assert [claim.claim_id for claim in as_of.claims] == [live.claim_id]
    assert [claim.claim_id for claim in history.claims] == [
        closed.claim_id,
        live.claim_id,
    ]
    by_id = {claim.claim_id: claim for claim in history.claims}
    assert by_id[closed.claim_id].valid_from == JULY_1
    assert by_id[closed.claim_id].valid_to == JULY_15
    assert by_id[live.claim_id].valid_to is None


def test_history_as_of_is_the_call_time_not_a_filter() -> None:
    """history의 as_of는 조회 시각 기록일 뿐 구간을 자르지 않는다."""
    closed = _claim("rate_limit", 30, valid_from=JULY_1, valid_to=JULY_15)
    uow = _history_uow((closed,))

    before = datetime.now(timezone.utc)
    result = query_claims_history(
        workspace_id=WORKSPACE,
        subject="feature:오픈 api",
        uow=uow,
    )
    after = datetime.now(timezone.utc)

    assert before - timedelta(seconds=1) <= result.as_of <= after
    assert result.as_of.tzinfo is not None
    assert [claim.claim_id for claim in result.claims] == [closed.claim_id]
    assert uow.knowledge_candidates.calls == []


def test_history_matches_subject_like_as_of() -> None:
    """subject 매칭 규칙은 as-of와 같은 헬퍼를 그대로 쓴다."""
    alias_node = _node()
    uow = FakeUnitOfWork(
        nodes=FakeNodeRepository(by_alias={"캐치업 오픈 api": alias_node}),
        claims=FakeClaimRepository((_claim(),)),
    )

    result = query_claims_history(
        workspace_id=WORKSPACE,
        subject="  캐치업   오픈 API  ",
        uow=uow,
    )

    assert result.subject is not None
    assert result.subject.node_id == alias_node.id
    assert result.subject.matched_by == "alias"
    assert uow.knowledge_nodes.alias_calls == ["캐치업 오픈 api"]


def test_history_no_match_returns_empty_and_logs() -> None:
    """대상을 못 찾으면 reader를 부르지 않고 빈 결과를 남긴다."""
    uow = FakeUnitOfWork(claims=FakeClaimRepository((_claim(),)))

    with capture_logs() as logs:
        result = query_claims_history(
            workspace_id=WORKSPACE,
            subject="없는 이름",
            uow=uow,
        )

    assert result.subject is None
    assert result.claims == ()
    assert uow.knowledge_candidates.history_calls == []

    entry = next(
        log for log in logs if log["event"] == "knowledge_history_queried"
    )
    assert entry["workspace_id"] == WORKSPACE
    assert entry["subject"] == "없는 이름"
    assert entry["matched_by"] is None
    assert entry["claim_count"] == 0


def test_history_predicate_filter_passthrough() -> None:
    """predicate 인자는 history reader로 그대로 넘어간다."""
    uow = _history_uow((_claim(), _claim("owner", "결제팀")))

    with capture_logs() as logs:
        result = query_claims_history(
            workspace_id=WORKSPACE,
            subject="feature:오픈 api",
            predicate="owner",
            uow=uow,
        )

    assert uow.knowledge_candidates.history_calls[0]["predicate"] == "owner"
    assert [claim.predicate for claim in result.claims] == ["owner"]

    entry = next(
        log for log in logs if log["event"] == "knowledge_history_queried"
    )
    assert entry["predicate"] == "owner"
    assert entry["claim_count"] == 1


def test_exact_match_skips_similarity_lookup() -> None:
    """정확 일치가 되면 유사 후보 조회 자체를 부르지 않는다."""
    node = _node(canonical_key="feature:오픈 api")
    uow = FakeUnitOfWork(
        nodes=FakeNodeRepository(
            by_canonical_key={"feature:오픈 api": node},
            by_alias={"캐치업 오픈 api 결제": _node()},
        ),
        claims=FakeClaimRepository((_claim(),)),
    )

    with capture_logs() as logs:
        result = query_claims_as_of(
            workspace_id=WORKSPACE,
            subject="feature:오픈 api",
            at=AT,
            uow=uow,
        )

    assert result.similar_candidates == ()
    assert uow.knowledge_nodes.similarity_calls == []

    entry = next(
        log for log in logs if log["event"] == "knowledge_as_of_queried"
    )
    assert entry["similar_candidate_count"] == 0
    assert entry["top_similarity_score"] is None


def test_alias_match_skips_similarity_lookup() -> None:
    """alias로 걸려도 유사 후보 조회는 일어나지 않는다."""
    alias_node = _node()
    uow = FakeUnitOfWork(
        nodes=FakeNodeRepository(by_alias={"캐치업 오픈 api": alias_node}),
        claims=FakeClaimRepository((_claim(),)),
    )

    result = query_claims_as_of(
        workspace_id=WORKSPACE,
        subject="  캐치업   오픈 API  ",
        at=AT,
        uow=uow,
    )

    assert result.similar_candidates == ()
    assert uow.knowledge_nodes.similarity_calls == []


def test_miss_returns_similar_candidates_without_deciding() -> None:
    """정확 일치가 없으면 유사 후보만 동반한다. 확정은 하지 않는다."""
    similar = _node(display_name="캐치업 오픈 API 결제")
    uow = FakeUnitOfWork(
        nodes=FakeNodeRepository(
            by_alias={"캐치업 오픈 api 결제": similar},
        ),
        claims=FakeClaimRepository((_claim(),)),
    )

    with capture_logs() as logs:
        result = query_claims_as_of(
            workspace_id=WORKSPACE,
            subject="캐치업 오픈 API",
            at=AT,
            uow=uow,
        )

    # 후보가 있어도 subject는 여전히 None이고 claim은 비어 있다.
    assert result.subject is None
    assert result.claims == ()
    assert uow.knowledge_candidates.calls == []

    assert len(result.similar_candidates) == 1
    candidate = result.similar_candidates[0]
    assert candidate.node_id == similar.id
    assert candidate.display_name == "캐치업 오픈 API 결제"
    assert candidate.entity_type == "feature"
    assert candidate.score > 0.0

    call = uow.knowledge_nodes.similarity_calls[0]
    assert call["normalized_query"] == "캐치업 오픈 api"
    assert call["threshold"] == SIMILARITY_THRESHOLD
    assert call["limit"] == SIMILARITY_CANDIDATE_LIMIT

    entry = next(
        log for log in logs if log["event"] == "knowledge_as_of_queried"
    )
    assert entry["matched_by"] is None
    assert entry["claim_count"] == 0
    assert entry["similar_candidate_count"] == 1
    assert entry["top_similarity_score"] == candidate.score


def test_miss_without_similar_nodes_stays_empty() -> None:
    """비슷한 것도 없으면 후보는 빈 튜플 그대로다."""
    uow = FakeUnitOfWork(
        nodes=FakeNodeRepository(by_alias={"완전히 다른 이름": _node()}),
    )

    result = query_claims_as_of(
        workspace_id=WORKSPACE,
        subject="캐치업 오픈 API",
        at=AT,
        uow=uow,
    )

    assert result.subject is None
    assert result.similar_candidates == ()
    assert uow.knowledge_nodes.similarity_calls != []


def test_history_miss_returns_similar_candidates() -> None:
    """history도 같은 규칙으로 유사 후보를 동반한다."""
    similar = _node(display_name="캐치업 오픈 API 결제")
    uow = FakeUnitOfWork(
        nodes=FakeNodeRepository(
            by_alias={"캐치업 오픈 api 결제": similar},
        ),
        claims=FakeClaimRepository((_claim(),)),
    )

    with capture_logs() as logs:
        result = query_claims_history(
            workspace_id=WORKSPACE,
            subject="캐치업 오픈 API",
            uow=uow,
        )

    assert result.subject is None
    assert result.claims == ()
    assert uow.knowledge_candidates.history_calls == []
    assert [item.node_id for item in result.similar_candidates] == [similar.id]

    entry = next(
        log for log in logs if log["event"] == "knowledge_history_queried"
    )
    assert entry["similar_candidate_count"] == 1
    assert entry["top_similarity_score"] == result.similar_candidates[0].score


def test_history_exact_match_skips_similarity_lookup() -> None:
    """history도 정확 일치면 유사 조회를 부르지 않는다."""
    node = _node(canonical_key="feature:오픈 api")
    uow = FakeUnitOfWork(
        nodes=FakeNodeRepository(
            by_canonical_key={"feature:오픈 api": node},
            by_alias={"캐치업 오픈 api 결제": _node()},
        ),
        claims=FakeClaimRepository((_claim(),)),
    )

    result = query_claims_history(
        workspace_id=WORKSPACE,
        subject="feature:오픈 api",
        uow=uow,
    )

    assert result.similar_candidates == ()
    assert uow.knowledge_nodes.similarity_calls == []


def test_include_similar_off_never_touches_the_similarity_repository() -> None:
    """off면 miss여도 유사 후보 SQL 자체를 부르지 않는다.

    이 조회는 workspace의 alias 전부를 훑는다. 후보를 쓰지 않을
    호출자에게는 그 비용이 통째로 낭비이고, 되짚기 없는 기준선을
    재려면 그 비용까지 빠져야 한다.
    """
    uow = FakeUnitOfWork(
        nodes=FakeNodeRepository(
            by_alias={"캐치업 오픈 api 결제": _node()},
        ),
        claims=FakeClaimRepository((_claim(),)),
    )

    as_of_result = query_claims_as_of(
        workspace_id=WORKSPACE,
        subject="캐치업 오픈 API",
        at=AT,
        include_similar=False,
        uow=uow,
    )
    history_result = query_claims_history(
        workspace_id=WORKSPACE,
        subject="캐치업 오픈 API",
        include_similar=False,
        uow=uow,
    )

    assert as_of_result.subject is None
    assert history_result.subject is None
    assert as_of_result.similar_candidates == ()
    assert history_result.similar_candidates == ()
    assert uow.knowledge_nodes.similarity_calls == []


def test_include_similar_defaults_to_on() -> None:
    """인자를 주지 않으면 기존 동작 그대로 후보를 조회한다."""
    uow = FakeUnitOfWork(
        nodes=FakeNodeRepository(
            by_alias={"캐치업 오픈 api 결제": _node()},
        ),
    )

    result = query_claims_as_of(
        workspace_id=WORKSPACE,
        subject="캐치업 오픈 API",
        at=AT,
        uow=uow,
    )

    assert result.similar_candidates != ()
    assert uow.knowledge_nodes.similarity_calls != []


def test_node_read_uses_the_given_id_without_resolving_a_name() -> None:
    """node id 조회는 이름 해소를 전혀 거치지 않는다."""
    node = _node(canonical_key="feature:오픈 api")
    uow = FakeUnitOfWork(
        nodes=FakeNodeRepository(by_id={node.id: node}),
        claims=FakeClaimRepository((_claim(),)),
    )

    result = query_claims_of_node(
        workspace_id=WORKSPACE,
        node_id=node.id,
        at=AT,
        uow=uow,
    )

    assert result.subject is not None
    assert result.subject.node_id == node.id
    assert result.subject.matched_by == MATCHED_BY_NODE_ID
    assert result.similar_candidates == ()
    assert len(result.claims) == 1
    assert uow.knowledge_nodes.id_calls == [node.id]
    assert uow.knowledge_nodes.canonical_key_calls == []
    assert uow.knowledge_nodes.alias_calls == []
    assert uow.knowledge_nodes.similarity_calls == []


def test_node_history_read_uses_the_history_reader() -> None:
    """node id history 조회는 닫힌 accepted까지 읽는다."""
    node = _node()
    closed = _claim(valid_from=JULY_1, valid_to=JULY_15)
    uow = FakeUnitOfWork(
        nodes=FakeNodeRepository(by_id={node.id: node}),
        claims=FakeClaimRepository((closed,)),
    )

    as_of_result = query_claims_of_node(
        workspace_id=WORKSPACE,
        node_id=node.id,
        at=AT,
        uow=uow,
    )
    history_result = query_claims_of_node_history(
        workspace_id=WORKSPACE,
        node_id=node.id,
        uow=uow,
    )

    assert as_of_result.claims == ()
    assert [claim.claim_id for claim in history_result.claims] == [
        closed.claim_id
    ]


def test_node_read_of_a_missing_node_is_empty() -> None:
    """없는 node id는 claim을 읽지 않고 빈 결과를 준다."""
    uow = FakeUnitOfWork(claims=FakeClaimRepository((_claim(),)))
    missing = uuid.uuid4()

    result = query_claims_of_node(
        workspace_id=WORKSPACE,
        node_id=missing,
        at=AT,
        uow=uow,
    )

    assert result.subject is None
    assert result.claims == ()
    assert uow.knowledge_candidates.calls == []


def test_node_read_of_a_merged_node_is_empty() -> None:
    """접힌 노드의 claim은 근거로 쓰지 않는다.

    merged 노드는 identity가 이미 다른 노드로 넘어간 상태다. 그 노드의
    claim을 되살려 실으면 병합 결정이 답변 경로에서만 무효가 된다.
    """
    survivor = _node()
    merged = KnowledgeNode(
        id=uuid.uuid4(),
        workspace_id=WORKSPACE,
        node_kind=NodeKind.ENTITY,
        entity_type="feature",
        display_name="옛 오픈 API",
        lifecycle_state=NodeLifecycleState.MERGED,
        merged_into_node_id=survivor.id,
    )
    uow = FakeUnitOfWork(
        nodes=FakeNodeRepository(by_id={merged.id: merged}),
        claims=FakeClaimRepository((_claim(),)),
    )

    as_of_result = query_claims_of_node(
        workspace_id=WORKSPACE,
        node_id=merged.id,
        at=AT,
        uow=uow,
    )
    history_result = query_claims_of_node_history(
        workspace_id=WORKSPACE,
        node_id=merged.id,
        uow=uow,
    )

    assert as_of_result.subject is None
    assert as_of_result.claims == ()
    assert history_result.subject is None
    assert history_result.claims == ()
    assert uow.knowledge_candidates.calls == []
    assert uow.knowledge_candidates.history_calls == []
