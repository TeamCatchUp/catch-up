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
from typing import Literal

from pydantic import BaseModel

from catchup.server.wiki.schemas import LayoutItemResponse
from catchup.server.wiki.schemas import OwnerResponse


class ArtifactRefResponse(BaseModel):
    """큐 한 줄이 가리키는 문서를 담는다.

    문서가 놓인 자리(채널·폴더)를 함께 싣는다. 목록에서 "어디 문서인가"를
    보여 주려면 필요한데, 없으면 화면이 문서마다 위치 조회를 한 번씩 더
    한다. 미분류 문서는 둘 다 None이고, 채널 루트의 문서는 폴더만 None이다.
    """

    id: str
    title: str | None
    channel_id: str | None = None
    folder_id: str | None = None


class QueueItemResponse(BaseModel):
    """검토 큐 한 줄을 담는다.

    can_review는 이 사용자가 이 문서의 안건을 결정할 수 있는지를 나타낸다.
    목록에서 결정 버튼을 미리 잠그는 재료다. 이 값이 True여도 결정 경로는
    같은 판정을 다시 하므로, 화면 표시가 인가의 정본은 아니다.
    """

    proposal_id: str
    status: str
    artifact: ArtifactRefResponse
    summary: str
    origin: str
    contains_conflict: bool
    created_at: datetime
    owners: list[OwnerResponse] = []
    can_review: bool


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


class VariantResponse(BaseModel):
    """다툼 블록이 나란히 보여 주는 후보 하나를 담는다.

    claim_id가 블록 결정에 실을 승자 식별자다. 후보마다 근거를 따로 나르는
    이유는, 검토자가 어느 쪽이 맞는지 고르려면 후보별 근거가 섞이지 않아야
    하기 때문이다.
    """

    claim_id: str
    body: str
    sources: list[BlockSourceResponse] = []


class BlockVerdictResponse(BaseModel):
    """블록 하나에 내려진 결정을 담는다.

    저장된 결정을 그대로 비춘다. block_content_hash는 그 결정이 어떤 본문을
    보고 내려졌는지를 못박는 지문이며, 소비자는 다음 결정 요청에 지금 보고
    있는 본문의 지문을 실어 낡은 화면의 결정이 기록되는 것을 막는다.
    """

    proposal_id: str
    block_index: int
    block_content_hash: str
    verdict: str
    rejection_reason: str | None
    chosen_winner_claim_id: str | None
    reviewer: str
    reviewed_at: datetime


class BlockResponse(BaseModel):
    """변경안 본문 블록 하나를 담는다.

    claim_ids·proposal_ids·relation_ids가 블록 단위 Read Set(근거
    장부)이다. 문서의 어느 문장이 무엇을 근거로 삼았는지는 블록에서만
    알 수 있으므로, 상세 응답은 이것을 블록에 붙인 채로 내보낸다.

    relation_ids는 relation_section 블록에서만 값이 있고, 그 블록의
    근거는 이것 하나뿐이다. 빈 목록을 기본값으로 두는 이유는 관계
    장부가 없던 옛 블록도 그대로 읽혀야 하기 때문이다.

    block_index는 목록에서의 자리이며 블록 결정 요청의 경로에 그대로
    실린다. block_content_hash는 지금 본문의 지문이다.

    sources는 그 근거의 원문 인용이다. 근거 인용 없이 만들어진 옛 블록도
    그대로 읽혀야 하므로 빈 목록을 기본값으로 둔다. 다툼 블록은 근거가
    후보마다 갈리므로 sources를 비우고 variants에만 싣는다 — 둘 다 실으면
    같은 인용이 두 자리에 나와 소비자가 어느 쪽을 정본으로 삼을지 알 수
    없다.

    variants는 다툼 블록에서만 값이 있고 그 밖에서는 없음이다. 빈 목록으로
    두지 않는 이유는 "후보가 없는 블록"과 "후보를 다투는 블록인데 후보가
    비었다"를 소비자가 구별할 수 있어야 하기 때문이다.

    markdown은 이 블록을 화면에 그대로 그릴 수 있게 만든 조각이다. 산문이
    있으면 산문을, 없으면 body를 본문으로 쓴다. 소비자가 제목과 본문을
    다시 조립하지 않게 하려는 것이며, 정본은 heading·body·narrative다.

    change_reason은 발행판과 견줘 이 블록이 왜 바뀌었는지를 한 줄로 쓴
    것이다. 바뀌지 않은 블록과 발행판이 없어 견줄 것이 없는 경우는 없음이다.

    narrative는 블록을 읽는 사람을 위해 쓴 산문이다. 근거가 아니라 표현이라
    없을 수 있고(근거 인용이 없는 블록), 산문이 없던 옛 변경안도 그대로
    읽혀야 하므로 기본값을 없음으로 둔다. 검수자는 이 문장과 sources의
    인용 원문을 나란히 놓고 대조한다.
    """

    block_index: int
    block_kind: str
    heading: str
    body: str
    claim_ids: list[str]
    proposal_ids: list[str]
    ontology_version: str | None
    block_content_hash: str
    narrative: str | None = None
    relation_ids: list[str] = []
    sources: list[BlockSourceResponse] = []
    variants: list[VariantResponse] | None = None
    verdict: BlockVerdictResponse | None = None
    markdown: str
    change_reason: str | None = None


