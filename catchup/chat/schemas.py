import uuid
from typing import Annotated, Any, Literal, Optional, Union

from pydantic import BaseModel, Field

from catchup.rag.schemas import JiraSource, PullRequestUserSelected, SourceResponse


class ChatRequest(BaseModel):
    query: str = Field(..., description="사용자 질문")
    role: Optional[str] = Field(
        default="user", description="사용자 역할"
    )  # TODO: 추후 RBAC 혹은 페르소나에 사용 (논의 필요)
    session_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()), description="대화 세션 ID"
    )
    index_list: list[str] = Field(description="검색 대상 인덱스 리스트")


class ChatStreamingResumeRequest(BaseModel):
    session_id: str = Field(..., description="PR 수동 선택 후 재개할 세션 ID")
    user_selected_pull_requests: list[PullRequestUserSelected] = Field(
        ..., description="사용자가 선택한 PR 번호 리스트"
    )


class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceResponse] = []
    process_time: float


class ChatStreamingResponse(BaseModel):
    type: Literal["status"] = "status"
    session_id: str
    node: str
    message: str


class ChatStreamingFinalResponse(BaseModel):
    type: Literal["result"] = "result"
    session_id: str
    node: str
    answer: str
    sources: list[SourceResponse] = []
    related_jira_issues: list[JiraSource] = []
    process_time: float


class ChatStreamingInterruptResponse(BaseModel):
    type: Literal["interrupt"] = "interrupt"
    session_id: str
    node: str
    payload: Any


class ChatStreamingKeepAliveResponse(BaseModel):
    type: Literal["ping"] = "ping"
    session_id: str


StreamEvent = Annotated[
    Union[
        ChatStreamingResponse,
        ChatStreamingFinalResponse,
        ChatStreamingInterruptResponse,
        ChatStreamingKeepAliveResponse,
    ],
    Field(discriminator="type"),
]
