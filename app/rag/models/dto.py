import uuid
from typing import Annotated, Any, Literal, Optional, Union

from pydantic import BaseModel, Field

from app.rag.models.retrieve import (
    BaseSearchResult,
    CodeSearchResult,
    PullRequestSearchResult,
    JiraIssueSearchResult,
    SourceType
)
from app.rag.models.manage_pr_context import PullRequestUserSelected

# 각 Source별 필수 필드 정의
class BaseSource(BaseModel):
    index: int | None  # LLM이 참고한 문서 번호
    is_cited: bool = Field(default=False, description="LLM 인용 여부")
    source_type: SourceType = Field(..., description="소스 종류 구분")
    owner: str = Field(..., description="레포지토리 소유자")
    repo: str = Field(..., description="레포지토리 이름")
    relevance_score: float = Field(..., description="사용자 쿼리와 출처의 관련 정도")
    html_url: str | None = Field(None, description="Github 원본 링크")
    text: str | None = Field(None, description="프론트엔드 표시용 본문 텍스트")
    
    @classmethod
    def from_search_result(
        cls,
        index: int,
        doc: BaseSearchResult,
        is_cited: bool = False
    ) -> "SourceResponse":
        """BaseSearchResult -> SourceResponse 변환"""
        base_data = {
            "index": index,
            "is_cited": is_cited,
            "source_type": doc.source_type,
            "owner": doc.owner,
            "repo": doc.repo,
            "relevance_score": doc.relevance_score or 0.0,
            "html_url": doc.html_url,
            "text": doc.text or getattr(doc, "body", "")
        }
        
        if doc.source_type == SourceType.CODE:
            if isinstance(doc, CodeSearchResult):
                return CodeSource(
                    **base_data,
                    file_path=doc.file_path,
                    category=doc.category,
                    language=doc.language
                )
        
        elif doc.source_type == SourceType.PULL_REQUEST:
            if isinstance(doc, PullRequestSearchResult):
                return PullRequestSource(
                    **base_data,
                    title=doc.title,
                    pr_number=doc.pr_number,
                    state=doc.state,
                    created_at=doc.created_at,
                    author=doc.author
                )
        
        elif doc.source_type == SourceType.ISSUE:
            pass
        
        elif doc.source_type == SourceType.JIRA_ISSUE:
            if isinstance(doc, JiraIssueSearchResult):
                return JiraSource(
                    **base_data,
                    issue_type_name=doc.issue_type_name,
                    summary=doc.summary,
                    project_name=doc.project_name,
                    issue_key=str(doc.id),
                    parent_key=doc.parent_key,
                    parent_summary=doc.parent_summary,
                    status_id=doc.status_id,
                    assignee_name=doc.assignee_name
                )

# 코드 메타데이터
class CodeSource(BaseSource):
    source_type: Literal[SourceType.CODE] = SourceType.CODE
    file_path: str | None = None  # 파일 경로
    category: str | None = None  # 카테고리
    language: str | None = None  # 프로그래밍 언어
    
# PR 메타데이터
class PullRequestSource(BaseSource):
    source_type: Literal[SourceType.PULL_REQUEST] = SourceType.PULL_REQUEST
    title: str = Field(..., description="PR 제목")
    pr_number: int = Field(..., description="PR 번호")
    state: str = Field(..., description="PR 상태")
    created_at: int = Field(..., description="생성일")
    author: str = Field(..., description="작성자")

# Jira 이슈 메타데이터
class JiraSource(BaseSource):
    source_type: Literal[SourceType.JIRA_ISSUE] = SourceType.JIRA_ISSUE
    issue_type_name: str = Field(..., description="이슈 타입 이름 (Story, Epic, ...)")
    summary: str = Field(..., description="이슈 제목")
    project_name: str = Field(..., description="프로젝트 명")
    issue_key: str = Field(..., description="이슈 키 (id)")
    
    # UI 계층 표현을 위한 필드
    parent_key: str | None = Field(None, description="부모 키")
    parent_summary: str | None = Field(None, description="부모 제목")
    
    # 기타 메타데이터
    status_id: int | None = None
    assignee_name: str | None = None


SourceResponse = Annotated[
    Union[CodeSource, PullRequestSource, JiraSource],
    Field(discriminator="source_type")
]


# 채팅 요청
class ChatRequest(BaseModel):
    query: str = Field(..., description="사용자 질문")
    role: Optional[str] = Field(
        default="user", description="사용자 역할"
    )  # TODO: 추후 RBAC 혹은 페르소나에 사용 (논의 필요)
    session_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()), description="대화 세션 ID"
    )
    index_list: list[str] = Field(description="검색 대상 인덱스 리스트")


# 최종 채팅 응답
class ChatResponse(BaseModel):
    answer: str = Field(..., description="AI의 답변 텍스트")
    sources: list[SourceResponse] = Field(
        default_factory=list, description="참고한 문서 출처 목록"
    )
    process_time: float = Field(..., description="답변 생성 시간")


# (Streaming) 중간 과정 응답
class ChatStreamingResponse(BaseModel):
    session_id: str = Field(..., description="PR 수동 선택 후 재개할 세션 ID")
    type: str = Field(..., description="payload 유형")
    node: str = Field(..., description="실행 중인 노드 이름")
    message: str = Field(..., description="payload")
    
# (Streaming) 인터럽트 Server -> Client 
class ChatStreamingInterruptResponse(BaseModel):
    session_id: str = Field(..., description="PR 수동 선택 후 재개할 세션 ID")
    type: Literal["interrupt"] = Field(default="interrupt", description="HITL 인터럽트")
    node: str = Field(..., description="중단된 노드 이름")
    payload: Any = Field(..., description="인터럽트 데이터 (PR 후보 리스트)")

# (Streaming) 인터럽트 Client -> Server
class ChatStreamingResumeRequest(BaseModel):
    session_id: str = Field(..., description="PR 수동 선택 후 재개할 세션 ID")
    user_selected_pull_requests: list[PullRequestUserSelected] = Field(..., description="사용자가 선택한 PR 번호 리스트")
    

# (Streaming) Keep-alive Ping
class ChatStreamingKeepAliveResponse(BaseModel):
    session_id: str = Field(..., description="PR 수동 선택 후 재개할 세션 ID")
    type: Literal["ping"] = Field(..., description="Keep-Alive 핑")


# (Streaming) 최종 채팅 응답
class ChatStreamingFinalResponse(ChatResponse):
    session_id: str = Field(..., description="PR 수동 선택 후 재개할 세션 ID")
    type: Literal["result"] = Field(..., description="최종 payload 유형")
    node: Literal["generate", "chitchat"] = Field(
        ..., description="최종 답변 생성 노드 이름"
    )
    related_jira_issues: list[JiraSource] = Field(
        default_factory=list, description="사용자 쿼리와 관련 있는 Jira 티켓 목록"
    )
