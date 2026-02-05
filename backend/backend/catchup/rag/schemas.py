from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field

from catchup.search.schemas import (
    BaseSearchResult,
    CodeSearchResult,
    JiraIssueSearchResult,
    PullRequestSearchResult,
    SourceType,
)


# 각 Source별 필수 필드 정의
class BaseSource(BaseModel):
    index: int | None  # LLM이 참고한 문서 번호
    is_cited: bool = Field(default=False, description="LLM 인용 여부")
    source_type: SourceType = Field(..., description="소스 종류 구분")
    owner: str = Field(..., description="레포지토리 소유자")
    repo: str = Field(..., description="레포지토리 이름")
    relevance_score: float = Field(..., description="사용자 쿼리와 출처의 관련 정도")
    html_url: str | None = Field(None, description="Github 원본 링크")
    text: str | None = Field(None, description="프론트엔드 표시용 본문 텍스트")

    @classmethod
    def from_search_result(
        cls, index: int, doc: BaseSearchResult, is_cited: bool = False
    ) -> "SourceResponse":
        """BaseSearchResult -> SourceResponse 변환"""
        base_data = {
            "index": index,
            "is_cited": is_cited,
            "source_type": doc.source_type,
            "owner": doc.owner,
            "repo": doc.repo,
            "relevance_score": doc.relevance_score or 0.0,
            "html_url": doc.html_url,
            "text": doc.text or getattr(doc, "body", ""),
        }

        if doc.source_type == SourceType.CODE:
            if isinstance(doc, CodeSearchResult):
                return CodeSource(
                    **base_data,
                    file_path=doc.file_path,
                    category=doc.category,
                    language=doc.language,
                )

        elif doc.source_type == SourceType.PULL_REQUEST:
            if isinstance(doc, PullRequestSearchResult):
                return PullRequestSource(
                    **base_data,
                    title=doc.title,
                    pr_number=doc.pr_number,
                    state=doc.state,
                    created_at=doc.created_at,
                    author=doc.author,
                )

        elif doc.source_type == SourceType.ISSUE:
            pass

        elif doc.source_type == SourceType.JIRA_ISSUE:
            if isinstance(doc, JiraIssueSearchResult):
                return JiraSource(
                    **base_data,
                    issue_type_name=doc.issue_type_name,
                    summary=doc.summary,
                    project_name=doc.project_name,
                    issue_key=str(doc.id),
                    parent_key=doc.parent_key,
                    parent_summary=doc.parent_summary,
                    status_id=doc.status_id,
                    assignee_name=doc.assignee_name,
                )


# 코드 메타데이터
class CodeSource(BaseSource):
    source_type: Literal[SourceType.CODE] = SourceType.CODE
    file_path: str | None = None  # 파일 경로
    category: str | None = None  # 카테고리
    language: str | None = None  # 프로그래밍 언어


# PR 메타데이터
class PullRequestSource(BaseSource):
    source_type: Literal[SourceType.PULL_REQUEST] = SourceType.PULL_REQUEST
    title: str = Field(..., description="PR 제목")
    pr_number: int = Field(..., description="PR 번호")
    state: str = Field(..., description="PR 상태")
    created_at: int = Field(..., description="생성일")
    author: str = Field(..., description="작성자")


# Jira 이슈 메타데이터
class JiraSource(BaseSource):
    source_type: Literal[SourceType.JIRA_ISSUE] = SourceType.JIRA_ISSUE
    issue_type_name: str = Field(..., description="이슈 타입 이름 (Story, Epic, ...)")
    summary: str = Field(..., description="이슈 제목")
    project_name: str = Field(..., description="프로젝트 명")
    issue_key: str = Field(..., description="이슈 키 (id)")

    # UI 계층 표현을 위한 필드
    parent_key: str | None = Field(None, description="부모 키")
    parent_summary: str | None = Field(None, description="부모 제목")

    # 기타 메타데이터
    status_id: int | None = None
    assignee_name: str | None = None


SourceResponse = Annotated[
    Union[CodeSource, PullRequestSource, JiraSource], Field(discriminator="source_type")
]


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


class SearchQuery(BaseModel):
    datasource: Literal["codebase", "github_issue", "pr_history", "jira_issue"] = Field(
        ..., description="검색할 데이터 소스 유형 선택"
    )
    query: str = Field(..., description="검색어")


class SearchPlan(BaseModel):
    queries: list[SearchQuery] = Field(
        ..., description="질문을 해결하기 위해 수행해야 할 모든 검색 쿼리의 목록"
    )


# 검색 결과에 대한 평가 담당 LLM 응답 양식
class GradeDocuments(BaseModel):
    binary_score: str = Field(
        description="Relevance score: 'yes' if relevant, or 'no' if not relevant"
    )


# 정보 검색이 필요한지, 일상 대화인지 여부에 대한 쿼리 라우터
class RouteQuery(BaseModel):
    datasource: Literal["chitchat", "search_pipeline"] = Field(
        ...,
        description=(
            "질문의 성격에 따라 다음 단계로 라우팅합니다:\n"
            "1. 'chitchat': 단순 인사, 날씨, 안부, 자기소개 등 검색이 필요 없는 일상 대화.\n"
            "2. 'search_pipeline': 코드, 버그, 지라(Jira), Pull Request, 기능 구현, 에러 원인 분석 등 "
            "소프트웨어 개발 프로젝트와 관련된 모든 기술적인 질문"
        ),
    )
