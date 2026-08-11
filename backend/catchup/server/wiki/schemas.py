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

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field


class ChannelCreateRequest(BaseModel):
    """채널 생성 요청을 담는다."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)


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
