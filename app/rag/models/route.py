from typing import Literal

from pydantic import BaseModel, Field


# 정보 검색이 필요한지, 일상 대화인지 여부에 대한 쿼리 라우터
class RouteQuery(BaseModel):
    datasource: Literal["chitchat", "codebase", "issue_tracker", "pr_history"] = Field(
        ...,
        description="질문의 성격에 따라 적절한 데이터 소스를 선택하세요. "
        "코드 구현/문법 질문은 'codebase', "
        "버그/기능요청/히스토리 질문은 'issue_tracker', "
        "코드 변경 내역 질문은 'pr_history', "
        "일상 대화는 'chitchat'입니다.",
    )
