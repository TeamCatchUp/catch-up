# TODO: 협의 필요

"""
노드 간 경계를 흐르는 공유 데이터 타입.

각 노드의 OutputModel과 다음 노드의 InputModel이 이 타입을 참조함으로써
compile_workflow()가 연결 가능 여부를 타입 수준에서 검증할 수 있다.
"""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel
from pydantic import Field


# 메시지 / 대화
class ChatMessage(BaseModel):
    """노드 간에 전달되는 단일 대화 메시지. InvokeLlm의 입력 단위."""
    role: Literal["system", "human", "ai"]
    content: str


# 외부 시스템 수신 메시지 (Connector → 다음 노드)
class IncomingMessage(BaseModel):
    """외부 시스템(채널톡, Slack 등)에서 수신한 메시지.

    Connector의 receive/subscribe 류 액션이 공통으로 반환하는 타입.
    다음 노드(검색, LLM 등)가 이 타입을 input으로 받아 처리한다.
    """
    id: str = Field(description="외부 시스템의 메시지 고유 ID.")
    content: str = Field(description="메시지 본문.")
    author: str | None = Field(default=None, description="발신자 ID 또는 이름.")
    channel_id: str = Field(description="메시지가 수신된 채널 ID.")
    created_at: datetime = Field(description="메시지 수신 시각.")
    source: str = Field(description="메시지 출처 시스템. 예: 'channel_talk', 'slack'.")
    metadata: dict = Field(default_factory=dict, description="시스템별 추가 필드.")


# 지식베이스 검색 결과 (SearchKnowledgeBase → InvokeLlm)
class DocumentChunk(BaseModel):
    """지식베이스에서 검색된 단일 문서 청크."""
    id: str = Field(description="청크 고유 ID.")
    content: str = Field(description="청크 본문.")
    title: str | None = Field(default=None, description="원본 문서 제목.")
    source: str = Field(description="출처 시스템. 예: 'confluence', 'github', 'slack'.")
    url: str | None = Field(default=None, description="원본 문서 URL.")
    score: float = Field(description="검색 유사도 점수 (0~1).")


class SearchResults(BaseModel):
    """SearchKnowledgeBase 노드의 검색 결과."""
    query: str = Field(description="검색에 사용된 쿼리.")
    items: list[DocumentChunk] = Field(description="유사도 순으로 정렬된 검색 결과 목록.")
    total: int = Field(description="전체 검색 결과 수.")


# LLM 응답 (InvokeLlm → 다음 노드)
class LlmResponse(BaseModel):
    """InvokeLlm 노드의 출력. 텍스트 응답과 토큰 사용량을 포함한다."""
    content: str = Field(description="LLM 응답 텍스트.")
    usage_metadata: dict | None = Field(
        default=None,
        description="토큰 사용량 정보.",
    )
