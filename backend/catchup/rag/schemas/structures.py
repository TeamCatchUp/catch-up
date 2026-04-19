from datetime import datetime
from typing import Literal

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


# Supervisor가 결정하는 파이프라인 실행 계획
class PipelinePlan(BaseModel):
    pipeline_type: Literal["chitchat", "reuse", "simple", "standard", "complex", "clarify"] = Field(
        description="실행할 파이프라인 타입"
    )
    max_iterations: int = Field(
        default=3,
        description="ReAct 루프 최대 반복 횟수. simple=0, standard=3, complex=7"
    )
    clarification_question: str | None = Field(
        default=None,
        description=(
            "clarify 타입일 때만 채운다. "
            "사용자에게 보낼 명확화 질문 (사용자 언어와 동일한 언어로 작성)."
        ),
    )


# Complex 파이프라인 planner가 생성하는 검색 단계
class SearchStep(BaseModel):
    step: int = Field(description="실행 순서")
    intent: str = Field(description="이 단계에서 찾으려는 정보의 의도")
    queries: list[str] = Field(description="실행할 검색 쿼리 목록")
    parallel: bool = Field(
        default=False,
        description="True면 queries를 병렬 실행 (multi_query_search 사용)"
    )
    depends_on: list[int] = Field(
        default=[],
        description="이 단계를 실행하기 전에 완료되어야 하는 선행 step 번호 목록"
    )


# Complex 파이프라인 gap_analysis_node의 분석 결과
class GapAnalysis(BaseModel):
    is_sufficient: bool = Field(
        description="현재까지 수집된 정보가 질문에 답하기 충분한지 여부"
    )
    gaps: list[str] = Field(
        default=[],
        description="부족한 정보 목록"
    )
    suggested_queries: list[str] = Field(
        default=[],
        description="gap을 메우기 위한 추가 검색 쿼리 제안"
    )
    reasoning: str = Field(
        default="",
        description="분석 근거 (extended thinking 결과 요약)"
    )


# Complex planner LLM 응답 스키마
class SearchPlan(BaseModel):
    steps: list[SearchStep] = Field(
        default=[],
        description="순서대로 실행할 검색 단계 목록"
    )


# 검색 결과에 대한 평가 담당 LLM 응답 양식
class GradeDocuments(BaseModel):
    binary_score: str = Field(
        description="문서들이 질문에 답변하는 데 유용한지 여부. 'yes' 또는 'no'"
    )
    explanation: str = Field(
        description="이 점수를 부여한 이유에 대한 간략한 설명 (예: '문서에 관련 키워드는 있으나 구체적인 해결책이 없음')"
    )
