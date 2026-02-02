# 채팅 요청
import uuid
from typing import Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    query: str = Field(..., description="사용자 질문")
    role: Optional[str] = Field(
        default="user", description="사용자 역할"
    )  # TODO: 추후 RBAC 혹은 페르소나에 사용 (논의 필요)
    session_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()), description="대화 세션 ID"
    )
    index_list: list[str] = Field(description="검색 대상 인덱스 리스트")
