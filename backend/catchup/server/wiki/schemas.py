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

from datetime import datetime

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
    않는다 — raw spec 입구가 열리면 카탈로그가 규칙의 유일한 출처라는
    약속이 깨진다.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=20)
    purpose_preset: str
    style_preset: str
    kind: str


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


class ChannelOnboardingResponse(BaseModel):
    """만들어진 채널·정의와 어휘 발행 결과를 담는다.

    vocabulary_version이 None이면 더할 어휘가 없어 발행을 건너뛴 것이다.
    같은 도메인으로 두 번째 채널을 만든 자리가 그렇다.
    """

    channel: ChannelResponse
    definition_id: str
    kind: str
    purpose_preset: str
    style_preset: str
    vocabulary_version: str | None


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


class ChannelListResponse(BaseModel):
    """채널 목록 전체를 담는다."""

    channels: list[ChannelListItemResponse]


class ArtifactOwnerResponse(BaseModel):
    """문서 담당자 한 명의 지정 결과를 담는다.

    담당자 명단 전체를 싣는다. 지정은 멱등이라 응답 코드만으로는 "지금
    누가 담당인가"를 알 수 없는데, 그 답을 위해 목록을 한 번 더 왕복하면
    두 응답 사이에서 명단이 갈린다.
    """

    artifact_id: str
    user_ids: list[int]


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
