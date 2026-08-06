"""검토를 기다리는 문서 변경안을 하나의 큐로 모아 읽는다.

큐의 순서가 이 서비스의 계약이다. 충돌(모순)이 걸린 안건이 먼저이고 그
안에서 오래된 것이 먼저다. 사람이 하루에 볼 수 있는 안건 수가 정해져
있으므로, 답이 갈린 대상의 문서를 먼저 손에 잡히게 만드는 것이 목록의
일이다.

자르기는 정렬 뒤에 한다. 저장소에서 미리 자르고 그 안에서 정렬하면 2쪽에
있던 충돌 안건이 1쪽으로 올라오지 못한다 — 페이지 경계에서 계약이 조용히
깨지는 셈이다. 그래서 이 서비스는 계류 중인 변경안을 전부 읽고 Python에서
정렬·절단한다. MVP 규모(workspace당 계류 안건 수십~수백 건)에서 받아들일
비용이며, 이 수가 커지면 충돌 표시를 SQL로 내려 정렬까지 DB에 맡기는 것이
다음 수순이다.

충돌 판정은 문서의 대상 노드로 한다. 계류 중인 모순의 값 후보 claim들이
가리키는 subject 노드 집합을 저장소에서 받아, 변경안이 설명하는 노드가 그
집합에 있으면 충돌로 표시한다. 안건의 본문(Read Set)을 뒤지지 않는 이유는
문서가 아직 그 모순을 열린 질문으로 옮겨 적지 못한 상태에서도 검토자가
"이 대상에 답이 갈렸다"를 알아야 하기 때문이다.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from types import TracebackType
from typing import Protocol
from typing import Self

from catchup.knowledge_maintenance.domain.artifact import ArtifactBlock
from catchup.knowledge_maintenance.ports.artifacts import ArtifactRepository
from catchup.knowledge_maintenance.ports.artifacts import StoredArtifactProposal
from catchup.knowledge_maintenance.ports.mutation_proposals import (
    MutationProposalRepository,
)
from catchup.observability.logging import get_logger

logger = get_logger(__name__)

# 목록 한 줄에 들어갈 요약의 길이 상한이다. 큐는 훑어보는 화면이라
# 본문을 통째로 실으면 오히려 고르기 어려워진다.
SUMMARY_MAX_LENGTH = 160


class ReviewQueueUnitOfWork(Protocol):
    """검토 큐 조회가 쓰는 읽기 전용 transaction 경계를 정의한다.

    commit을 요구하지 않는다. 이 경로는 아무것도 쓰지 않기 때문이다.
    두 저장소를 함께 받는 이유는 충돌 표시가 mutation 쪽 사실이라
    한 transaction 안에서 같은 시점을 봐야 하기 때문이다.
    """

    artifacts: ArtifactRepository
    mutation_proposals: MutationProposalRepository

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class ReviewQueueItem:
    """검토 큐 한 줄을 표현한다.

    Attributes:
        proposal_id: 이 줄이 가리키는 변경안을 식별한다.
        artifact_id: 변경안이 붙은 문서를 가리킨다.
        title: 문서 제목을 보존한다.
        status: 변경안의 검토 상태를 나타낸다.
        summary: 본문에서 조립한 한 줄 요약을 담는다.
        origin: 변경안이 어디서 왔는지 나타낸다.
        contains_conflict: 이 문서의 대상에 계류 중인 모순이 걸려 있는지
            나타낸다. 큐의 첫 정렬 기준이다.
        created_at: 변경안이 올라온 시각을 나타낸다.
    """

    proposal_id: uuid.UUID
    artifact_id: uuid.UUID
    title: str | None
    status: str
    summary: str
    origin: str
    contains_conflict: bool
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ReviewQueuePage:
    """큐의 한 페이지를 표현한다.

    Attributes:
        items: 이 페이지에 실린 줄들이다. 이미 정렬된 순서다.
        total: 거르기를 적용한 뒤의 전체 수다. 페이지 크기와 무관하다.
    """

    items: tuple[ReviewQueueItem, ...]
    total: int


def list_review_queue(
    uow: ReviewQueueUnitOfWork,
    *,
    workspace_id: int,
    contains_conflict: bool | None = None,
    limit: int = 50,
    offset: int = 0,
) -> ReviewQueuePage:
    """계류 중인 변경안을 충돌 우선·오래된 순으로 한 페이지 읽는다.

    `contains_conflict`를 주면 그 값과 같은 줄만 남긴다. total도 거른
    뒤의 수다 — 거른 목록의 마지막 쪽을 세는 근거이므로 거르기 전 수를
    주면 호출자가 빈 쪽을 요청하게 된다.

    Raises:
        ValueError: limit이나 offset이 음수일 때 던진다.
    """
    if limit < 0:
        raise ValueError("limit은 음수일 수 없다")
    if offset < 0:
        raise ValueError("offset은 음수일 수 없다")

    with uow:
        proposals = uow.artifacts.list_pending_proposals()
        contested = uow.mutation_proposals.find_contested_subject_node_ids(
            workspace_id=workspace_id,
        )

    items = [
        _to_item(proposal, contested=contested) for proposal in proposals
    ]
    if contains_conflict is not None:
        items = [
            item
            for item in items
            if item.contains_conflict is contains_conflict
        ]
    # 충돌 우선, 그 안에서 오래된 순이다. sorted는 안정 정렬이라 시각까지
    # 같은 줄은 저장소가 준 순서(created_at, id)를 그대로 지킨다.
    items.sort(key=lambda item: (not item.contains_conflict, item.created_at))

    total = len(items)
    page = tuple(items[offset : offset + limit])
    logger.info(
        "review_queue_listed",
        workspace_id=workspace_id,
        total=total,
        returned=len(page),
        conflict_count=sum(1 for item in items if item.contains_conflict),
    )
    return ReviewQueuePage(items=page, total=total)


def _to_item(
    proposal: StoredArtifactProposal,
    *,
    contested: frozenset[uuid.UUID],
) -> ReviewQueueItem:
    """변경안 하나를 큐 한 줄로 옮긴다."""
    return ReviewQueueItem(
        proposal_id=proposal.id,
        artifact_id=proposal.artifact_id,
        title=proposal.title,
        status=proposal.status,
        summary=_summary(proposal.blocks),
        origin=proposal.origin,
        contains_conflict=proposal.subject_node_id in contested,
        created_at=proposal.created_at,
    )


def _summary(blocks: tuple[ArtifactBlock, ...]) -> str:
    """첫 블록의 제목과 본문 첫 줄로 한 줄 요약을 조립한다.

    제목만으로는 같은 속성을 다루는 안건들이 구별되지 않고, 본문 전체는
    목록에 실을 수 없다. 첫 줄까지가 "무엇이 달라졌나"를 가리는 최소
    단위다. 블록이 없으면 빈 문자열이다.
    """
    if not blocks:
        return ""
    block = blocks[0]
    lines = [line.strip() for line in block.body.splitlines() if line.strip()]
    parts = [part for part in (block.heading.strip(), *lines[:1]) if part]
    summary = ": ".join(parts)
    if len(summary) > SUMMARY_MAX_LENGTH:
        return summary[: SUMMARY_MAX_LENGTH - 1] + "…"
    return summary
