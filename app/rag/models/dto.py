import uuid
from typing import List

from pydantic import BaseModel, Field


# 요청
class ChatRequest(BaseModel):
    query: str = Field(..., description="사용자 질문")
    role: str = Field(default="user", description="사용자 역할")
    session_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()), description="대화 세션 ID"
    )


class Source(BaseModel):
    source: str | None = None  # 문서 출처
    category: str | None = None  # 카테고리
    page: int | None = None
    content: str | None = None  # 실제 내용
    file_path: str | None = None
    file_name: str | None = None


# 응답
class ChatResponse(BaseModel):
    answer: str = Field(..., description="AI의 답변 텍스트")
    sources: List[Source] = Field(default=[], description="참고한 문서 출처 목록")
