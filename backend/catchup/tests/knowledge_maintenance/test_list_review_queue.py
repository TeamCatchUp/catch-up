"""통합 검토 큐 목록 서비스를 fake 저장소 위에서 확인한다.

큐의 계약은 정렬과 거르기와 페이지다. 정렬은 created_at 오름차순 하나이고,
거르기를 다 적용한 뒤에 자른다. 충돌 여부는 정렬에 쓰지 않는다.

충돌 표시는 본문의 다툼(contested) 블록에서 나온다. 그래서 fake는
저장소가 내주는 블록을 실 DB처럼 직렬화·역직렬화해 돌린다 — 후보가
왕복에서 사라지면 표시도 함께 사라지므로, 그 경로까지 이 테스트가
지나가야 한다.
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

from catchup.knowledge_maintenance.domain.artifact import BLOCK_KIND_CLAIM_SECTION
from catchup.knowledge_maintenance.domain.artifact import BLOCK_KIND_CONTESTED
from catchup.knowledge_maintenance.domain.artifact import BLOCK_KIND_SUMMARY
from catchup.knowledge_maintenance.domain.artifact import ArtifactBlock
from catchup.knowledge_maintenance.domain.artifact import ContestedVariant
from catchup.knowledge_maintenance.domain.artifact import deserialize_blocks
from catchup.knowledge_maintenance.domain.artifact import serialize_blocks
from catchup.knowledge_maintenance.ports.artifacts import StoredArtifactProposal
from catchup.knowledge_maintenance.services.list_review_queue import list_review_queue

WORKSPACE_ID = 1
BASE_TIME = datetime(2026, 8, 1, 9, 0, tzinfo=UTC)


def _blocks(heading: str, body: str) -> tuple[ArtifactBlock, ...]:
    """근거를 갖춘 블록 한 벌을 만든다."""
    return (
        ArtifactBlock(
            block_kind=BLOCK_KIND_CLAIM_SECTION,
            heading=heading,
            body=body,
            claim_ids=(uuid.uuid4(),),
            proposal_ids=(),
            ontology_version="1",
        ),
    )


def _contested_blocks(heading: str, body: str) -> tuple[ArtifactBlock, ...]:
    """값이 갈린 속성을 다툼 블록으로 담은 한 벌을 만든다."""
    winner = uuid.uuid4()
    loser = uuid.uuid4()
    return (
        ArtifactBlock(
            block_kind=BLOCK_KIND_CONTESTED,
            heading=heading,
            body=body,
            claim_ids=(winner, loser),
            proposal_ids=(uuid.uuid4(),),
            ontology_version="1",
            variants=(
                ContestedVariant(claim_id=winner, body="9월", sources=()),
                ContestedVariant(claim_id=loser, body="10월", sources=()),
            ),
        ),
    )


def _summary_block(
    *,
    narrative: str | None,
    heading: str = "결제 기능",
    body: str = "claim 3건 · 관계 1건 · 최초 보고 2026-06-03T07:59:38.407000+00:00",
) -> ArtifactBlock:
    """문서 맨 앞에 오는 summary 블록 하나를 만든다."""
    return ArtifactBlock(
        block_kind=BLOCK_KIND_SUMMARY,
        heading=heading,
        body=body,
        claim_ids=(uuid.uuid4(),),
        proposal_ids=(),
        ontology_version="1",
        narrative=narrative,
    )


@dataclass
class FakeState:
    """변경안들을 담아 두는 공유 상태다."""

    proposals: list[dict[str, Any]] = field(default_factory=list)

    def add_proposal(
        self,
        *,
        contested: bool = False,
        created_at: datetime = BASE_TIME,
        status: str = "pending",
        origin: str = "compiled",
        heading: str = "release_month",
        body: str = "9월 출시 예정입니다.",
        title: str = "결제 기능",
        artifact_id: uuid.UUID | None = None,
        blocks: tuple[ArtifactBlock, ...] | None = None,
    ) -> uuid.UUID:
        """검토를 기다리는 문서 변경안 한 건을 넣는다.

        blocks를 주면 heading·body·contested 대신 그 블록들을 그대로 담는다.
        """
        proposal_id = uuid.uuid4()
        if blocks is None:
            blocks = (
                _contested_blocks(heading, body)
                if contested
                else _blocks(heading, body)
            )
        self.proposals.append(
            {
                "id": proposal_id,
                "artifact_id": artifact_id or uuid.uuid4(),
                "subject_node_id": uuid.uuid4(),
                "title": title,
                "status": status,
                # 실 DB처럼 직렬화한 형태로 담는다.
                "blocks": serialize_blocks(blocks),
                "content_hash": "0" * 64,
                "base_revision_id": None,
                "rejection_reason": None,
                "origin": origin,
                "created_at": created_at,
            }
        )
        return proposal_id


@dataclass
class FakeArtifactRepo:
    """artifact 저장소의 목록 조회만 실 어댑터처럼 흉내 낸다.

    실 어댑터와 같이 pending 행만 내주고 `(created_at, id)` 순서로
    정렬한다. limit/offset도 그 순서 위에서 자른다 — 서비스가 자기
    정렬을 쓰는지 저장소 순서에 기대는지가 여기서 드러난다.
    """

    state: FakeState

    def list_pending_proposals(
        self,
        *,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[StoredArtifactProposal]:
        rows = sorted(
            (row for row in self.state.proposals if row["status"] == "pending"),
            key=lambda row: (row["created_at"], str(row["id"])),
        )
        if offset:
            rows = rows[offset:]
        if limit is not None:
            rows = rows[:limit]
        return [
            StoredArtifactProposal(
                id=row["id"],
                artifact_id=row["artifact_id"],
                subject_node_id=row["subject_node_id"],
                title=row["title"],
                status=row["status"],
                blocks=deserialize_blocks(row["blocks"]),
                content_hash=row["content_hash"],
                base_revision_id=row["base_revision_id"],
                rejection_reason=row["rejection_reason"],
                origin=row["origin"],
                created_at=row["created_at"],
            )
            for row in rows
        ]


@dataclass
class FakeUnitOfWork:
    """읽기 전용 UnitOfWork를 대신한다. commit이 없다."""

    state: FakeState

    def __post_init__(self) -> None:
        self.artifacts = FakeArtifactRepo(self.state)

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None


def test_sorts_by_created_at_only() -> None:
    """충돌 안건도 앞으로 오지 않는다. 오래된 순 하나다."""
    state = FakeState()
    calm_old = state.add_proposal(created_at=BASE_TIME)
    hot_new = state.add_proposal(
        contested=True, created_at=BASE_TIME + timedelta(hours=1)
    )

    page = list_review_queue(
        FakeUnitOfWork(state), workspace_id=WORKSPACE_ID
    )

    assert [item.proposal_id for item in page.items] == [calm_old, hot_new]
    assert [item.contains_conflict for item in page.items] == [False, True]
    assert page.total == 2


def test_filters_by_artifact_ids_and_time_window() -> None:
    """문서 id와 시간창으로 각각 거르고 total도 거른 뒤의 수다."""
    state = FakeState()
    artifact_a = uuid.uuid4()
    artifact_b = uuid.uuid4()
    on_a = state.add_proposal(artifact_id=artifact_a, created_at=BASE_TIME)
    on_b_late = state.add_proposal(
        artifact_id=artifact_b, created_at=BASE_TIME + timedelta(hours=2)
    )

    only_a = list_review_queue(
        FakeUnitOfWork(state),
        workspace_id=WORKSPACE_ID,
        artifact_ids=frozenset({artifact_a}),
    )
    after = list_review_queue(
        FakeUnitOfWork(state),
        workspace_id=WORKSPACE_ID,
        created_after=BASE_TIME + timedelta(hours=1),
    )
    before = list_review_queue(
        FakeUnitOfWork(state),
        workspace_id=WORKSPACE_ID,
        created_before=BASE_TIME + timedelta(hours=1),
    )
    empty = list_review_queue(
        FakeUnitOfWork(state),
        workspace_id=WORKSPACE_ID,
        artifact_ids=frozenset(),
    )

    assert [item.proposal_id for item in only_a.items] == [on_a]
    assert only_a.total == 1
    assert [item.proposal_id for item in after.items] == [on_b_late]
    assert after.total == 1
    assert [item.proposal_id for item in before.items] == [on_a]
    assert before.total == 1
    assert empty.items == ()
    assert empty.total == 0


def test_queue_pagination_and_total() -> None:
    """limit/offset은 정렬 뒤에 자르고 total은 거른 뒤의 전체 수다."""
    state = FakeState()
    calm = [
        state.add_proposal(created_at=BASE_TIME + timedelta(hours=index))
        for index in range(4)
    ]
    hot = state.add_proposal(
        contested=True, created_at=BASE_TIME + timedelta(hours=9)
    )

    first = list_review_queue(
        FakeUnitOfWork(state), workspace_id=WORKSPACE_ID, limit=2
    )
    second = list_review_queue(
        FakeUnitOfWork(state),
        workspace_id=WORKSPACE_ID,
        limit=2,
        offset=2,
    )
    last = list_review_queue(
        FakeUnitOfWork(state),
        workspace_id=WORKSPACE_ID,
        limit=2,
        offset=4,
    )

    assert [item.proposal_id for item in first.items] == [calm[0], calm[1]]
    assert [item.proposal_id for item in second.items] == [calm[2], calm[3]]
    assert [item.proposal_id for item in last.items] == [hot]
    assert first.total == 5
    assert second.total == 5


def test_contains_conflict_matches_contested_blocks() -> None:
    """본문에 다툼 블록이 있는 안건만 충돌로 표시한다.

    표시의 근거가 본문 하나뿐이므로, 상세가 보여 주는 충돌 목록과 어긋날
    자리가 없다. 대상 노드로 판정하던 옛 경로는 목록과 다른 사실을 봐서
    표시만 켜지는 안건을 만들 수 있었다.
    """
    state = FakeState()
    contested_proposal = state.add_proposal(contested=True)
    calm_proposal = state.add_proposal()

    page = list_review_queue(
        FakeUnitOfWork(state), workspace_id=WORKSPACE_ID
    )

    by_id = {item.proposal_id: item for item in page.items}
    assert by_id[contested_proposal].contains_conflict is True
    assert by_id[calm_proposal].contains_conflict is False


def test_conflict_filter_narrows_total_too() -> None:
    """contains_conflict로 거르면 total도 거른 뒤의 수다."""
    state = FakeState()
    hot = state.add_proposal(contested=True)
    calm = state.add_proposal(created_at=BASE_TIME + timedelta(hours=1))

    only_hot = list_review_queue(
        FakeUnitOfWork(state),
        workspace_id=WORKSPACE_ID,
        contains_conflict=True,
    )
    only_calm = list_review_queue(
        FakeUnitOfWork(state),
        workspace_id=WORKSPACE_ID,
        contains_conflict=False,
    )

    assert [item.proposal_id for item in only_hot.items] == [hot]
    assert only_hot.total == 1
    assert [item.proposal_id for item in only_calm.items] == [calm]
    assert only_calm.total == 1


def test_queue_item_carries_origin_title_and_summary() -> None:
    """항목은 origin과 제목, 본문에서 조립한 요약을 실어 준다."""
    state = FakeState()
    proposal_id = state.add_proposal(
        origin="manual",
        heading="release_month",
        body="9월 출시 예정입니다.\n둘째 줄은 요약에 넣지 않는다.",
        title="결제 기능",
    )

    page = list_review_queue(
        FakeUnitOfWork(state), workspace_id=WORKSPACE_ID
    )

    item = page.items[0]
    assert item.proposal_id == proposal_id
    assert item.origin == "manual"
    assert item.title == "결제 기능"
    assert item.status == "pending"
    assert item.created_at == BASE_TIME
    assert item.summary == "release_month: 9월 출시 예정입니다."


def test_summary_uses_narrative_headline_of_summary_block() -> None:
    """첫 summary 블록에 산문이 있으면 그 첫 줄이 요약이다."""
    state = FakeState()
    state.add_proposal(
        blocks=(
            _summary_block(
                narrative="**결제 기능은 9월 출시를 목표로 한다**\n\n근거는 세 건이다.",
            ),
        )
        + _blocks("release_month", "9월 출시 예정입니다."),
    )

    page = list_review_queue(
        FakeUnitOfWork(state), workspace_id=WORKSPACE_ID
    )

    assert page.items[0].summary == "결제 기능은 9월 출시를 목표로 한다"


def test_summary_skips_aggregate_line_when_narrative_missing() -> None:
    """산문 없는 summary 블록은 건너뛰고 다음 블록으로 요약을 만든다."""
    state = FakeState()
    state.add_proposal(
        blocks=(_summary_block(narrative=None),)
        + _blocks("release_month", "9월 출시 예정입니다.\n둘째 줄."),
    )

    page = list_review_queue(
        FakeUnitOfWork(state), workspace_id=WORKSPACE_ID
    )

    assert page.items[0].summary == "release_month: 9월 출시 예정입니다."


def test_summary_is_empty_when_only_narrativeless_summary_block() -> None:
    """건너뛸 다음 블록이 없으면 요약은 빈 문자열이다.

    집계 한 줄에는 ISO 시각이 들어 있어, 그대로 실으면 검토 화면 배너가
    기계 값을 보여 준다.
    """
    state = FakeState()
    state.add_proposal(blocks=(_summary_block(narrative=None),))

    page = list_review_queue(
        FakeUnitOfWork(state), workspace_id=WORKSPACE_ID
    )

    assert page.items[0].summary == ""

def test_negative_paging_is_refused() -> None:
    """음수 페이지 인자는 조용히 넘기지 않는다."""
    state = FakeState()
    state.add_proposal()

    with pytest.raises(ValueError):
        list_review_queue(
            FakeUnitOfWork(state), workspace_id=WORKSPACE_ID, limit=-1
        )
    with pytest.raises(ValueError):
        list_review_queue(
            FakeUnitOfWork(state), workspace_id=WORKSPACE_ID, offset=-1
        )
