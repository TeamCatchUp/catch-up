"""정의 순회로 바뀐 컴파일 입구를 fake와 실 PostgreSQL로 확인한다.

입구가 "claim 많은 상위 N개 노드"에서 "workspace의 정의 목록"으로 바뀌면
확인할 것도 바뀐다. 정의가 고른 종류의 노드마다 문서가 서는지, 정의가
고른 절만 그 차례로 실리는지, 경로가 관계 블록과 근거 장부를 남기는지,
그리고 어휘 개정으로 깨진 정의 하나가 나머지 정의의 컴파일을 막지
않는지다.

내려가는 흐름(반려 억제·지문 비교·멱등 키)은 기존 엔진과 같은 함수를
그대로 쓰므로 여기서 다시 확인하지 않는다. 다만 같은 입력을 두 번 넣으면
아무것도 쓰지 않는다는 결정론만은 실 DB에서 한 번 더 본다 — fake는
정렬과 대조 규칙을 흉내 낼 뿐이라 그것이 실제 질의에서도 성립하는지
말해 주지 못한다.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from collections.abc import Iterator
from collections.abc import Sequence
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from typing import Any

import pytest
from sqlalchemy import Engine
from sqlalchemy import create_engine
from sqlalchemy import inspect
from sqlalchemy import select
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker
from structlog.testing import capture_logs

from catchup.configs.config import settings
from catchup.db.models import ArtifactDefinition
from catchup.db.models import Channel
from catchup.db.models import KnowledgeClaimCandidate as ClaimRow
from catchup.db.models import KnowledgeExtractionRun as RunRow
from catchup.db.models import KnowledgeNode as NodeRow
from catchup.db.models import KnowledgeOntologySnapshot as SnapshotRow
from catchup.db.models import KnowledgeRelationAssertionCandidate
from catchup.db.models import Observation as ObservationRow
from catchup.db.models import SourceVersion as SourceVersionRow
from catchup.db.models import User
from catchup.db.models import Workspace
from catchup.knowledge_maintenance.adapters.postgres.unit_of_work import (
    KnowledgeMaintenanceUnitOfWork,
)
from catchup.knowledge_maintenance.contracts.extraction import EntityTypeEntry
from catchup.knowledge_maintenance.contracts.extraction import ExtractionVocabulary
from catchup.knowledge_maintenance.contracts.extraction import PredicateEntry
from catchup.knowledge_maintenance.contracts.extraction import RelationTypeEntry
from catchup.knowledge_maintenance.domain.artifact import BLOCK_KIND_CLAIM_SECTION
from catchup.knowledge_maintenance.domain.artifact import BLOCK_KIND_RELATION_SECTION
from catchup.knowledge_maintenance.domain.artifact import ArtifactBlock
from catchup.knowledge_maintenance.domain.artifact import BlockSource
from catchup.knowledge_maintenance.domain.artifact import block_content_hash
from catchup.knowledge_maintenance.domain.artifact import validate_blocks
from catchup.knowledge_maintenance.domain.artifact_definition import MAX_NODES_PER_STEP
from catchup.knowledge_maintenance.domain.claim_conflict import StoredClaimCandidate
from catchup.knowledge_maintenance.ports.relations import StoredRelationEdge
from catchup.knowledge_maintenance.services.compile_entity_artifacts import (
    compile_definition_artifacts,
)
from catchup.tests.knowledge_maintenance.test_artifact_definition_repository import (
    FakeArtifactDefinitionRepository,
)
from catchup.tests.knowledge_maintenance.test_artifact_definition_schema import _channel
from catchup.tests.knowledge_maintenance.test_compile_entity_artifacts import (
    FakeArtifactRepository,
)
from catchup.tests.knowledge_maintenance.test_compile_entity_artifacts import (
    FakeBlockVerdictRepository,
)
from catchup.tests.knowledge_maintenance.test_compile_entity_artifacts import (
    FakeClaimRepository,
)
from catchup.tests.knowledge_maintenance.test_compile_entity_artifacts import (
    FakeMutationProposalRepository,
)

NOW = datetime(2026, 8, 12, 9, 0, tzinfo=timezone.utc)
# 실 DB 시험이 심는 원문·관찰의 시각이다. claim의 관찰 시각이 여기서
# 온다.
PG_OBSERVED_AT = NOW
WORKSPACE = 1
DEFINITION_KIND = "feature_request_card"

# 정의 차례를 확인하려면 식별자를 우연에 맡길 수 없다.
FIRST_DEFINITION_ID = uuid.UUID("00000000-0000-4000-8000-000000000001")
SECOND_DEFINITION_ID = uuid.UUID("ffffffff-0000-4000-8000-000000000002")

VOCABULARY = ExtractionVocabulary(
    snapshot_id="7",
    entity_type_entries=(
        EntityTypeEntry(
            name="feature_request",
            definition="사용자가 올린 요청이다.",
            identity_scope="standalone",
        ),
        EntityTypeEntry(
            name="team",
            definition="일을 맡는 조직이다.",
            identity_scope="standalone",
        ),
    ),
    predicate_entries=(
        PredicateEntry(
            name="status", definition="지금 상태다.", value_type="text"
        ),
        PredicateEntry(
            name="summary", definition="요청 요약이다.", value_type="text"
        ),
        PredicateEntry(
            name="priority", definition="처리 우선순위다.", value_type="text"
        ),
    ),
    relation_type_entries=(
        RelationTypeEntry(
            name="owned_by", definition="요청을 맡은 팀을 가리킨다."
        ),
    ),
)


def _spec(
    *,
    entity_types: Sequence[str] = ("feature_request",),
    relation_paths: Sequence[dict[str, Any]] = (),
    predicate_sections: Sequence[str] | None = None,
) -> dict[str, Any]:
    """저장 형태 그대로의 선택 규칙을 만든다."""
    return {
        "entity_filter": {"entity_types": list(entity_types)},
        "relation_paths": list(relation_paths),
        "predicate_sections": (
            None if predicate_sections is None else list(predicate_sections)
        ),
    }


def _definition_row(
    *,
    definition_id: uuid.UUID = FIRST_DEFINITION_ID,
    kind: str = DEFINITION_KIND,
    spec: dict[str, Any] | None = None,
) -> tuple[uuid.UUID, uuid.UUID, str, dict[str, Any]]:
    """정의 저장소 fake가 읽을 행 한 줄을 만든다."""
    return (definition_id, uuid.uuid4(), kind, spec or _spec())


def _claim(
    *,
    node_id: uuid.UUID,
    predicate: str = "status",
    value: object = "검토 중",
    minutes: int = 0,
) -> StoredClaimCandidate:
    """canonical 노드를 subject로 삼는 claim 후보를 하나 만든다."""
    return StoredClaimCandidate(
        id=uuid.uuid4(),
        subject_entity_candidate_id=None,
        subject_node_id=node_id,
        subject_resolved_node_id=None,
        predicate=predicate,
        value_type="text",
        value=value,
        statement=f"{predicate}는 {value}이다",
        observed_at=NOW + timedelta(minutes=minutes),
        valid_from=None,
        valid_to=None,
        citation_verified=None,
    )


class FakeRelationRepository:
    """관계 한 걸음 조회를 메모리에서 흉내 낸다.

    실 조회의 계약을 그대로 따른다 — 관계 종류는 정확히 일치해야 하고,
    방향 규칙을 지키며, 결과는 관계 식별자 사전순이다. 시점은 호출자가
    넘긴 값을 기록만 한다. 컴파일이 걸음마다 같은 시점을 넘기는지
    확인할 자리다.
    """

    def __init__(self, edges: Sequence[tuple[str, StoredRelationEdge]] = ()):
        self.edges = list(edges)
        self.moments: list[datetime] = []

    def find_edges(
        self,
        *,
        node_ids: Sequence[uuid.UUID],
        relation_type: str,
        direction: str,
        now: datetime,
    ) -> list[StoredRelationEdge]:
        """주어진 노드에 걸린 간선을 방향 규칙대로 고른다."""
        self.moments.append(now)
        wanted = set(node_ids)
        found = []
        for stored_type, edge in self.edges:
            if stored_type != relation_type:
                continue
            if direction == "out":
                matched = edge.source_node_id in wanted
            elif direction == "in":
                matched = edge.target_node_id in wanted
            else:
                matched = (
                    edge.source_node_id in wanted
                    or edge.target_node_id in wanted
                )
            if matched:
                found.append(edge)
        return sorted(found, key=lambda edge: str(edge.id))


class FakeDefinitionUnitOfWork:
    """정의 순회 컴파일이 쓰는 저장소를 한 벌로 묶는다.

    문서·claim·계류 안건·블록 결정 fake는 기존 엔진 시험의 것을 그대로
    쓴다. 내려가는 흐름이 같은 함수를 쓰므로 저장소도 같아야 두 입구의
    차이만 드러난다.
    """

    def __init__(
        self,
        *,
        definitions: Sequence[tuple[uuid.UUID, uuid.UUID, str, dict[str, Any]]],
        nodes: Sequence[tuple[uuid.UUID, str, str, str]] = (),
        claims: Sequence[StoredClaimCandidate] = (),
        relations: FakeRelationRepository | None = None,
    ) -> None:
        self.artifacts = FakeArtifactRepository(nodes=list(nodes))
        self.artifact_definitions = FakeArtifactDefinitionRepository(
            list(definitions)
        )
        self.knowledge_candidates = FakeClaimRepository(list(claims))
        self.mutation_proposals = FakeMutationProposalRepository()
        self.block_verdicts = FakeBlockVerdictRepository(self.artifacts.by_id)
        self.relations = relations or FakeRelationRepository()
        self.committed = 0

    def __enter__(self) -> FakeDefinitionUnitOfWork:
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        return None

    def commit(self) -> None:
        self.committed += 1


def _run(uow: FakeDefinitionUnitOfWork):
    """정의 순회 컴파일을 한 번 돌린다."""
    return compile_definition_artifacts(
        uow, workspace_id=WORKSPACE, vocabulary=VOCABULARY
    )


def _pending_by_title(uow: FakeDefinitionUnitOfWork) -> dict[str, dict]:
    """계류 변경안을 문서 제목으로 찾을 수 있게 모은다."""
    return {
        uow.artifacts.titles[row["artifact_id"]]: row
        for row in uow.artifacts.pending_rows()
    }


def test_definition_loop_creates_proposal_per_matching_entity() -> None:
    """정의가 고른 종류의 노드마다 문서 변경안이 하나씩 선다."""
    first = uuid.uuid4()
    second = uuid.uuid4()
    other = uuid.uuid4()
    uow = FakeDefinitionUnitOfWork(
        definitions=[
            _definition_row(
                spec=_spec(
                    relation_paths=[
                        {"steps": [{"type": "owned_by", "dir": "out"}]}
                    ],
                    predicate_sections=["status"],
                )
            )
        ],
        nodes=[
            (first, "요청 A", "feature_request", "active"),
            (second, "요청 B", "feature_request", "active"),
            (other, "결제팀", "team", "active"),
        ],
        claims=[
            _claim(node_id=first),
            _claim(node_id=second),
            _claim(node_id=other),
        ],
    )

    result = _run(uow)

    assert result.definitions_considered == 1
    assert result.nodes_considered == 2
    assert result.proposals_created == 2
    assert uow.committed == 1
    titles = set(_pending_by_title(uow))
    assert titles == {
        f"{DEFINITION_KIND}: 요청 A",
        f"{DEFINITION_KIND}: 요청 B",
    }
    # 정의가 고르지 않은 종류의 노드는 문서를 얻지 못한다.
    assert all("결제팀" not in title for title in titles)


def test_definition_artifacts_carry_definition_and_channel() -> None:
    """문서 행이 자기를 만든 정의와 그 채널을 이어받는다."""
    node_id = uuid.uuid4()
    row = _definition_row()
    uow = FakeDefinitionUnitOfWork(
        definitions=[row],
        nodes=[(node_id, "요청 A", "feature_request", "active")],
        claims=[_claim(node_id=node_id)],
    )

    _run(uow)

    definition_id, channel_id, kind, _ = row
    artifact_id = uow.artifacts.definition_artifacts[(definition_id, node_id)]
    stored = uow.artifacts.artifact_rows[artifact_id]
    assert stored["definition_id"] == definition_id
    assert stored["channel_id"] == channel_id
    assert stored["kind"] == kind
    assert stored["subject_node_id"] == node_id
    assert _pending_by_title(uow)[stored["title"]]["artifact_id"] == (
        artifact_id
    )


def test_predicate_sections_orders_and_filters() -> None:
    """정의가 고른 절만 그 차례대로 실린다."""
    node_id = uuid.uuid4()
    uow = FakeDefinitionUnitOfWork(
        definitions=[
            _definition_row(
                spec=_spec(predicate_sections=["summary", "status"])
            )
        ],
        nodes=[(node_id, "요청 A", "feature_request", "active")],
        claims=[
            _claim(node_id=node_id, predicate="status", value="검토 중"),
            _claim(node_id=node_id, predicate="summary", value="결제 개선"),
            _claim(node_id=node_id, predicate="priority", value="높음"),
        ],
    )

    _run(uow)

    row = _pending_by_title(uow)[f"{DEFINITION_KIND}: 요청 A"]
    headings = [block.heading for block in row["blocks"]]
    # 어휘 차례는 status·summary·priority지만 정의의 차례가 이긴다.
    assert headings == ["summary", "status"]


def test_no_predicate_sections_keeps_dictionary_order() -> None:
    """절을 고르지 않은 정의는 어휘 차례로 전부 싣는다."""
    node_id = uuid.uuid4()
    uow = FakeDefinitionUnitOfWork(
        definitions=[_definition_row(spec=_spec(predicate_sections=None))],
        nodes=[(node_id, "요청 A", "feature_request", "active")],
        claims=[
            _claim(node_id=node_id, predicate="priority", value="높음"),
            _claim(node_id=node_id, predicate="status", value="검토 중"),
        ],
    )

    _run(uow)

    row = _pending_by_title(uow)[f"{DEFINITION_KIND}: 요청 A"]
    assert [block.heading for block in row["blocks"]] == [
        "status",
        "priority",
    ]


def test_empty_predicate_sections_drops_claim_sections() -> None:
    """절을 하나도 고르지 않은 정의는 claim 절을 싣지 않는다.

    고르지 않음(None)과 하나도 고르지 않음(빈 목록)은 선택 규칙이 뜻을
    갈라 둔 두 가지다. 빈 목록을 "전부"로 읽으면 사람이 절을 비운 정의가
    도리어 모든 절을 싣는다.
    """
    node_id = uuid.uuid4()
    target = uuid.uuid4()
    relation_id = uuid.uuid4()
    uow = FakeDefinitionUnitOfWork(
        definitions=[
            _definition_row(
                spec=_spec(
                    relation_paths=[
                        {"steps": [{"type": "owned_by", "dir": "out"}]}
                    ],
                    predicate_sections=[],
                )
            )
        ],
        nodes=[(node_id, "요청 A", "feature_request", "active")],
        claims=[_claim(node_id=node_id, predicate="status")],
        relations=FakeRelationRepository(
            [
                (
                    "owned_by",
                    StoredRelationEdge(
                        id=relation_id,
                        source_node_id=node_id,
                        target_node_id=target,
                        assertion_text="요청 A는 결제팀이 맡는다",
                        source_display_name="요청 A",
                        target_display_name="결제팀",
                    ),
                )
            ]
        ),
    )

    _run(uow)

    row = _pending_by_title(uow)[f"{DEFINITION_KIND}: 요청 A"]
    assert [block.block_kind for block in row["blocks"]] == [
        BLOCK_KIND_RELATION_SECTION
    ]


TRUNCATED_PATH_SPEC = _spec(
    relation_paths=[
        {
            "steps": [
                {"type": "owned_by", "dir": "out"},
                {"type": "owned_by", "dir": "out"},
            ]
        }
    ],
    predicate_sections=["status"],
)


def _dead_end_after_truncation(
    node_id: uuid.UUID,
) -> FakeRelationRepository:
    """첫 걸음이 상한을 넘겨 잘리고 다음 걸음이 끊기는 그래프를 만든다.

    이웃이 상한보다 하나 많으므로 첫 걸음은 잘린다. 그 이웃에서 나가는
    간선은 하나도 없으므로 둘째 걸음에서 frontier가 비고, 완주한 가지가
    없어 근거 장부도 빈다.
    """
    return FakeRelationRepository(
        [
            (
                "owned_by",
                StoredRelationEdge(
                    id=uuid.UUID(f"ffffffff-0000-4000-8000-{number:012d}"),
                    source_node_id=node_id,
                    target_node_id=uuid.UUID(
                        f"00000000-0000-4000-8000-{number:012d}"
                    ),
                    assertion_text=f"이웃 {number}",
                    source_display_name="요청 A",
                    target_display_name=f"팀{number:03d}",
                ),
            )
            for number in range(1, MAX_NODES_PER_STEP + 2)
        ]
    )


def _two_hop_completing(node_id: uuid.UUID) -> FakeRelationRepository:
    """두 걸음을 끝까지 완주하는 그래프를 만든다.

    잘림도 끊김도 없으므로 관계 절이 그대로 선다.
    """
    middle = uuid.UUID("00000000-0000-4000-8000-000000009001")
    last = uuid.UUID("00000000-0000-4000-8000-000000009002")
    return FakeRelationRepository(
        [
            (
                "owned_by",
                StoredRelationEdge(
                    id=uuid.UUID("ffffffff-0000-4000-8000-000000009001"),
                    source_node_id=node_id,
                    target_node_id=middle,
                    assertion_text="요청 A는 결제팀이 맡는다",
                    source_display_name="요청 A",
                    target_display_name="결제팀",
                ),
            ),
            (
                "owned_by",
                StoredRelationEdge(
                    id=uuid.UUID("ffffffff-0000-4000-8000-000000009002"),
                    source_node_id=middle,
                    target_node_id=last,
                    assertion_text="결제팀은 플랫폼실 소속이다",
                    source_display_name="결제팀",
                    target_display_name="플랫폼실",
                ),
            ),
        ]
    )


def test_truncated_path_without_ledger_fails_the_document() -> None:
    """잘렸는데 완주가 없으면 그 문서의 컴파일이 실패한다.

    완주한 간선만 근거 장부에 남으므로, 잘림만 있고 끝까지 간 가지가
    없는 경로는 근거가 비어 관계 절을 세울 수 없다. 그 절만 빼고 문서를
    올리면 읽는 사람은 잘려 나간 것이 있다는 사실을 알 길이 없다.
    불완전할 수 있는 문서는 소비 표면에 올리지 않는다.
    """
    node_id = uuid.uuid4()
    uow = FakeDefinitionUnitOfWork(
        definitions=[_definition_row(spec=TRUNCATED_PATH_SPEC)],
        nodes=[(node_id, "요청 A", "feature_request", "active")],
        claims=[_claim(node_id=node_id)],
        relations=_dead_end_after_truncation(node_id),
    )

    with capture_logs() as logs:
        result = _run(uow)

    assert _pending_by_title(uow) == {}
    assert result.proposals_created == 0
    assert result.nodes_failed == 1

    entries = [
        entry
        for entry in logs
        if entry["event"] == "artifact_compile_node_failed_truncated_path"
    ]
    assert len(entries) == 1
    assert entries[0]["log_level"] == "warning"
    assert entries[0]["workspace_id"] == WORKSPACE
    assert entries[0]["definition_id"] == str(FIRST_DEFINITION_ID)
    assert entries[0]["node_id"] == str(node_id)
    assert entries[0]["path_index"] == 0
    assert entries[0]["truncated_steps"] == [0]


def test_truncated_path_failure_does_not_stop_other_nodes() -> None:
    """한 문서가 잘림으로 실패해도 다른 문서는 그대로 만들어진다.

    격리가 없으면 허브 노드 하나가 그 정의의 카드 전부를 멈춘다.
    """
    failing = uuid.uuid4()
    healthy = uuid.uuid4()
    uow = FakeDefinitionUnitOfWork(
        definitions=[_definition_row(spec=TRUNCATED_PATH_SPEC)],
        nodes=[
            (failing, "요청 A", "feature_request", "active"),
            (healthy, "요청 B", "feature_request", "active"),
        ],
        claims=[_claim(node_id=failing), _claim(node_id=healthy)],
        relations=_dead_end_after_truncation(failing),
    )

    result = _run(uow)

    titles = _pending_by_title(uow)
    assert f"{DEFINITION_KIND}: 요청 A" not in titles
    assert f"{DEFINITION_KIND}: 요청 B" in titles
    assert result.nodes_considered == 2
    assert result.nodes_failed == 1
    assert result.proposals_created == 1


def test_truncation_failure_abandons_earlier_pending_proposal() -> None:
    """잘림으로 접힌 문서는 앞서 올려 둔 계류 변경안까지 거둔다.

    계류 변경안은 검토 큐에 그대로 보이고, 자동 승인이 도는 자리에서는
    판으로 확정된다. 방금 불완전하다고 판정한 내용이 그 길로 발행되면
    fail-closed는 이름뿐이다.
    """
    node_id = uuid.uuid4()
    uow = FakeDefinitionUnitOfWork(
        definitions=[_definition_row(spec=TRUNCATED_PATH_SPEC)],
        nodes=[(node_id, "요청 A", "feature_request", "active")],
        claims=[_claim(node_id=node_id)],
        relations=_two_hop_completing(node_id),
    )

    first = _run(uow)

    assert first.proposals_created == 1
    assert len(uow.artifacts.pending_rows()) == 1
    artifact_id = uow.artifacts.pending_rows()[0]["artifact_id"]

    # 지식이 바뀌어 경로가 잘리고 완주가 사라진다.
    uow.relations = _dead_end_after_truncation(node_id)
    second = _run(uow)

    assert second.nodes_failed == 1
    assert second.proposals_created == 0
    assert second.proposals_abandoned == 1
    assert [
        row
        for row in uow.artifacts.pending_rows()
        if row["artifact_id"] == artifact_id
    ] == []
    # 자동 승인이 보는 자리에서도 비어 있어야 한다.
    assert uow.artifacts.list_pending_proposals() == []


def test_first_ever_truncation_failure_creates_no_artifact() -> None:
    """한 번도 선 적 없는 문서는 실패로도 행을 만들지 않는다.

    빈 문서 행은 검토자에게 제목만 있고 내용이 없는 카드로 보인다.
    """
    node_id = uuid.uuid4()
    uow = FakeDefinitionUnitOfWork(
        definitions=[_definition_row(spec=TRUNCATED_PATH_SPEC)],
        nodes=[(node_id, "요청 A", "feature_request", "active")],
        claims=[_claim(node_id=node_id)],
        relations=_dead_end_after_truncation(node_id),
    )

    result = _run(uow)

    assert result.nodes_failed == 1
    assert result.proposals_abandoned == 0
    assert uow.artifacts.artifact_rows == {}


def test_dead_path_without_truncation_stays_silent() -> None:
    """잘림 없이 이을 것만 없는 경로는 문서를 세우지도 실패시키지도 않는다.

    잘라 낸 것이 없으면 감춘 것도 없다. 관계 절만 빠지고 나머지는
    그대로 실린다.
    """
    node_id = uuid.uuid4()
    uow = FakeDefinitionUnitOfWork(
        definitions=[_definition_row(spec=TRUNCATED_PATH_SPEC)],
        nodes=[(node_id, "요청 A", "feature_request", "active")],
        claims=[_claim(node_id=node_id)],
        relations=FakeRelationRepository([]),
    )

    result = _run(uow)

    blocks = _pending_by_title(uow)[f"{DEFINITION_KIND}: 요청 A"]["blocks"]
    assert [block.block_kind for block in blocks] == [BLOCK_KIND_CLAIM_SECTION]
    assert result.nodes_failed == 0


def test_relation_blocks_included_with_ledger() -> None:
    """경로를 고른 정의는 관계 블록과 근거 장부를 남긴다."""
    node_id = uuid.uuid4()
    target = uuid.uuid4()
    relation_id = uuid.uuid4()
    uow = FakeDefinitionUnitOfWork(
        definitions=[
            _definition_row(
                spec=_spec(
                    relation_paths=[
                        {"steps": [{"type": "owned_by", "dir": "out"}]}
                    ],
                    predicate_sections=["status"],
                )
            )
        ],
        nodes=[(node_id, "요청 A", "feature_request", "active")],
        claims=[_claim(node_id=node_id)],
        relations=FakeRelationRepository(
            [
                (
                    "owned_by",
                    StoredRelationEdge(
                        id=relation_id,
                        source_node_id=node_id,
                        target_node_id=target,
                        assertion_text="요청 A는 결제팀이 맡는다",
                        source_display_name="요청 A",
                        target_display_name="결제팀",
                    ),
                )
            ]
        ),
    )

    _run(uow)

    blocks = _pending_by_title(uow)[f"{DEFINITION_KIND}: 요청 A"]["blocks"]
    assert [block.block_kind for block in blocks] == [
        BLOCK_KIND_CLAIM_SECTION,
        BLOCK_KIND_RELATION_SECTION,
    ]
    relation_block = blocks[1]
    assert relation_block.heading == "owned_by(out)"
    assert relation_block.body == "요청 A는 결제팀이 맡는다"
    assert relation_block.relation_ids == (relation_id,)
    validate_blocks(blocks)
    # 순회는 컴파일 시점 하나만 쓴다. 걸음마다 시계를 새로 읽으면 같은
    # 실행 안에서도 살아 있는 관계의 기준이 흔들린다.
    assert len(set(uow.relations.moments)) == 1


def test_relation_path_without_edges_leaves_no_block() -> None:
    """이어지는 관계가 없으면 빈 관계 블록을 만들지 않는다."""
    node_id = uuid.uuid4()
    uow = FakeDefinitionUnitOfWork(
        definitions=[
            _definition_row(
                spec=_spec(
                    relation_paths=[
                        {"steps": [{"type": "owned_by", "dir": "out"}]}
                    ]
                )
            )
        ],
        nodes=[(node_id, "요청 A", "feature_request", "active")],
        claims=[_claim(node_id=node_id)],
    )

    _run(uow)

    blocks = _pending_by_title(uow)[f"{DEFINITION_KIND}: 요청 A"]["blocks"]
    assert [block.block_kind for block in blocks] == [BLOCK_KIND_CLAIM_SECTION]


def test_invalid_definition_skipped_not_fatal() -> None:
    """어휘에 없는 이름을 쓴 정의만 건너뛰고 나머지는 그대로 돈다."""
    node_id = uuid.uuid4()
    uow = FakeDefinitionUnitOfWork(
        definitions=[
            _definition_row(
                definition_id=FIRST_DEFINITION_ID,
                spec=_spec(entity_types=["ghost_type"]),
            ),
            _definition_row(
                definition_id=SECOND_DEFINITION_ID,
                spec=_spec(predicate_sections=["status"]),
            ),
        ],
        nodes=[(node_id, "요청 A", "feature_request", "active")],
        claims=[_claim(node_id=node_id)],
    )

    result = _run(uow)

    assert result.definitions_considered == 2
    assert result.proposals_created == 1
    assert result.nodes_considered == 1
    assert uow.committed == 1


def test_two_definitions_share_a_node_without_colliding() -> None:
    """두 정의가 같은 노드를 고르면 문서도 정의마다 따로 선다."""
    node_id = uuid.uuid4()
    first = _definition_row(
        definition_id=FIRST_DEFINITION_ID,
        kind="feature_request_card",
        spec=_spec(predicate_sections=["status"]),
    )
    second = _definition_row(
        definition_id=SECOND_DEFINITION_ID,
        kind="feature_request_brief",
        spec=_spec(predicate_sections=["status"]),
    )
    uow = FakeDefinitionUnitOfWork(
        definitions=[first, second],
        nodes=[(node_id, "요청 A", "feature_request", "active")],
        claims=[_claim(node_id=node_id)],
    )

    result = _run(uow)

    assert result.definitions_considered == 2
    assert result.proposals_created == 2
    assert uow.artifacts.definition_artifacts[
        (FIRST_DEFINITION_ID, node_id)
    ] != uow.artifacts.definition_artifacts[(SECOND_DEFINITION_ID, node_id)]


def test_node_without_content_is_counted_but_not_written() -> None:
    """쓸 내용이 없는 노드는 세기만 하고 빈 문서를 만들지 않는다."""
    node_id = uuid.uuid4()
    uow = FakeDefinitionUnitOfWork(
        definitions=[_definition_row()],
        nodes=[(node_id, "요청 A", "feature_request", "active")],
        claims=[],
    )

    result = _run(uow)

    assert result.nodes_considered == 1
    assert result.proposals_created == 0
    assert uow.artifacts.by_key == {}


def test_recompiling_same_input_does_nothing() -> None:
    """같은 입력을 다시 컴파일하면 아무것도 쓰지 않는다."""
    node_id = uuid.uuid4()
    uow = FakeDefinitionUnitOfWork(
        definitions=[_definition_row(spec=_spec(predicate_sections=["status"]))],
        nodes=[(node_id, "요청 A", "feature_request", "active")],
        claims=[_claim(node_id=node_id)],
    )
    first = _run(uow)

    second = _run(uow)

    assert first.proposals_created == 1
    assert second.proposals_created == 0
    assert second.unchanged_skipped == 1


@pytest.fixture(scope="module")
def engine() -> Iterator[Engine]:
    engine = create_engine(settings.sqlalchemy_database_url)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except OperationalError:
        engine.dispose()
        pytest.skip("PostgreSQL이 없어 통합 테스트를 건너뛴다.")

    if not inspect(engine).has_table(ArtifactDefinition.__tablename__):
        engine.dispose()
        pytest.skip("정의 테이블이 없다. alembic upgrade head가 필요하다.")

    yield engine
    engine.dispose()


@pytest.fixture(scope="module")
def seed_workspace_id(engine: Engine) -> int:
    with engine.connect() as connection:
        found = connection.execute(
            select(Workspace.id).order_by(Workspace.id).limit(1)
        ).scalar()

    if found is None:
        pytest.skip("workspace가 없어 통합 테스트를 건너뛴다.")
    return found


@pytest.fixture(scope="module")
def user_id(engine: Engine) -> int:
    with engine.connect() as connection:
        found = connection.execute(
            select(User.id).order_by(User.id).limit(1)
        ).scalar()

    if found is None:
        pytest.skip("user가 없어 통합 테스트를 건너뛴다.")
    return found


@pytest.fixture
def session_factory(engine: Engine) -> Iterator[Callable[[], Session]]:
    connection = engine.connect()
    transaction = connection.begin()

    yield sessionmaker(
        bind=connection,
        join_transaction_mode="create_savepoint",
        expire_on_commit=False,
    )

    transaction.rollback()
    connection.close()


@pytest.fixture
def workspace_id(
    session_factory: Callable[[], Session],
    seed_workspace_id: int,
) -> int:
    """이 시험만 쓰는 빈 workspace를 마련한다.

    기존 workspace에는 다른 시험이나 실제 운영이 남긴 정의와 노드가 있어
    "몇 건이 나오는가"를 셀 수 없다.
    """
    with session_factory() as session:
        company_id = session.execute(
            select(Workspace.company_id).where(
                Workspace.id == seed_workspace_id
            )
        ).scalar_one()
        workspace = Workspace(
            name=f"ws-{uuid.uuid4().hex[:8]}", company_id=company_id
        )
        session.add(workspace)
        session.commit()
        return workspace.id


@pytest.fixture
def uow_factory(
    session_factory: Callable[[], Session],
    workspace_id: int,
) -> Callable[[], KnowledgeMaintenanceUnitOfWork]:
    return lambda: KnowledgeMaintenanceUnitOfWork(
        session_factory, workspace_id=workspace_id
    )


def _pg_extraction_run(session: Session, workspace_id: int) -> uuid.UUID:
    """claim을 매달 추출 실행을 하나 만든다.

    원문·관찰까지 함께 심는다. claim 조회가 관찰 시각을 원문 사슬에서
    얻으므로, 그 사슬이 끊긴 claim은 조회에 아예 나오지 않는다.
    """
    ontology_version = uuid.uuid4().hex[:8]
    session.add(
        SnapshotRow(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            ontology_id="test",
            version=ontology_version,
            predicates=[],
            relation_types=[],
        )
    )
    session.flush()
    source_version_id = uuid.uuid4()
    session.add(
        SourceVersionRow(
            id=source_version_id,
            workspace_id=workspace_id,
            source_type="channel_talk",
            entity_type="user_chat",
            scope_id="ch-test",
            target_id="ch-test",
            external_document_id=f"doc-{uuid.uuid4().hex[:8]}",
            change_kind="created",
            source_version_key="1",
            content="본문",
            content_type="text/plain",
            content_hash="a" * 64,
            source_updated_at=PG_OBSERVED_AT,
            observed_at=PG_OBSERVED_AT,
            idempotency_key=f"test:{uuid.uuid4().hex}",
            payload_hash="b" * 64,
        )
    )
    session.flush()
    observation_id = uuid.uuid4()
    session.add(
        ObservationRow(
            id=observation_id,
            workspace_id=workspace_id,
            source_version_id=source_version_id,
            observation_kind="document",
            normalized_content="본문",
            normalized_content_hash="c" * 64,
            normalizer_id="test",
            normalizer_version="1",
            occurred_at=PG_OBSERVED_AT,
        )
    )
    session.flush()
    input_node = NodeRow(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        node_kind="observation",
        resource_type="observation",
        resource_id=str(observation_id),
    )
    session.add(input_node)
    session.flush()
    run = RunRow(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        input_node_id=input_node.id,
        provider="test",
        model="test",
        extractor_version="1",
        prompt_version="1",
        ontology_id="test",
        ontology_version=ontology_version,
        status="succeeded",
        started_at=datetime.now(timezone.utc),
    )
    session.add(run)
    session.flush()
    return run.id


def _pg_node(
    session: Session, workspace_id: int, name: str, entity_type: str
) -> uuid.UUID:
    """살아 있는 canonical entity 노드를 하나 만든다."""
    node = NodeRow(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        node_kind="entity",
        entity_type=entity_type,
        canonical_key=f"test:{entity_type}:{uuid.uuid4().hex}",
        display_name=name,
        lifecycle_state="active",
    )
    session.add(node)
    session.flush()
    return node.id


def _pg_claim(
    session: Session,
    workspace_id: int,
    run_id: uuid.UUID,
    node_id: uuid.UUID,
    predicate: str,
    value: str,
) -> uuid.UUID:
    """어떤 노드에 붙는 계류 claim 후보를 하나 만든다."""
    row = ClaimRow(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        extraction_run_id=run_id,
        local_key=f"c-{uuid.uuid4().hex}",
        subject_node_id=node_id,
        predicate=predicate,
        value_type="string",
        value=value,
        value_hash=uuid.uuid4().hex * 2,
        statement=f"{predicate}는 {value}입니다.",
        ontology_id="test",
        ontology_version="1",
        extraction_method="llm",
    )
    session.add(row)
    session.flush()
    return row.id


def _pg_relation(
    session: Session,
    workspace_id: int,
    run_id: uuid.UUID,
    *,
    relation_id: uuid.UUID,
    source_node_id: uuid.UUID,
    target_node_id: uuid.UUID,
    relation_type: str = "owned_by",
) -> uuid.UUID:
    """두 canonical 노드를 잇는 살아 있는 관계 후보를 하나 만든다."""
    session.add(
        KnowledgeRelationAssertionCandidate(
            id=relation_id,
            workspace_id=workspace_id,
            extraction_run_id=run_id,
            local_key=f"rel-{relation_id}",
            source_node_id=source_node_id,
            target_node_id=target_node_id,
            relation_type=relation_type,
            assertion_text="요청 A는 결제팀이 맡는다",
            extraction_method="llm",
            resolution_status="accepted",
        )
    )
    session.flush()
    return relation_id


def test_same_input_twice_all_skipped(
    workspace_id: int,
    user_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """실 DB에서도 같은 입력을 두 번 컴파일하면 두 번째는 전부 넘긴다.

    fake는 정렬과 대조 규칙을 흉내 낼 뿐이다. 정의·노드·claim 조회가
    실제로 같은 차례를 내는지, 그래서 지문이 흔들리지 않는지는 실 DB에서
    확인해야 한다.

    정의에 관계 경로를 함께 실어 관계 블록까지 결정론에 넣는다. 관계
    조회는 claim 조회와 다른 질의라, claim만으로는 관계 쪽 차례가
    흔들려도 드러나지 않는다.
    """
    channel_id = _channel(session_factory, workspace_id, user_id)
    relation_id = uuid.uuid4()
    with session_factory() as session:
        session.add(
            ArtifactDefinition(
                id=FIRST_DEFINITION_ID,
                workspace_id=workspace_id,
                channel_id=channel_id,
                kind=DEFINITION_KIND,
                selection_spec=_spec(
                    relation_paths=[
                        {"steps": [{"type": "owned_by", "dir": "out"}]}
                    ],
                    predicate_sections=["status"],
                ),
                created_by=user_id,
            )
        )
        run_id = _pg_extraction_run(session, workspace_id)
        node_ids: dict[str, uuid.UUID] = {}
        for name in ("요청 A", "요청 B"):
            node_id = _pg_node(session, workspace_id, name, "feature_request")
            node_ids[name] = node_id
            _pg_claim(
                session, workspace_id, run_id, node_id, "status", "검토 중"
            )
        team_id = _pg_node(session, workspace_id, "결제팀", "team")
        _pg_relation(
            session,
            workspace_id,
            run_id,
            relation_id=relation_id,
            source_node_id=node_ids["요청 A"],
            target_node_id=team_id,
        )
        session.commit()

    first = compile_definition_artifacts(
        uow_factory(), workspace_id=workspace_id, vocabulary=VOCABULARY
    )
    second = compile_definition_artifacts(
        uow_factory(), workspace_id=workspace_id, vocabulary=VOCABULARY
    )

    assert first.definitions_considered == 1
    assert first.proposals_created == 2
    assert second.proposals_created == 0
    assert second.unchanged_skipped == first.proposals_created

    with session_factory() as session:
        stored = session.execute(
            text(
                "SELECT definition_id, channel_id, kind, title"
                " FROM knowledge_artifacts WHERE workspace_id = :workspace"
                " ORDER BY title"
            ),
            {"workspace": workspace_id},
        ).all()
    assert [row.title for row in stored] == [
        f"{DEFINITION_KIND}: 요청 A",
        f"{DEFINITION_KIND}: 요청 B",
    ]
    for row in stored:
        assert row.definition_id == FIRST_DEFINITION_ID
        assert row.channel_id == channel_id
        assert row.kind == DEFINITION_KIND

    with session_factory() as session:
        blocks = session.execute(
            text(
                "SELECT p.blocks FROM knowledge_artifact_change_proposals p"
                " JOIN knowledge_artifacts a ON a.id = p.artifact_id"
                " WHERE p.workspace_id = :workspace AND a.title = :title"
            ),
            {"workspace": workspace_id, "title": f"{DEFINITION_KIND}: 요청 A"},
        ).scalar_one()
    relation_blocks = [
        block
        for block in blocks
        if block["block_kind"] == BLOCK_KIND_RELATION_SECTION
    ]
    assert len(relation_blocks) == 1
    assert relation_blocks[0]["relation_ids"] == [str(relation_id)]


def test_truncation_failure_abandons_pending_in_postgres(
    workspace_id: int,
    user_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """실 DB에서도 잘림 실패가 앞선 계류 변경안을 거둔다.

    fake는 접기 호출이 불렸는지만 보여 준다. 그 호출이 실제로 행 상태를
    바꾸는지, 그래서 검토 큐 조회에서 빠지는지는 실 DB에서 확인해야
    한다.

    두 걸음 경로를 쓴다. 첫 실행은 이웃이 하나뿐이라 잘리지 않고, 둘째
    걸음이 비어 관계 절 없이 claim 절만으로 문서가 선다. 그다음 막다른
    이웃을 상한 너머로 더해 첫 걸음이 잘리게 만들면, 완주한 가지가
    없는 채로 잘림만 남는다 — 관계를 지우거나 다시 심지 않고 행을
    더하기만 해서 그 상태에 닿는 가장 싼 길이다.
    """
    channel_id = _channel(session_factory, workspace_id, user_id)
    with session_factory() as session:
        session.add(
            ArtifactDefinition(
                id=FIRST_DEFINITION_ID,
                workspace_id=workspace_id,
                channel_id=channel_id,
                kind=DEFINITION_KIND,
                selection_spec=_spec(
                    relation_paths=[
                        {
                            "steps": [
                                {"type": "owned_by", "dir": "out"},
                                {"type": "owned_by", "dir": "out"},
                            ]
                        }
                    ],
                    predicate_sections=["status"],
                ),
                created_by=user_id,
            )
        )
        run_id = _pg_extraction_run(session, workspace_id)
        subject_id = _pg_node(session, workspace_id, "요청 A", "feature_request")
        _pg_claim(session, workspace_id, run_id, subject_id, "status", "검토 중")
        team_id = _pg_node(session, workspace_id, "결제팀", "team")
        _pg_relation(
            session,
            workspace_id,
            run_id,
            relation_id=uuid.uuid4(),
            source_node_id=subject_id,
            target_node_id=team_id,
        )
        session.commit()

    first = compile_definition_artifacts(
        uow_factory(), workspace_id=workspace_id, vocabulary=VOCABULARY
    )

    assert first.proposals_created == 1
    with uow_factory() as uow:
        assert len(uow.artifacts.list_pending_proposals()) == 1

    # 막다른 이웃을 상한 너머로 더해 첫 걸음을 자른다.
    with session_factory() as session:
        for _ in range(MAX_NODES_PER_STEP):
            _pg_relation(
                session,
                workspace_id,
                run_id,
                relation_id=uuid.uuid4(),
                source_node_id=subject_id,
                target_node_id=_pg_node(
                    session, workspace_id, f"팀-{uuid.uuid4().hex[:6]}", "team"
                ),
            )
        session.commit()

    second = compile_definition_artifacts(
        uow_factory(), workspace_id=workspace_id, vocabulary=VOCABULARY
    )

    assert second.nodes_failed == 1
    assert second.proposals_created == 0
    assert second.proposals_abandoned == 1
    with uow_factory() as uow:
        assert uow.artifacts.list_pending_proposals() == []
    with session_factory() as session:
        statuses = session.execute(
            text(
                "SELECT status FROM knowledge_artifact_change_proposals"
                " WHERE workspace_id = :workspace"
            ),
            {"workspace": workspace_id},
        ).scalars().all()
    assert statuses == ["abandoned"]


def _narrated_block(
    node_id: uuid.UUID, narrative: str, heading: str
) -> ArtifactBlock:
    """산문이 붙은 claim 절 블록 하나를 만든다."""
    claim_id = uuid.uuid4()
    return ArtifactBlock(
        block_kind=BLOCK_KIND_CLAIM_SECTION,
        heading=heading,
        body=f"{heading} 값이다",
        claim_ids=(claim_id,),
        proposal_ids=(),
        ontology_version="7",
        sources=(
            BlockSource(
                claim_id=claim_id,
                statement=f"{heading}는 값이다",
                observed_at=PG_OBSERVED_AT,
                citation_verified=True,
            ),
        ),
        narrative=narrative,
    )


def test_pg_find_channel_style_reads_the_stored_preset(
    session_factory: Callable[[], Session],
    workspace_id: int,
    user_id: int,
    uow_factory,
) -> None:
    """채널에 저장된 문체 id를 정의 저장소가 그대로 읽는다."""
    session = session_factory()
    channel_id = uuid.uuid4()
    session.add(
        Channel(
            id=channel_id,
            workspace_id=workspace_id,
            name=f"문체-{uuid.uuid4().hex[:8]}",
            style_preset="style.report_summary",
            created_by=user_id,
        )
    )
    session.commit()
    session.close()

    with uow_factory() as uow:
        found = uow.artifact_definitions.find_channel_style(
            channel_id=channel_id
        )

    assert found == "style.report_summary"


def test_pg_find_channel_style_is_none_without_a_preset(
    session_factory: Callable[[], Session],
    workspace_id: int,
    user_id: int,
    uow_factory,
) -> None:
    """문체를 고르지 않은 채널은 없음으로 답한다."""
    session = session_factory()
    channel_id = uuid.uuid4()
    session.add(
        Channel(
            id=channel_id,
            workspace_id=workspace_id,
            name=f"무문체-{uuid.uuid4().hex[:8]}",
            created_by=user_id,
        )
    )
    session.commit()
    session.close()

    with uow_factory() as uow:
        found = uow.artifact_definitions.find_channel_style(
            channel_id=channel_id
        )

    assert found is None


def test_pg_find_channel_style_ignores_other_workspaces(
    session_factory: Callable[[], Session],
    seed_workspace_id: int,
    workspace_id: int,
    user_id: int,
    uow_factory,
) -> None:
    """다른 workspace의 채널 문체는 읽지 않는다."""
    session = session_factory()
    channel_id = uuid.uuid4()
    session.add(
        Channel(
            id=channel_id,
            workspace_id=seed_workspace_id,
            name=f"남의채널-{uuid.uuid4().hex[:8]}",
            style_preset="style.faq",
            created_by=user_id,
        )
    )
    session.commit()
    session.close()

    with uow_factory() as uow:
        found = uow.artifact_definitions.find_channel_style(
            channel_id=channel_id
        )

    assert found is None


def test_pg_reusable_narratives_come_from_revision_and_pending(
    session_factory: Callable[[], Session],
    workspace_id: int,
    user_id: int,
    uow_factory,
) -> None:
    """최신 판과 계류 변경안의 산문만 재사용 사전에 실린다."""
    channel_id = _channel(session_factory, workspace_id, user_id)
    session = session_factory()
    session.add(
        ArtifactDefinition(
            id=FIRST_DEFINITION_ID,
            workspace_id=workspace_id,
            channel_id=channel_id,
            kind=DEFINITION_KIND,
            selection_spec=_spec(),
            created_by=user_id,
        )
    )
    node_id = _pg_node(session, workspace_id, "요청 A", "feature_request")
    session.commit()
    session.close()

    with uow_factory() as uow:
        artifact_id = uow.artifacts.get_or_create_definition_artifact(
            definition_id=FIRST_DEFINITION_ID,
            channel_id=channel_id,
            kind=DEFINITION_KIND,
            subject_node_id=node_id,
            title="요청 A",
        )
        published = _narrated_block(node_id, "발행된 산문이다.", "status")
        proposal_id = uow.artifacts.add_or_revive_proposal(
            artifact_id=artifact_id,
            blocks=[published],
            content_hash="hash-published",
            idempotency_key=f"key-published-{uuid.uuid4()}",
            base_revision_id=None,
        )
        uow.artifacts.mark_approved(
            proposal_id=proposal_id, reviewer="test"
        )
        uow.artifacts.add_revision(
            artifact_id=artifact_id,
            revision_number=1,
            blocks=[published],
            source_proposal_id=proposal_id,
        )
        pending = _narrated_block(node_id, "계류 산문이다.", "priority")
        uow.artifacts.add_or_revive_proposal(
            artifact_id=artifact_id,
            blocks=[pending],
            content_hash="hash-pending",
            idempotency_key=f"key-pending-{uuid.uuid4()}",
            base_revision_id=None,
        )
        uow.commit()

    with uow_factory() as uow:
        found = uow.artifacts.list_reusable_narratives(
            artifact_id=artifact_id
        )

    assert found[block_content_hash(published)] == "발행된 산문이다."
    assert found[block_content_hash(pending)] == "계류 산문이다."


def test_pg_reusable_narratives_skip_rejected_proposals(
    session_factory: Callable[[], Session],
    workspace_id: int,
    user_id: int,
    uow_factory,
) -> None:
    """반려된 변경안의 산문은 재사용 대상이 아니다."""
    channel_id = _channel(session_factory, workspace_id, user_id)
    session = session_factory()
    session.add(
        ArtifactDefinition(
            id=FIRST_DEFINITION_ID,
            workspace_id=workspace_id,
            channel_id=channel_id,
            kind=DEFINITION_KIND,
            selection_spec=_spec(),
            created_by=user_id,
        )
    )
    node_id = _pg_node(session, workspace_id, "요청 B", "feature_request")
    session.commit()
    session.close()

    with uow_factory() as uow:
        artifact_id = uow.artifacts.get_or_create_definition_artifact(
            definition_id=FIRST_DEFINITION_ID,
            channel_id=channel_id,
            kind=DEFINITION_KIND,
            subject_node_id=node_id,
            title="요청 B",
        )
        block = _narrated_block(node_id, "반려된 산문이다.", "status")
        proposal_id = uow.artifacts.add_or_revive_proposal(
            artifact_id=artifact_id,
            blocks=[block],
            content_hash="hash-rejected",
            idempotency_key=f"key-rejected-{uuid.uuid4()}",
            base_revision_id=None,
        )
        uow.artifacts.mark_rejected(
            proposal_id=proposal_id, reviewer="test", reason="문장이 틀렸다"
        )
        uow.commit()

    with uow_factory() as uow:
        found = uow.artifacts.list_reusable_narratives(
            artifact_id=artifact_id
        )

    assert found == {}
