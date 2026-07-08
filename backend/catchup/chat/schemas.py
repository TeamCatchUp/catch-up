import uuid
from datetime import datetime
from typing import Annotated
from typing import Any
from typing import Literal
from typing import Optional
from typing import Union

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import field_validator

from catchup.db.models import FeedbackLiteral
from catchup.db.models import SenderType
from catchup.db.models import SourceType
from catchup.db.models import UserRole
from catchup.schemas.sources import SourceResponse

# stream processor가 on_chain_start 시점에 in_progress 이벤트를 발행할 노드 목록.
# 이 목록에 없는 노드는 자신이 직접 adispatch_custom_event로 lifecycle을 관리한다.
INPROGRESS_NODES: frozenset[str] = frozenset({
    "clarify",
    "direct_answer",
    "generate_final_answer",
    "generate_final_answer_fast",
    "rerank",
    "rewrite",
    "search_vector_db",
})


class ChatRequest(BaseModel):
    query: str = Field(..., description="사용자 질문")
    role: Optional[str] = Field(default=UserRole.USER, description="사용자 역할 (admin 또는 user)")
    session_id: uuid.UUID = Field(default_factory=uuid.uuid4, description="대화 세션 ID")
    tool_filters: list[SourceType] = Field(default_factory=list, description="협업 툴 검색 필터")
    mode: Literal["fast", "standard"] = Field(default="standard", description="응답 모드 (default: standard)")
    
    @field_validator('tool_filters', mode='before')
    @classmethod
    def validate_tool_filters(cls, v):
        if v is None:
            return []
        return v


class ChatResponse(BaseModel):
    """일반 채팅 응답"""

    answer: str
    sources: list[SourceResponse] = []
    process_time: float


class ChatStreamingSourceResponse(BaseModel):
    """출처 정보 전송 (답변 생성 전 먼저 전송)"""

    type: Literal["sources"] = "sources"
    session_id: uuid.UUID = Field(default_factory=uuid.uuid4, description="대화 세션 ID")
    sources: Optional[list[SourceResponse]]


class ChatStreamingTokenResponse(BaseModel):
    type: Literal["token"] = "token"
    session_id: uuid.UUID = Field(default_factory=uuid.uuid4, description="대화 세션 ID")
    token: str


class ChatStreamingProcessResponse(BaseModel):
    """답변 생성 과정(에이전트 사고 과정 포함) 스트리밍"""

    type: Literal["process"] = "process"
    session_id: uuid.UUID = Field(default_factory=uuid.uuid4, description="대화 세션 ID")
    status: Literal["in_progress", "completed", "error"]
    node: str
    reasoning: str | None = None
    content: dict[str, Any] | None = None


StreamEvent = Annotated[
    Union[
        ChatStreamingSourceResponse,
        ChatStreamingTokenResponse,
        ChatStreamingProcessResponse,
    ],
    Field(discriminator="type"),
]


class ChatGenerationStatusResponse(BaseModel):
    """답변 생성 진행 여부와 재연결 시 배치/실시간 렌더링 경계를 담는다."""

    is_generating: bool = Field(..., description="현재 답변 생성이 진행 중인지 여부")
    cutoff_id: str | None = Field(
        default=None,
        description=(
            "생성 중일 때만 값이 있음. 이 ID 이하의 이벤트는 재연결 이전에 이미 생성된 "
            "것이므로 프론트는 애니메이션 없이 일괄 렌더링하고, 이 ID 초과 이벤트만 "
            "실시간 애니메이션을 적용해야 한다."
        ),
    )

# --- [Human In The Loop] ---
# class ChatStreamingResumeRequest(BaseModel):
#     session_id: str = Field(..., description="PR 수동 선택 후 재개할 세션 ID")
#     user_selected_pull_requests: list[PullRequestUserSelected] = Field(
#         ..., description="사용자가 선택한 PR 번호 리스트"
#     )

# class ChatStreamingInterruptResponse(BaseModel):
#     type: Literal["interrupt"] = "interrupt"
#     session_id: str
#     node: str
#     payload: Any


# 채팅방 목록
class ChatRoomResponse(BaseModel):
    session_id: uuid.UUID = Field(default_factory=uuid.uuid4, description="대화 세션 ID")
    title: str = Field(..., description="채팅방 이름")
    created_at: datetime = Field(..., description="생성 시각")
    updated_at: datetime = Field(..., description="최근 활동 시각")
    
    model_config = ConfigDict(from_attributes=True)
    
# 채팅 메시지 히스토리
class ChatHistoryResponse(BaseModel):
    id: int = Field(..., description="메시지 고유 ID")
    sender_type: SenderType = Field(..., description="sender 유형 (user/assistant)")
    content: str = Field(..., description="메시지 내용")
    created_at: datetime = Field(..., description="메시지 생성 시각")
    sources: Optional[list[SourceResponse]] = Field(default_factory=list, description="출처 목록 (sender_type='assistant'인 경우에만 존재)")
    is_liked: Optional[bool] = Field(default=None, description="답변 평가 여부 (True: 긍정, False: 부정, None: 없음)")
    is_saved: bool = Field(default=False, description="사용자의 답변 저장 여부")
    pipeline_result: list[dict] | None = Field(
        default=None,
        description="RAG 파이프라인 노드별 status 이벤트 (sender_type='assistant'인 경우에만 존재)"
    )

    model_config = ConfigDict(from_attributes=True)
    
# 사용자 쿼리 정보
class UserQueryResponse(BaseModel):
    id: int = Field(..., description="메시지 고유 ID")
    session_id: uuid.UUID = Field(..., description="사용자 쿼리가 속한 채팅방 세션 ID")
    content: str = Field(..., description="메시지 내용")
    created_at: datetime = Field(..., description="메시지 생성 시각")

    model_config = ConfigDict(from_attributes=True)


class UserQueryWithSaveStatusResponse(UserQueryResponse):    
    is_answer_saved: bool = Field(
        default=False, 
        description="이 질문에 대한 AI 답변이 저장되었는지 여부"
    )
    answer_id: Optional[int] = Field(
        default=None, 
        description="토글(저장/해제) 시 타겟이 될 AI 답변의 메시지 ID"
    )

    model_config = ConfigDict(from_attributes=True)


class FeedbackRequest(BaseModel):
    is_liked: Optional[bool] = Field(default=None, description="사용자 긍정/부정 피드백")
    reasons: Optional[list[FeedbackLiteral]] = Field(default_factory=list, description="부정 피드백 사유 목록")
    comment: Optional[str] = Field(default=None, description="사용자가 직접 작성한 상세 피드백")
    