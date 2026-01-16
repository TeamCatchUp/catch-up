from enum import IntEnum
from typing import Optional

from langchain_core.documents import Document
from pydantic import BaseModel, Field


class SourceType(IntEnum):
    CODE = 0
    PULL_REQUEST = 1
    ISSUE = 2


# 공통 필드
class BaseSearchResult(BaseModel):
    id: str = Field(description="고유 식별자")
    source_type: SourceType = Field(
        description="출처 유형(0: code, 1: pull request, 2: issue)"
    )
    source: str = Field(description="출처 이름")
    text: str = Field(description="문서 본문")
    html_url: str = Field(description="Github url")
    relevance_score: Optional[float] = Field(None, description="Rerank 점수")

    @classmethod
    def _base_kwargs_from_doc(cls, doc: Document) -> dict:
        metadata = doc.metadata
        return {
            "id": metadata.get("id"),
            "source_type": SourceType(metadata.get("sourceType")),  # 0 -> CODE
            "source": metadata.get("source"),
            "text": doc.page_content,
            "html_url": metadata.get("html_url"),
        }


# Code
class CodeSearchResult(BaseSearchResult):
    file_path: str = Field(description="파일 경로")
    category: str = Field(default="", description="파일 범주")
    language: str | None = Field(default="", description="프로그래밍 언어")

    @classmethod
    def from_search_result_doc(cls, doc: Document) -> "CodeSearchResult":
        metadata = doc.metadata

        return cls(
            # BaseSearchResult
            **BaseSearchResult._base_kwargs_from_doc(doc),
            # CodeSearchResult
            file_path=metadata.get("file_path", ""),
            category=metadata.get("category", ""),
            language=metadata.get("language", ""),
        )


# Pull Request
class PullRequestSearchResult(BaseSearchResult):
    title: str = Field(default="")
    body: str | None = Field(default=None)
    commit_messages: list[str] = Field(default_factory=list)
    changed_files: list[str] = Field(default_factory=list)
    changed_files_count: int = Field(default=0)
    pr_number: int = Field(default=0)
    state: str = Field(default="open")
    author: str = Field(default="")
    created_at: int = Field(default=0)
    updated_at: int = Field(default=0)
    merged_at: int | None = Field(default=None)
    closed_at: int | None = Field(default=None)
    additions: int = Field(default=0)
    deletions: int = Field(default=0)
    labels: list[str] = Field(default_factory=list)
    milestone: str | None = Field(default=None)
    repository_id: int = Field(
        default=0, description="PostgreSQL에 저장된 Repository 식별자"
    )
    owner: str = Field(default="")
    repo_name: str = Field(default="")
    branch: str = Field(default="")

    @classmethod
    def from_search_result_doc(cls, doc: Document) -> "PullRequestSearchResult":
        metadata = doc.metadata

        return cls(
            # BaseSearchResult
            **BaseSearchResult._base_kwargs_from_doc(doc),
            # PullRequestSearchResult
            title=metadata.get("title", ""),
            body=metadata.get("body", ""),
            commit_messages=metadata.get("commit_messages", []),
            changed_files=metadata.get("changed_files", []),
            changed_files_count=metadata.get(
                "changed_files_count",
                len(metadata.get("changed_files", [])),
            ),
            pr_number=metadata.get("pr_number"),
            state=metadata.get("state"),
            author=metadata.get("author"),
            created_at=metadata.get("created_at"),
            updated_at=metadata.get("updated_at"),
            merged_at=metadata.get("merged_at"),
            closed_at=metadata.get("closed_at"),
            additions=metadata.get("additions", 0),
            deletions=metadata.get("deletions", 0),
            labels=metadata.get("labels", []),
            milestone=metadata.get("milestone"),
            repository_id=metadata.get("repository_id"),
            owner=metadata.get("owner"),
            repo_name=metadata.get("repo_name"),
            branch=metadata.get("branch"),
        )


class IssueSearchResult(BaseSearchResult):
    @classmethod
    def from_search_result_doc(cls, doc: Document) -> "IssueSearchResult":
        pass
