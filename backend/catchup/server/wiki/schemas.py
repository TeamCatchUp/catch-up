"""채널·폴더 관리 API의 요청·응답 모양을 정의한다.

ORM 모델을 그대로 내보내지 않고 여기서 한 번 옮겨 담는다. 응답은
소비자와의 계약이라, 테이블 컬럼이 바뀔 때 그것이 곧바로 API 변경이 되는
상태를 만들지 않기 위한 것이다.

식별자는 문자열로 내보낸다. JSON에 UUID 타입이 없고, 소비자가 그것을
다시 파싱하지 않고 그대로 경로에 실을 수 있어야 하기 때문이다.

요청 모델은 모르는 필드를 거부한다(extra="forbid"). 폴더는 depth 1이
구조 자체의 약속이라 `parent_folder_id` 같은 필드가 조용히 무시되면
소비자는 중첩이 만들어졌다고 믿는다. 422로 끊어 그 오해를 없앤다.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import field_validator


class TestKnowledgeMaintenanceSettingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool
    execution_anchor_at: datetime
    interval_minutes: int = Field(gt=0)

    @field_validator("execution_anchor_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("execution_anchor_at must include timezone information")
        return value


class TestKnowledgeMaintenanceSettingResponse(BaseModel):
    id: int
    workspace_id: int
    channel_talk_credential_id: int
    enabled: bool
    execution_anchor_at: datetime
    interval_minutes: int

    model_config = ConfigDict(from_attributes=True)


class TestKnowledgeMaintenanceSettingListResponse(BaseModel):
    items: list[TestKnowledgeMaintenanceSettingResponse]


class ChannelCreateRequest(BaseModel):
    """채널 생성 요청을 담는다."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)


class ChannelOnboardingRequest(BaseModel):
    """온보딩 위자드 1단계의 선택 결과를 담는다.

    고르는 것은 preset id뿐이다. 선택 규칙을 직접 실어 보낼 자리는 두지
    않는다. raw spec 입구가 열리면 카탈로그가 규칙의 유일한 출처라는
    약속이 깨진다.

    목적과 문서 종류는 여러 개를 고를 수 있다. 한 채널이 여러 목적을 함께
    갖는 것이 보통이고, 목적마다 필요한 문서 종류가 다르다. 둘 다 최소
    하나는 있어야 한다. 목적이 없으면 문서를 왜 만드는지가 비고, 문서
    종류가 없으면 만들 문서가 없다.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=20)
    domain_preset: str
    purpose_presets: list[str] = Field(min_length=1)
    kinds: list[str] = Field(min_length=1)
    style_preset: str


class ChannelRenameRequest(BaseModel):
    """채널 이름 변경 요청을 담는다."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)


class FolderCreateRequest(BaseModel):
    """폴더 생성 요청을 담는다.

    상위 폴더를 가리키는 필드가 없다 — 폴더는 채널 바로 아래 한 겹뿐이다.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)


class FolderRenameRequest(BaseModel):
    """폴더 이름 변경 요청을 담는다."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)


class ChannelResponse(BaseModel):
    """채널 하나의 식별 정보를 담는다."""

    id: str
    name: str
    workspace_id: int


class DefinitionSummaryResponse(BaseModel):
    """채널 안 정의 하나를 요약해 담는다.

    문서 종류(kind)와 그 종류의 문서가 놓일 폴더, 그리고 이 정의가 맡은
    목적 preset들을 싣는다. folder_id가 None이면 폴더 없이 채널 바로 아래
    놓이는 정의다.
    """

    definition_id: str
    kind: str
    folder_id: str | None
    purpose_presets: list[str] = []


class ChannelOnboardingResponse(BaseModel):
    """만들어진 채널·정의와 어휘 발행 결과를 담는다.

    vocabulary_version이 None이면 더할 어휘가 없어 발행을 건너뛴 것이다.
    같은 도메인으로 두 번째 채널을 만든 자리가 그렇다.
    """

    channel: ChannelResponse
    domain_preset: str
    purpose_presets: list[str]
    style_preset: str
    vocabulary_version: str | None
    definitions: list[DefinitionSummaryResponse]


class FolderResponse(BaseModel):
    """폴더 하나의 식별 정보를 담는다."""

    id: str
    name: str
    channel_id: str


class ChannelListItemResponse(BaseModel):
    """채널 목록 한 줄을 담는다.

    is_admin을 함께 싣는다. 소비자가 관리 버튼을 보일지 정하려면 역할을
    알아야 하는데, 그것만 따로 물어보게 하면 목록과 판정이 두 번의 왕복
    사이에서 어긋난다.
    """

    id: str
    name: str
    workspace_id: int
    is_admin: bool
    document_count: int
    folders: list[FolderResponse]
    purpose_presets: list[str] = []
    definitions: list[DefinitionSummaryResponse] = []


