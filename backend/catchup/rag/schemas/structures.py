from datetime import datetime

from pydantic import BaseModel
from pydantic import Field


# Search Plan
class BaseSearchQuery(BaseModel):
    reasoning: str = Field(default="", description="이 검색이 필요한 이유")
    start_date: datetime | None = Field(
        None,
        description="""
        Vector 검색 대상 문서의 발생(생성/수정) 기준 시작일.
        반드시 'YYYY-MM-DDTHH:MM:SS' 형식의 ISO 8601 포맷으로 작성할 것.
        (시간 특정 불가 시 null)
        """
    )
    end_date: datetime | None = Field(
        None,
        description="""
        Vector 검색 대상 문서의 발생(생성/수정) 기준 종료일.
        반드시 'YYYY-MM-DDTHH:MM:SS' 형식의 ISO 8601 포맷으로 작성할 것.
        (시간 특정 불가 시 null)
        """
    )


class VectorDbSearchQuery(BaseSearchQuery):
    query: str = Field(..., description="Vector 검색 엔진에 전달할 최적화된 검색어")


class VectorDbSearchPlan(BaseModel):
    queries: list[VectorDbSearchQuery] = Field(
        default=[],
        min_length=0,
        max_length=3,
        description="사용자의 의도를 분석하여 생성된 독립적인 검색 쿼리 목록",
    )


class GraphDbSearchQuery(BaseSearchQuery):
    cypher: str = Field(..., description="Graph DB에 검색할 최적화된 Cypher")


class GraphDbSearchPlan(BaseModel):
    cyphers: list[GraphDbSearchQuery] = Field(
        default=[],
        min_length=0,
        max_length=3,
        description="사용자의 의도를 분석하여 생성된 독립적인 Cypher 목록",
    )


# 검색 결과에 대한 평가 담당 LLM 응답 양식
class GradeDocuments(BaseModel):
    binary_score: str = Field(
        description="문서들이 질문에 답변하는 데 유용한지 여부. 'yes' 또는 'no'"
    )
    explanation: str = Field(
        description="이 점수를 부여한 이유에 대한 간략한 설명 (예: '문서에 관련 키워드는 있으나 구체적인 해결책이 없음')"
    )
