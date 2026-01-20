from enum import IntEnum
from typing import Optional

from langchain_core.documents import Document
from pydantic import BaseModel, Field

from app.rag.models.pr_base import PRFileContext


class SourceType(IntEnum):
    CODE = 0
    PULL_REQUEST = 1
    ISSUE = 2
    JIRA_ISSUE = 3


# 공통 필드
class BaseSearchResult(BaseModel):
    id: str | int = Field(description="고유 식별자 (Code: UUID, PR: pr_number)")
    source_type: SourceType = Field(description="출처 유형")
    # source: str = Field(description="출처 이름(code: owner_repo_branch, pr: owner_repo)")\\
    
    owner: str = Field(default="", description="레포지토리 소유자")
    repo: str = Field(description="레포지토리 이름")
    
    text: str = Field(default="", description="문서 본문")
    html_url: str = Field(default="", description="출처 원본 url")
    relevance_score: Optional[float] = Field(None, description="Rerank 점수")

    @classmethod
    def _base_kwargs_from_doc(cls, doc: Document) -> dict:
        
        metadata = doc.metadata
        
        doc_id = metadata.get("id")
        if doc_id is None and metadata.get("pr_number"):
            doc_id = metadata.get("pr_number")
        
        return {
            "id": doc_id,
            "source_type": SourceType(metadata.get("source_type")),
            "owner": metadata.get("owner", ""),
            "repo": metadata.get("repo", ""),
            "text": doc.page_content,
            "html_url": metadata.get("html_url", ""),
        }
    
    def to_context_text(self, index: int) -> str:
        """하위 클래스에서 오버라이딩"""
        source_display = f"{self.owner}/{self.repo}"        
        return f"[{index}] 출처: {source_display} | 유형: {self.source_type.name}\n내용:\n{self.text}"


# Code
class CodeSearchResult(BaseSearchResult):
    branch: str = Field(default="main", description="브랜치 명")
    file_path: str = Field("", description="파일 경로")
    chunk_number: int = Field(default=0, description="청크 번호")
    category: str = Field(default="", description="파일 범주")
    language: str | None = Field(default="", description="프로그래밍 언어")

    @classmethod
    def from_search_result_doc(cls, doc: Document) -> "CodeSearchResult":
        metadata = doc.metadata
        
        raw_category: str = metadata.get("category", "")
        
        language = raw_category if not raw_category.startswith(".") else None

        return cls(
            # BaseSearchResult
            **BaseSearchResult._base_kwargs_from_doc(doc),
            # CodeSearchResult
            file_path=metadata.get("file_path", ""),
            chunk_number=metadata.get("chunk_number", 0),            
            category=raw_category,
            language=metadata.get("language", language),
        )
    
    def to_context_text(self, index: int) -> str:
        return (
            f"[{index}] 출처: {self.owner}/{self.repo} ({self.file_path}) | "
            f"언어: {self.language or 'N/A'}\n"
            f"코드 내용:\n{self.text}"
        )


# Pull Request
class PullRequestSearchResult(BaseSearchResult):
    # Core    
    pr_number: int = Field(default=0)
    title: str = Field(default="")
    state: str = Field(default="open")
    author: str = Field(default="")
    
    # Branch
    base_branch: str = Field(default="", description="타겟 브랜치")
    head_branch: str = Field(default="", description="소스 브랜치")
    
    # Timestamps
    created_at: int = Field(default=0)
    updated_at: int = Field(default=0)
    merged_at: int | None = Field(default=None)
    closed_at: int | None = Field(default=None)
    
    # Content (본문)
    body: str | None = Field(default=None)
    commit_messages: list[str] = Field(default_factory=list)
    
    # File Changes
    changed_files: list[str] = Field(default_factory=list)
    additions: int = Field(default=0)
    deletions: int = Field(default=0)    

    # Others
    labels: list[str] = Field(default_factory=list)
    milestone: str | None = Field(default=None)
    
    # 런타임 Context
    file_context: list[PRFileContext] = Field(default_factory=list)
    
    @property
    def branch(self) -> str:
        return self.base_branch
    
    @classmethod
    def from_search_result_doc(cls, doc: Document) -> "PullRequestSearchResult":
        metadata = doc.metadata

        return cls(
            # BaseSearchResult
            **BaseSearchResult._base_kwargs_from_doc(doc),
            
            # PullRequestSearchResult Core
            pr_number=metadata.get("pr_number"),
            title=metadata.get("title", ""),
            state=metadata.get("state"),
            author=metadata.get("author"),
            
            # Repository
            base_branch=metadata.get("base_branch", ""),
            head_branch=metadata.get("head_branch", ""),
                        
            # Timestamps
            created_at=metadata.get("created_at"),
            updated_at=metadata.get("updated_at"),
            merged_at=metadata.get("merged_at"),
            closed_at=metadata.get("closed_at"),
            
            # Content
            body=metadata.get("body", ""),
            commit_messages=metadata.get("commit_messages", []),
            
            # File Changes
            changed_files=metadata.get("changed_files", []),
            additions=metadata.get("additions", 0),
            deletions=metadata.get("deletions", 0),
            
            # Metadata
            labels=metadata.get("labels", []),
            milestone=metadata.get("milestone"),
        )
    
    def to_context_text(self, index: int) -> str:
        header = (
            f"[{index}] 출처: {self.owner}/{self.repo} (PR #{self.pr_number}) | "
            f"제목: {self.title} | 상태: {self.state}\n"
        )
        
        content = f"=== PR 본문/요약 ===\n{self.body}"
        
        if self.commit_messages:
            content += "\n=== 주요 커밋===\n" + "\n".join(f"- {msg}" for msg in self.commit_messages[:10])
            if len(self.commit_messages) > 10:
                content += f"\n... (외 {len(self.commit_messages)-10})"
            
        if self.file_context:
            content += "\n=== 변경된 파일 상세 (Diff 포함) ===\n"
            for fc in self.file_context:
                content += (
                    f"파일: {fc.path} ({fc.status})"
                    f"변경: +{fc.additions} / -{fc.deletions} "
                    f"Diff: \n{fc.patch}\n"
                    f"---\n"
                )
        return header + content
        
        