class ChannelListResponse(BaseModel):
    """채널 목록 전체를 담는다."""

    channels: list[ChannelListItemResponse]


class OwnerResponse(BaseModel):
    """담당자 한 명을 화면에 그릴 만큼 담는다.

    id만 내보내면 화면이 이름과 사진을 얻으려고 사용자 조회를 한 번 더
    해야 한다. 담당자는 목록에서도 문서에서도 늘 사람 이름으로 보이므로
    이름과 사진을 같이 싣는다. 사진은 없을 수 있어 None을 허용한다.
    """

    user_id: int
    display_name: str
    profile_image_url: str | None


class WorkspaceMemberListResponse(BaseModel):
    """워크스페이스의 활성 구성원 목록을 담는다.

    항목 모양은 담당자 응답(OwnerResponse)과 같다. 담당자를 고르는 화면이
    "고를 수 있는 사람"과 "이미 담당인 사람"을 같은 타입으로 다루게 하려는
    것이다. 모양이 다르면 화면이 두 목록을 맞춰 보려고 변환을 한 겹 더
    둬야 한다.
    """

    items: list[OwnerResponse]


class ArtifactOwnerResponse(BaseModel):
    """문서 담당자 한 명의 지정 결과를 담는다.

    담당자 명단 전체를 싣는다. 지정은 멱등이라 응답 코드만으로는 "지금
    누가 담당인가"를 알 수 없는데, 그 답을 위해 목록을 한 번 더 왕복하면
    두 응답 사이에서 명단이 갈린다.
    """

    artifact_id: str
    owners: list[OwnerResponse]


class ChannelAdminResponse(BaseModel):
    """채널 관리자 한 명의 지정 결과를 담는다."""

    channel_id: str
    user_ids: list[int]


class PresetKindResponse(BaseModel):
    """온보딩이 고를 문서 종류 하나를 담는다.

    선택 규칙(spec_template)은 싣지 않는다. 규칙이 응답에 나가면
    소비자가 그것을 손봐 되돌려 보낼 입구가 생기고, 정의를 만드는 길이
    카탈로그 밖으로 하나 더 열린다.
    """

    kind: str
    label: str
    description: str
    example_text: str


class PresetPurposeResponse(BaseModel):
    """채널을 왜 만드는지에 해당하는 목적 하나를 담는다."""

    id: str
    label: str
    recommended_kind: str


class PresetDomainResponse(BaseModel):
    """한 업무 영역의 preset 묶음을 담는다.

    seed 어휘는 싣지 않는다. 온보딩 화면이 쓰지 않는 값이라, 내보내면
    소비자가 기대할 계약만 늘어난다.
    """

    id: str
    label: str
    purposes: list[PresetPurposeResponse]
    kinds: list[PresetKindResponse]


class PresetStyleResponse(BaseModel):
    """문서를 어떤 문체로 쓸지 고르는 preset 하나를 담는다."""

    id: str
    label: str


class DefinitionPresetsResponse(BaseModel):
    """온보딩이 고를 preset 카탈로그 전체를 담는다."""

    domains: list[PresetDomainResponse]
    styles: list[PresetStyleResponse]


class ArtifactBlockSourceResponse(BaseModel):
    """블록 한 칸이 근거로 삼은 claim의 원문 인용을 담는다.

    산문과 함께 실어야 읽는 쪽이 문장을 근거와 대조할 수 있다. 근거 지위는
    statement에만 있고 산문에는 없다.
    """

    claim_id: str
    statement: str
    observed_at: datetime
    citation_verified: bool | None


class ArtifactDocumentBlockResponse(BaseModel):
    """발행된 문서의 블록 하나를 담는다.

    narrative는 표현이라 없을 수 있다. 산문이 없던 옛 판도 그대로 읽혀야
    하므로 없음을 허용한다.
    """

    block_index: int
    block_kind: str
    heading: str
    narrative: str | None
    body: str
    claim_ids: list[str]
    relation_ids: list[str]
    sources: list[ArtifactBlockSourceResponse]


class LayoutTableRowResponse(BaseModel):
    """읽기 레이아웃이 만든 표의 행 하나를 담는다."""

    label: str
    value: str


class LayoutItemResponse(BaseModel):
    """읽기 레이아웃이 만든 표시 항목 하나를 담는다.

    blocks를 대신하지 않고 blocks 옆에 함께 실린다. 이 목록은 어떤 순서와
    어떤 이름으로 읽힐지만 정하고, 블록의 내용과 근거는 blocks에 그대로
    있다.

    block_index는 언제나 blocks 배열에서의 자리다. 표시 순서에 맞춰 번호를
    다시 매기지 않는다. 블록 판정과 변경 목록이 그 자리로 블록을 가리키기
    때문이다.

    item_kind가 table이면 여러 블록을 한 표로 묶은 항목이라 block_index가
    없고 block_indexes와 rows가 찬다. table 항목에서 rows[i]는
    block_indexes[i]의 블록에서 나온다. 두 목록은 같은 순서다. placeholder는
    값이 아직 없다는 사실을 알리는 항목이라 가리킬 블록이 없고 text만 있다.
    """

    item_kind: Literal["block", "table", "placeholder"]
    heading: str
    block_index: int | None = None
    block_indexes: list[int] = []
    rows: list[LayoutTableRowResponse] = []
    text: str | None = None


