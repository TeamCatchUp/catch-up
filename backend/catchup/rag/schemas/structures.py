from enum import StrEnum
from typing import Literal, Optional

from pydantic import BaseModel, Field

from catchup.search.schemas import (
    PullRequestSearchResult,
)


class PullRequestCandidate(BaseModel):
    id: int = Field(default="", description="pr_number")
    pr_number: int = Field(default=0)
    title: str = Field(default="")
    repo: str = Field(default="")
    summary: str = Field(default="")
    owner: str = Field(default="")
    created_at: int = Field(default=0)

    @classmethod
    def from_search_result_doc(
        cls, res: PullRequestSearchResult
    ) -> "PullRequestCandidate":
        return cls(
            id=res.id,
            pr_number=res.pr_number,
            title=res.title,
            repo=res.repo,
            summary=res.body[:100] if res.body else "",
            owner=res.owner,
            created_at=res.created_at,
        )


class PullRequestUserSelected(BaseModel):
    pr_number: int = Field(default=0)
    repo: str = Field(default="")
    owner: str = Field(default="")


# Search Plan
class BaseSearchQuery(BaseModel):
    reasoning: Optional[str] = Field(default="", description="이 검색이 필요한 이유")


class VectorDbSearchQuery(BaseSearchQuery):
    query: str = Field(..., description="Vector 검색 엔진에 전달할 최적화된 검색어")


class VectorDbSearchPlan(BaseModel):
    queries: list[VectorDbSearchQuery] = Field(
        default=[],
        min_items=0,
        max_items=3,
        description="사용자의 의도를 분석하여 생성된 독립적인 검색 쿼리 목록",
    )


class GraphDbSearchQuery(BaseSearchQuery):
    cypher: str = Field(..., description="Graph DB에 검색할 최적화된 Cypher")


class GraphDbSearchPlan(BaseModel):
    cyphers: list[GraphDbSearchQuery] = Field(
        default=[],
        min_items=0,
        max_items=3,
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


# 정보 검색이 필요한지, 일상 대화인지 여부에 대한 쿼리 라우터
class RouteQuery(BaseModel):
    intent: Literal["chitchat", "search_pipeline"] = Field(
        ...,
        description=(
            "질문의 성격에 따라 다음 단계로 라우팅합니다:\n"
            "1. 'chitchat': 단순 인사, 날씨, 안부, 자기소개 등 검색이 필요 없는 일상 대화.\n"
            "2. 'search_pipeline': 코드, 버그, 지라(Jira), Pull Request, 기능 구현, 에러 원인 분석 등 "
            "소프트웨어 개발 프로젝트와 관련된 모든 기술적인 질문"
        ),
    )
