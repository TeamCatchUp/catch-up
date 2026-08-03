from __future__ import annotations

import uuid
from datetime import datetime
from datetime import timedelta
from datetime import timezone

from structlog.testing import capture_logs

from catchup.knowledge_maintenance.domain.knowledge_node import KnowledgeNode
from catchup.knowledge_maintenance.domain.knowledge_node import NodeKind
from catchup.knowledge_maintenance.ports.knowledge_candidates import AsOfClaim
from catchup.knowledge_maintenance.services.query_knowledge_as_of import (
    query_claims_as_of,
)

WORKSPACE = 1
AT = datetime(2026, 8, 1, 9, 0, tzinfo=timezone.utc)


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


def _claim(predicate: str = "rate_limit", value: object = 60) -> AsOfClaim:
    return AsOfClaim(
        claim_id=uuid.uuid4(),
        predicate=predicate,
        value_type="number",
        value=value,
        statement=f"{predicate}은 {value}이다",
        valid_from=None,
        valid_to=None,
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
    ) -> None:
        self.by_canonical_key = dict(by_canonical_key or {})
        self.by_alias = dict(by_alias or {})
        self.canonical_key_calls: list[str] = []
        self.alias_calls: list[str] = []

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
    ) -> KnowledgeNode | None:
        del workspace_id
        self.alias_calls.append(normalized_alias)
        return self.by_alias.get(normalized_alias)


class FakeClaimRepository:
    def __init__(self, claims: tuple[AsOfClaim, ...] = ()) -> None:
        self.claims = claims
        self.calls: list[dict] = []

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
