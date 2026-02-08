import uuid
from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, Field

from catchup.rag.schemas import SourceResponse


NODE_STATUS_MAP = {
    "route": "질문의 성격을 분석하고 있습니다...",
    "rewrite": "검색 정확도를 높이기 위해 질문을 최적화하고 있습니다...",
    "generate_vector_queries": "최적의 검색 쿼리를 생성하고 있습니다...",
    "search_vector_db": "지식 저장소(Vector DB)에서 문서를 검색 중입니다...",
    "rerank": "검색된 문서들의 관련성을 분석하여 우선순위를 정하고 있습니다...",
    "grade": "검색 결과가 충분한지 검토하고 있습니다...",
    "expand_graph_context": "지식 그래프를 통해 연관된 정보를 확장 탐색 중입니다...",
    "fetch_details_after_graph_context_expansion": "확장된 정보의 상세 내용을 불러오고 있습니다...",
    "fallback_cypher_query": "추가적인 그래프 질의(Cypher)를 실행하여 정보를 보완 중입니다...",
    "generate_final_answer": "모든 정보를 종합하여 최종 답변을 작성하고 있습니다...",
    "chitchat": "답변을 생성하고 있습니다...",
}


class ChatRequest(BaseModel):
    query: str = Field(..., description="사용자 질문")
    role: Optional[str] = Field(
        default="user", description="사용자 역할"
    )  # TODO: 추후 RBAC 혹은 페르소나에 사용 (논의 필요)
    session_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()), description="대화 세션 ID"
    )


class ChatResponse(BaseModel):
    """일반 채팅 응답"""

    answer: str
    sources: list[SourceResponse] = []
    process_time: float


class ChatStreamingStatusResponse(BaseModel):
    """답변 생성 단계 스트리밍"""

    type: Literal["status"] = "status"
    session_id: str
    node: str
    message: str


class ChatStreamingSourceResponse(BaseModel):
    """출처 정보 전송 (답변 생성 전 먼저 전송)"""

    type: Literal["sources"] = "sources"
    session_id: str
    # sources: list[SourceResponse]  TODO: 주석 해제
    sources: Optional[list]


class ChatStreamingTokenResponse(BaseModel):
    type: Literal["token"] = "token"
    session_id: str
    token: str


StreamEvent = Annotated[
    Union[
        ChatStreamingStatusResponse,
        ChatStreamingSourceResponse,
        ChatStreamingTokenResponse,
    ],
    Field(discriminator="type"),
]

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
