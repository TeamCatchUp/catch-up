import logging
from enum import StrEnum
from typing import Annotated
from typing import Literal
from typing import Optional
from typing import Union

from langchain_core.documents import Document
from pydantic import BaseModel
from pydantic import Field

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# Enums
# --------------------------------------------------------------------------
class SourceType(StrEnum):
    JIRA = "jira"
    CONFLUENCE = "confluence"
    SLACK = "slack"
    GITHUB = "github"
    UNKNOWN = "unknown"


class EntityType(StrEnum):
    # Jira
    ISSUE = "issue"
    EPIC = "epic"
    # Confluence
    PAGE = "page"
    BLOGPOST = "blogpost"
    # Slack
    MESSAGE = "message"
    # GitHub
    PR = "pr"
    # Common / Others
    COMMENT = "comment"


# --------------------------------------------------------------------------
# Base Model
# --------------------------------------------------------------------------
class BaseSource(BaseModel):
    """
    모든 검색 결과의 공통 부모 클래스
    """

    # 식별자 및 분류
    id: str = Field(..., description="고유 ID (예: jira:issue:CAT-145)")

    # 데이터 출처
    source: SourceType = Field(..., description="데이터 소스 (e.g. Jira, Slack, GitHub)")
    entity_type: EntityType = Field(..., description="엔티티 타입 (툴별 상이)")

    # 공통 메타데이터
    title: str = Field(..., description="제목 또는 요약")
    url: str | None = Field(None, description="원본 링크")
    text: str = Field(..., description="본문 내용")
    
    # 시간 정보
    created_at: str | None = Field(None, description="생성일 (ISO 8601)")
    updated_at: str | None = Field(None, description="수정일 (ISO 8601)")

    author: str | None = Field(None, description="작성자")

    # RAG 관련
    index: int | None = Field(None, description="LLM이 답변에 활용한 출처 번호")
    relevance_score: float = Field(default=0.0, description="검색 관련성 점수")
    is_cited: bool = Field(default=False, description="LLM 인용 여부")
    citation_rationale: Optional[str] = Field(default="", description="LLM이 문서를 인용한 이유")

    @classmethod
    def from_document(
        cls,
        index: int,
        doc: Document,
        relevance_score: float = 0.0,
        is_cited: bool = False,
    ) -> "SourceResponse":
        """
        Factory Method: Metadata -> Specific Source Model
        """
        metadata = doc.metadata
        source_str = metadata.get("source", "unknown")
        entity_type = metadata.get("entity_type", "unknown")
        
        doc_id = getattr(doc, "id", None)
        if not doc_id:
            # doc.id가 존재하지 않을 경우 fallback
            if source_str == "jira":
                # jira:{issue|epic}:{issue_key}
                issue_key = metadata.get("issue_key")
                if issue_key:
                    doc_id = f"jira:{entity_type}:{issue_key}"

            elif source_str == "slack":
                # slack:message:{team_id}:{channel_id}:{ts}
                team_id = metadata.get("team_id")
                channel_id = metadata.get("channel_id")
                ts = metadata.get("ts")
                if team_id and channel_id and ts:
                    doc_id = f"slack:message:{team_id}:{channel_id}:{ts}"

            elif source_str == "github":
                # github:{issue|pr}:{owner}/{repo}:{number}
                full_name = metadata.get("full_name")
                # full_name이 없으면 owner/repo 조합
                if not full_name:
                    owner = metadata.get("owner")
                    repo = metadata.get("repo")
                    if owner and repo:
                        full_name = f"{owner}/{repo}"
                
                number = metadata.get("number")
                
                if full_name and number:
                    doc_id = f"github:{entity_type}:{full_name}:{number}"
                    
            elif source_str == "confluence":
                content_id = metadata.get("id")
                chunk_index = metadata.get("chunk_index")
                if content_id and chunk_index is not None:
                    doc_id = f"confluence:{entity_type}:{content_id}:chunk:{chunk_index}"
            

        # Slack은 edited_at을 사용하므로, updated_at이 없으면 edited_at을 찾도록 fallback 처리
        updated_at = metadata.get("updated_at") or metadata.get("edited_at")

        # 공통 데이터 셋업
        base_data = {
            "index": index,
            "id": doc_id,
            "relevance_score": relevance_score,
            "is_cited": is_cited,
            "text": doc.metadata.get('contextual_content', ''),
            "url": metadata.get("url"),
            "created_at": metadata.get("created_at"),
            "updated_at": updated_at,
            "entity_type": entity_type,
        }

        # 1. Jira
        if source_str == "jira":
            issue_title = (
                metadata.get("title")
                or metadata.get("summary")
                or "No Title"
            )
            return JiraSource(
                **base_data,
                source=SourceType.JIRA,
                title=f"[{metadata.get('issue_key')}] {issue_title}",
                author=metadata.get("reporter"),
                # Jira Specific
                project_key=metadata.get("project_key"),
                issue_key=metadata.get("issue_key"),
                status=metadata.get("status"),
                priority=metadata.get("priority"),
                assignee=metadata.get("assignee"),
                labels=metadata.get("labels", []),
            )

        # 2. Slack
        elif source_str == "slack":

            return SlackSource(
                **base_data,
                source=SourceType.SLACK,
                title=metadata.get("summary", "Slack Message"),
                author=metadata.get("author_name"),
                # Slack Specific
                channel_name=metadata.get("channel_name"),
                team_id=metadata.get("team_id"),
                ts=metadata.get("ts"),
                thread_ts=metadata.get("thread_ts"),
            )

        # 3. GitHub
        elif source_str == "github":            
            full_name = metadata.get("full_name", "")
            owner, repo = (
                full_name.split("/", 1)  # 최대 한 번만 분리
                if "/" in full_name
                else (metadata.get("owner"), metadata.get("repo"))
            )
            
            author_info = metadata.get("author")
            author = ""
            if author_info:
                author = author_info.get("name") or author_info.get("login")
            
            return GithubSource(
                **base_data,
                source=SourceType.GITHUB,
                title=metadata.get(
                    "summary", f"{entity_type} #{metadata.get('number')}"
                ),
                author=author,
                # Github Common
                owner=owner,
                repo=repo,
                number=int(metadata.get("number", 0)),
                state=metadata.get("state"),
                labels=metadata.get("labels", []),
                # PR Specific Fields
                merged=metadata.get("merged"),
                base_ref=metadata.get("base_ref"),
                head_ref=metadata.get("head_ref"),
            )
        
        # 4. Confluence
        elif source_str == "confluence":
            return ConfluenceSource(
                **base_data,
                source=SourceType.CONFLUENCE,
                title=metadata.get("title", "No Title"),
                author=metadata.get("author_name"),
                space_id=metadata.get("space_id"),
                space_key=metadata.get("space_key"),
                space_name=metadata.get("space_name"),
                parent_page_id=metadata.get("parent_page_id"),
                version=metadata.get("version"),
                labels=metadata.get("labels", []),
                chunk_index=metadata.get("chunk_index"),
                total_chunks=metadata.get("total_chunks"),
                section_hierarchy=metadata.get("section_hierarchy", []),
                has_images=metadata.get("has_images", False),
                image_urls=metadata.get("image_urls", []),
            )
        
        # Fallback
        return UnknownSource(
            **base_data,
            title="Unknown Source",
        )


