from typing import Literal, Optional

from pydantic import BaseModel, Field


class SearchQuery(BaseModel):
    datasource: Literal["codebase", "github_issue", "pr_history", "jira_issue"] = Field(
        ..., description="검색할 데이터 소스 유형 선택"
    )
    query: str = Field(..., description="검색어")


class SearchPlan(BaseModel):
    queries: list[SearchQuery] = Field(
        ..., description="질문을 해결하기 위해 수행해야 할 모든 검색 쿼리의 목록"
    )