class IssueSearchResult(BaseSearchResult):
    @classmethod
    def from_search_result_doc(cls, doc: Document) -> "IssueSearchResult":
        pass


class JiraIssueSearchResult(BaseSearchResult):
    # Core Fields (Java의 JiraIssueDocument와 매핑)
    summary: str = Field(..., description="이슈 요약(제목)")
    description: str | None = Field(None, description="이슈 상세 내용")
    
    project_name: str = Field(default="", description="프로젝트 이름")
    project_key: str = Field(default="", description="프로젝트 키")
    
    issue_type_name: str | None = Field(None, description="이슈 타입 (Task, Bug ...)")
    status_id: int | None = Field(None, description="상태 ID")
    priority_id: int | None = Field(None, description="우선순위 ID")
    
    assignee_name: str | None = Field(None, description="담당자")
    reporter_name: str | None = Field(None, description="보고자")
    
    created_at: str | None = Field(None, description="생성일시")
    resolution_date: str | None = Field(None, description="해결일시")
    
    # Hierarchy (계층 구조용)
    parent_key: str | None = Field(None, description="부모 이슈 키 (Epic)")
    parent_summary: str | None = Field(None, description="부모 이슈 제목")

    @classmethod
    def from_search_result_doc(cls, doc: Document) -> "JiraIssueSearchResult":
        metadata = doc.metadata
        
        raw_text = doc.page_content or metadata.get("description", "")
        if not raw_text.strip():
            raw_text = metadata.get("summary", "")
        
        base_data = {
            "id": metadata.get("id"), # 예: BJDD-72
            "source_type": SourceType.JIRA_ISSUE,
            "owner": metadata.get("project_key", ""), # Owner -> Project Key (임시)
            "repo": metadata.get("project_name", ""), # Repo -> Project Name (임시)
            "text": raw_text,
            "html_url": metadata.get("self_url", ""), # self_url -> html_url (임시)
        }

        return cls(
            **base_data,
            # Jira Specific
            summary=metadata.get("summary", ""),
            description=metadata.get("description"),
            project_name=metadata.get("project_name", ""),
            project_key=metadata.get("project_key", ""),
            issue_type_name=metadata.get("issue_type_name"),
            status_id=metadata.get("status_id"),
            priority_id=metadata.get("priority_id"),
            assignee_name=metadata.get("assignee_name"),
            reporter_name=metadata.get("reporter_name"),
            created_at=metadata.get("created_at"),
            resolution_date=metadata.get("resolution_date"),
            parent_key=metadata.get("parent_key"),
            parent_summary=metadata.get("parent_summary"),
        )

    def to_context_text(self, index: int) -> str:
        return (
            f"[{index}] 문서 타입: Jira Issue | 키: {self.id}\n"
            f"제목: {self.summary}\n"
            f"담당자: {self.assignee_name} | 상태: {self.status_id}\n"
            f"내용 요약: 이 이슈는 '{self.project_name}' 프로젝트의 '{self.parent_summary or '최상위'}' 작업의 일환으로 진행되었습니다.\n"
            f"상세 내용:\n{self.text}"
)

