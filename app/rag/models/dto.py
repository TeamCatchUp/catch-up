import uuid
from typing import Optional, Literal, Annotated, Union, Any

from pydantic import BaseModel, Field


# 각 Source별 필수 필드 정의
class BaseSource(BaseModel):
    index: int | None # LLM이 참고한 문서 번호
    is_cited: bool = Field(default=False, description="LLM 인용 여부")
    source_type: str = Field(..., description="소스 종류 구분") # TODO: 세분화
    text: str | None = Field(None, description="본문 내용")
    relevance_score: float = Field(..., description="사용자 쿼리와 출처의 관련 정도")

# Github 코드 메타데이터
class GithubSource(BaseSource):
    source_type: Literal["github"] = "github"
    file_path: str | None = None # 파일 경로
    category: str | None = None  # 카테고리
    source: str | None = None  # 문서 출처
    html_url: str | None = None # Github 소스코드 url
    language: str | None = None # 프로그래밍 언어


Source = Annotated[
    Union[GithubSource],
    Field(discriminator="source_type")
]


# 채팅 요청
class ChatRequest(BaseModel):
    query: str = Field(..., description="사용자 질문")
    role: Optional[str] = Field(default="user", description="사용자 역할") # TODO: 추후 RBAC 혹은 페르소나에 사용 (논의 필요)
    session_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()), description="대화 세션 ID"
    )
    index_name: str = Field(description="검색 대상 인덱스")


# 채팅 응답
class ChatResponse(BaseModel):
    answer: str = Field(..., description="AI의 답변 텍스트")
    sources: list[Source] = Field(default_factory=list, description="참고한 문서 출처 목록")
    process_time: float = Field(..., description="답변 생성 시간")