class ArtifactDocumentResponse(BaseModel):
    """지금 발행된 판 하나를 문서 정보와 함께 담는다.

    published_at은 그 판이 만들어진 시각이다. 판은 덮어쓰지 않고 쌓으므로
    이 값이 곧 그 문장이 발행된 시점이다.

    담당자와 즐겨찾기를 함께 싣는다. 문서 화면이 늘 같이 그리는 값이라,
    따로 물어보게 하면 한 화면에 왕복이 세 번 생기고 그 사이에 값이 갈린다.
    """

    artifact_id: str
    channel_id: str | None
    definition_id: str | None
    kind: str
    title: str
    folder_id: str | None
    owners: list[OwnerResponse]
    is_favorite: bool
    revision_id: str
    published_at: datetime
    blocks: list[ArtifactDocumentBlockResponse]
    layout: list[LayoutItemResponse] = []


class LatestRevisionResponse(BaseModel):
    """문서의 가장 최근 발행 판을 목록 한 줄만큼 담는다."""

    revision_id: str
    revision_number: int
    published_at: datetime


class ArtifactListItemResponse(BaseModel):
    """문서 목록 한 줄을 담는다.

    상태·담당자·즐겨찾기를 한 줄에 함께 싣는다. 목록 화면이 줄마다 그리는
    값이라, 따로 물어보게 하면 한 화면에 왕복이 여러 번 생기고 그 사이에
    값이 갈린다.

    status는 컬럼이 아니라 계류 제안 수와 최신 판에서 계산한 값이다. 계류
    제안이 있으면 그것이 먼저다. 발행본이 있어도 사람이 볼 일이 남아 있는
    쪽을 먼저 알려야 하기 때문이다.

    last_activity_at은 이 문서가 마지막으로 움직인 시각이다. 가장 최근 발행
    시각과 가장 최근 변경안 도착 시각 중 늦은 쪽이고, 둘 다 없으면 문서
    생성 시각이다. 변경안은 계류·승인·반려를 가리지 않는다. 도착 자체가
    문서가 움직인 사실이기 때문이다. 값은 항상 있다.
    """

    artifact_id: str
    kind: str
    title: str
    channel_id: str | None
    folder_id: str | None
    created_at: datetime
    last_activity_at: datetime
    status: Literal["pending_review", "published", "no_revision"]
    pending_proposal_count: int
    latest_revision: LatestRevisionResponse | None
    owners: list[OwnerResponse]
    is_favorite: bool


class ArtifactListResponse(BaseModel):
    """문서 목록 한 쪽과 필터 뒤 전체 수를 담는다.

    total은 limit·offset을 걸기 전의 수다. 소비자가 쪽 수를 계산하려면 이
    쪽에 실린 개수가 아니라 필터 뒤 전체 수를 알아야 한다.
    """

    items: list[ArtifactListItemResponse]
    total: int
    limit: int
    offset: int


class ArtifactMoveRequest(BaseModel):
    """문서를 옮길 폴더를 담는다.

    folder_id가 None이면 채널 루트로 올린다. 채널은 여기서 바꾸지 않는다.
    채널 이동은 정의·담당자·관리자 판정이 함께 따라와야 하는 조작이라,
    폴더 이동과 같은 문에 두지 않는다.

    키는 필수이고 값만 null을 받는다. 기본값을 두면 키를 빠뜨린 요청이
    "루트로 올려라"로 읽혀, 오타 하나가 조용히 문서를 옮긴다.
    """

    model_config = ConfigDict(extra="forbid")

    folder_id: uuid.UUID | None


class ArtifactLocationResponse(BaseModel):
    """문서가 지금 놓인 자리를 담는다."""

    artifact_id: str
    channel_id: str | None
    folder_id: str | None


class FavoriteItemResponse(BaseModel):
    """즐겨찾기 목록 한 줄을 담는다."""

    artifact_id: str
    title: str
    kind: str
    channel_id: str | None
    folder_id: str | None
    favorited_at: datetime


class FavoriteListResponse(BaseModel):
    """즐겨찾기 목록 전체를 담는다."""

    items: list[FavoriteItemResponse]


class FavoriteResponse(BaseModel):
    """즐겨찾기 지정 결과를 담는다.

    지정은 멱등이라 응답 코드만으로는 지금 상태를 알 수 없다. 결과 상태를
    같이 실어 소비자가 응답 하나로 화면을 정하게 한다.
    """

    artifact_id: str
    is_favorite: bool