# --------------------------------------------------------------------------
# Specific Models (Source별 통합 모델)
# --------------------------------------------------------------------------


class JiraSource(BaseSource):
    source: Literal[SourceType.JIRA] = SourceType.JIRA
    
    project_key: str | None = Field(None, description="프로젝트 키")
    issue_key: str | None = Field(None, description="이슈 키")
    status: str | None = Field(None, description="상태")
    priority: str | None = Field(None, description="우선순위")
    assignee: str | None = Field(None, description="담당자")
    labels: list[str] = Field(default_factory=list)


class SlackSource(BaseSource):
    source: Literal[SourceType.SLACK] = SourceType.SLACK
    
    channel_name: str | None = Field(None, description="채널 이름")
    team_id: str | None = Field(None, description="워크스페이스 ID")
    ts: str | None = Field(None, description="타임스탬프")
    thread_ts: str | None = Field(None, description="스레드 부모 TS")


class GithubSource(BaseSource):
    source: Literal[SourceType.GITHUB] = SourceType.GITHUB
    
    # Common Fields
    owner: str | None = Field(None, description="Owner")
    repo: str | None = Field(None, description="Repo")
    number: int | None = Field(None, description="번호")
    state: str | None = Field(None, description="상태")
    labels: list[str] = Field(default_factory=list)

    # PR Specific (Optional)
    merged: bool | None = Field(None, description="머지 여부 (PR only)")
    base_ref: str | None = Field(None, description="타겟 브랜치 (PR only)")
    head_ref: str | None = Field(None, description="소스 브랜치 (PR only)")


class ConfluenceSource(BaseSource):
    source: Literal[SourceType.CONFLUENCE] = SourceType.CONFLUENCE
    
    space_id: str | None = Field(None, description="스페이스 ID")
    space_key: str | None = Field(None, description="스페이스 키")
    space_name: str | None = Field(None, description="스페이스 이름")
    parent_page_id: str | None = Field(None, description="상위 페이지 ID")
    version: int | str | None = Field(None, description="문서 버전")
    labels: list[str] = Field(default_factory=list, description="라벨 목록")
    chunk_index: int | None = Field(None, description="현재 청크 인덱스")
    total_chunks: int | None = Field(None, description="전체 청크 수")
    section_hierarchy: list[str] = Field(default_factory=list, description="섹션 계층 구조")
    has_images: bool = Field(False, description="이미지 포함 여부")
    image_urls: list[str] = Field(default_factory=list, description="이미지 URL 목록")


# Fallback
class UnknownSource(BaseSource):
    source: Literal[SourceType.UNKNOWN] = SourceType.UNKNOWN

# --------------------------------------------------------------------------
# Response Union
# --------------------------------------------------------------------------
SourceResponse = Annotated[
    Union[JiraSource, SlackSource, GithubSource, ConfluenceSource, UnknownSource],
    Field(discriminator="source"),
]