class BaseBlockResponse(BaseModel):
    """지금 발행돼 있는 판의 블록 하나를 담는다.

    검토자가 "지금 문서"와 "바뀔 문서"를 나란히 놓고 보게 하려는 재료다.
    발행판 블록에는 결정을 내릴 자리가 없으므로 block_content_hash와
    verdict를 싣지 않는다. 그 둘을 함께 실으면 소비자가 발행판 블록에도
    결정 요청을 보낼 수 있다고 읽는다.
    """

    block_index: int
    block_kind: str
    heading: str
    body: str
    narrative: str | None = None
    claim_ids: list[str] = []
    relation_ids: list[str] = []
    sources: list[BlockSourceResponse] = []


class BlockChangeResponse(BaseModel):
    """발행판과 견준 블록 하나의 변경을 담는다.

    자리를 두 개로 나눠 싣는다. block_index는 변경안 blocks 안 자리이고
    base_block_index는 base_blocks 안 자리다. 새로 생긴 블록은 발행판에
    짝이 없어 base_block_index가 없음이고, 빠진 블록은 변경안에 짝이 없어
    block_index가 없음이다.
    """

    change: Literal["added", "modified", "removed"]
    block_index: int | None
    base_block_index: int | None


class ReadSetResponse(BaseModel):
    """변경안 전체의 근거를 한 벌로 모아 담는다.

    블록별 목록의 합집합이다. 소비자가 "이 안건이 건드리는 근거 전체"를
    보려고 블록을 다시 순회하지 않게 하려는 편의값이며, 정본은 블록에
    붙은 목록이다.
    """

    claim_ids: list[str]
    proposal_ids: list[str]
    relation_ids: list[str] = []


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

    contains_conflict와 conflicts는 같은 사실 하나에서 나온다. 표시는 본문에
    다툼(contested) 블록이 있는지이고, 목록은 그 블록들이 가리키는 모순
    안건이다. 대상 노드와 subject_key라는 서로 다른 두 경로로 각각 구하던
    옛 방식은 둘이 어긋날 수 있었고, 그 자리를 없앴다.

    그래도 표시가 켜졌는데 목록이 빌 수 있다. 다툼 블록이 가리킨 안건이
    먼저 판정되면 계류 목록에서 빠지기 때문이다. 빈 목록은 표시가 틀렸다는
    뜻이 아니라 그 안건이 이미 결정됐다는 뜻이다.

    can_review는 이 사용자가 이 문서의 안건을 결정할 수 있는지를 나타낸다.
    상세는 결정 권한이 없어도 열린다. 읽는 것과 정하는 것은 다른 일이고,
    권한이 없다고 내용까지 가리면 검토자가 남의 채널 문서를 확인할 방법이
    없어지기 때문이다. 이 값이 True여도 결정 경로는 같은 판정을 다시 하므로
    화면 표시가 인가의 정본은 아니다.

    base_blocks는 지금 발행돼 있는 판의 블록이고 block_changes는 그것과
    견준 변경 목록이다. 아직 발행된 판이 없으면 base_blocks는 비고 변경안의
    모든 블록이 added가 된다. 계산을 백엔드에서 하는 이유는 블록 짝짓기
    규칙이 화면마다 달라지면 같은 안건이 소비자마다 다르게 보이기 때문이다.

    layout과 base_layout은 각각 blocks와 base_blocks를 문서 종류의 양식
    순서로 읽는 방법이다. 블록 배열 자체는 재배치하지 않는다. 저장된 순서가
    곧 블록 판정과 변경 목록이 가리키는 자리이기 때문이다. 발행판이 없으면
    base_layout도 빈 목록이다.
    """

    proposal_id: str
    status: str
    artifact: ArtifactRefResponse
    origin: str
    created_at: datetime
    base_revision_id: str | None
    contains_conflict: bool
    owners: list[OwnerResponse] = []
    can_review: bool
    blocks: list[BlockResponse]
    layout: list[LayoutItemResponse] = []
    base_blocks: list[BaseBlockResponse] = []
    base_layout: list[LayoutItemResponse] = []
    block_changes: list[BlockChangeResponse] = []
    read_set: ReadSetResponse
    conflicts: list[ConflictResponse]


class BlockVerdictRequest(BaseModel):
    """블록 하나에 내리는 결정을 담는다.

    block_content_hash는 검토자가 화면에서 본 본문의 지문이다. 필수인 이유는
    이것이 "무엇을 보고 결정했나"를 못박는 유일한 재료이기 때문이다. 없이
    받으면 사람이 읽지 않은 문장에 사람의 이름이 붙을 수 있다.
    """

    verdict: Literal["approved", "rejected"]
    rejection_reason: str | None = None
    chosen_winner_claim_id: uuid.UUID | None = None
    block_content_hash: str


class PublishRequest(BaseModel):
    """발행이 딛고 선 기준 판과 미결정 블록 처리 방법을 담는다.

    없음(null)은 "아직 판이 없는 문서"라는 뜻이지 생략이 아니다. 그래서
    기본값을 두지 않고 명시를 요구한다. 빠뜨린 요청을 "판 없음"으로 읽어
    주면 낙관적 잠금이 조용히 꺼진다. 값이 변경안의 기준과 다르면 발행은
    거부된다.

    undecided는 아직 결정이 없는 블록만 한 번에 처리한다. 이미 결정이
    있는 블록은 그대로 둔다. 보내지 않으면 미결정 블록이 하나라도 있을 때
    발행이 거부된다.

    Attributes:
        base_revision_id: 클라이언트가 본 기준 판을 가리킨다.
        undecided: 미결정 블록에 일괄로 내릴 결정을 나타낸다.
        rejection_reason: 일괄 반려의 사유를 담는다. reject일 때 필요하다.
    """

    base_revision_id: uuid.UUID | None
    undecided: Literal["approve", "reject"] | None = None
    rejection_reason: str | None = None


class PublishResponse(BaseModel):
    """발행 한 번의 결과를 담는다.

    전 블록이 반려됐으면 verdict가 rejected이고 판이 없어 revision 자리가
    비어 있다.

    owners는 이 발행이 끝난 시점의 담당자 명단이다. 담당자가 없던 문서를
    발행하면 발행한 사람이 담당자가 되므로, 명단을 함께 실어야 화면이
    문서를 다시 읽지 않고 담당자 표시를 고칠 수 있다.
    """

    proposal_id: str
    verdict: str
    revision_id: str | None
    revision_number: int | None
    blocks_published: int
    blocks_rejected: int
    contradictions_resolved: int
    claims_accepted: int
    owners: list[OwnerResponse] = []
