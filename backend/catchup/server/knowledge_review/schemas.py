"""검수 루프 API의 요청·응답 모양을 정의한다.

서비스가 돌려주는 dataclass를 그대로 내보내지 않고 여기서 한 번 옮겨
담는다. 응답은 소비자와의 계약이라, 도메인 값 객체의 필드가 바뀔 때
그것이 곧바로 API 변경이 되는 상태를 만들지 않기 위한 것이다.

식별자는 문자열로 내보낸다. JSON에 UUID 타입이 없고, 소비자가 그것을
다시 파싱하지 않고 그대로 경로에 실을 수 있어야 하기 때문이다.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel
from pydantic import Field


class ArtifactRefResponse(BaseModel):
    """큐 한 줄이 가리키는 문서를 담는다."""

    id: str
    title: str | None


class QueueItemResponse(BaseModel):
    """검토 큐 한 줄을 담는다."""

    proposal_id: str
    status: str
    artifact: ArtifactRefResponse
    summary: str
    origin: str
    contains_conflict: bool
    created_at: datetime


class QueuePageResponse(BaseModel):
    """검토 큐 한 페이지를 담는다.

    total은 거르기를 적용한 뒤의 전체 수다. limit·offset을 함께 실어
    소비자가 다음 쪽을 자기 상태 없이 계산할 수 있게 한다.
    """

    items: list[QueueItemResponse]
    total: int
    limit: int
    offset: int


class BlockSourceResponse(BaseModel):
    """블록 본문 한 줄의 근거 인용을 담는다.

    statement가 근거의 정본이고 body의 값 표기는 색인용 라벨이다.
    citation_verified는 신뢰도 표시 재료다 — True 검증 인용, False
    대조 실패, None evidence 없음.
    """

    claim_id: str
    statement: str
    observed_at: datetime
    citation_verified: bool | None


class BlockResponse(BaseModel):
    """변경안 본문 블록 하나를 담는다.

    claim_ids·proposal_ids가 블록 단위 Read Set(근거 장부)이다. 문서의
    어느 문장이 무엇을 근거로 삼았는지는 블록에서만 알 수 있으므로,
    상세 응답은 이것을 블록에 붙인 채로 내보낸다.

    sources는 그 근거의 원문 인용이다. 근거 인용 없이 만들어진 옛 블록도
    그대로 읽혀야 하므로 빈 목록을 기본값으로 둔다.
    """

    block_kind: str
    heading: str
    body: str
    claim_ids: list[str]
    proposal_ids: list[str]
    ontology_version: str | None
    sources: list[BlockSourceResponse] = []


class ReadSetResponse(BaseModel):
    """변경안 전체의 근거를 한 벌로 모아 담는다.

    블록별 목록의 합집합이다. 소비자가 "이 안건이 건드리는 근거 전체"를
    보려고 블록을 다시 순회하지 않게 하려는 편의값이며, 정본은 블록에
    붙은 목록이다.
    """

    claim_ids: list[str]
    proposal_ids: list[str]


class ConflictValueResponse(BaseModel):
    """모순 안건의 값 후보 하나를 담는다.

    claim_id가 판정 요청에 실을 승자 식별자다.
    """

    claim_id: str
    value: Any
    statement: str | None


class ConflictResponse(BaseModel):
    """이 문서의 대상에 걸린 모순 안건 하나를 담는다."""

    proposal_id: str
    predicate: str
    summary: str
    values: list[ConflictValueResponse]


class ProposalDetailResponse(BaseModel):
    """변경안 상세를 담는다.

    contains_conflict가 true인데 conflicts가 빈 경우가 있다. 충돌 표시는
    값 후보 claim을 노드로 되짚어 판정하고, 목록은 판정 근거의 subject_key로
    모으기 때문이다. 노드가 나중에 생긴 대상은 key가 낡은 채 남아 목록에서
    빠질 수 있다 — 표시를 지우는 대신 그대로 알린다.
    """

    proposal_id: str
    status: str
    artifact: ArtifactRefResponse
    origin: str
    created_at: datetime
    base_revision_id: str | None
    contains_conflict: bool
    blocks: list[BlockResponse]
    read_set: ReadSetResponse
    conflicts: list[ConflictResponse]


class RejectRequest(BaseModel):
    """반려 사유를 담는다. 사유 없는 반려는 서비스와 DB가 모두 거부한다."""

    reason: str


class ResolveRequest(BaseModel):
    """모순 판정의 승자를 담는다."""

    winner_claim_id: uuid.UUID


class DecisionResponse(BaseModel):
    """문서 변경안 결정 한 번의 결과를 담는다.

    승인이면 새로 쌓인 판과 확정된 claim 수가 실리고, 반려면 판이 없어
    비어 있다.
    """

    proposal_id: str
    verdict: str
    revision_id: str | None = None
    revision_number: int | None = None
    claims_accepted: int = 0


class ResolveResponse(BaseModel):
    """모순 판정 한 번의 결과를 담는다.

    적용은 이 응답 시점에 일어나지 않는다. 결정 저널만 남고, 실제 구간
    닫기는 apply가 한다.
    """

    proposal_id: str
    winner_claim_id: str
    loser_claim_ids: list[str]
    valid_to: datetime
    valid_to_source: str


class ApplyResponse(BaseModel):
    """적용 한 번의 집계를 담는다."""

    proposals_applied: int
    proposals_failed: int
    candidates_resolved: int
    candidates_already_resolved: int
    claims_superseded: int = Field(default=0)
    claims_invalidated: int = Field(default=0)
    claims_already_closed: int = Field(default=0)
