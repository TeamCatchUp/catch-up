from typing import Literal

from pydantic import BaseModel, Field


# 정보 검색이 필요한지, 일상 대화인지 여부에 대한 쿼리 라우터
class RouteQuery(BaseModel):
    datasource: Literal["chitchat", "search_pipeline"] = Field(
        ...,
        description=(
            "질문의 성격에 따라 다음 단계로 라우팅합니다:\n"
            "1. 'chitchat': 단순 인사, 날씨, 안부, 자기소개 등 검색이 필요 없는 일상 대화.\n"
            "2. 'search_pipeline': 코드, 버그, 지라(Jira), Pull Request, 기능 구현, 에러 원인 분석 등 "
            "소프트웨어 개발 프로젝트와 관련된 모든 기술적인 질문"
        )
    )
