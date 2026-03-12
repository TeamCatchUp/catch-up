"""
Github Connector Schemas
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ============================================================
# 공통 서브 모델
# ============================================================

class GithubUser(BaseModel):
    """Github 사용자 정보"""
    id: int
    login: str
    name: str | None = None
    email: str | None = None
    avatar_url: str | None = None
    html_url: str | None = None


# ============================================================
# Issue 관련 스키마
# ============================================================

class GithubIssueComment(BaseModel):
    """Issue 코멘트 (간소화)"""
    author: GithubUser | None = None
    body: str
    created_at: datetime
    updated_at: datetime | None = None


class GithubIssue(BaseModel):
    """
    Github Issue (GraphQL 기반 간소화)

    - GraphQL API 응답에서 파싱하여 생성
    - PGVector에 저장할 Document로 변환 가능
    """
    # 기본 식별
    number: int
    html_url: str  # Web URL (API URL 제거)

    # 내용
    title: str
    body: str | None = None
    state: str  # open/closed
    state_reason: str | None = None  # completed/not_planned/reopened

    # 담당자
    author: GithubUser | None = None
    assignees: list[GithubUser] = Field(default_factory=list)
    # Note: GitHub GraphQL API의 Issue 타입에는 closedBy 필드가 없음 (PR만 지원)

    # 시간
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None = None

    # 코멘트
    comments_count: int = 0
    comments: list[GithubIssueComment] = Field(default_factory=list)


# ============================================================
# Pull Request 관련 스키마
# ============================================================

class PRComment(BaseModel):
    """PR 파일에 달린 개별 리뷰 코멘트 (최적화 버전)"""

    id: int
    author: str
    body: str
    created_at: str
    line: Optional[int] = Field(default=None, description="코멘트가 달린 라인 번호")
    original_line: Optional[int] = Field(
        default=None, description="코멘트 작성 시점의 라인 번호"
    )


class PRFileContext(BaseModel):
    """PR에 포함된 파일의 변경 내역 및 코멘트 정보"""

    path: str = Field(description="파일 경로")
    status: str = Field(description="변경 상태 (modified, added, deleted, etc)")
    additions: int
    deletions: int
    previous_filename: Optional[str] = Field(
        default=None, description="Renaming의 경우 이전 파일 이름 포함"
    )
    patch: str = Field(default="", description="변경된 코드 내용 (Diff)")
    comments: list[PRComment] = Field(
        default_factory=list, description="해당 파일에 달린 리뷰 코멘트 목록"
    )


class GithubPRReview(BaseModel):
    """PR 리뷰"""
    author: GithubUser | None = None
    state: str  # APPROVED/CHANGES_REQUESTED/COMMENTED/DISMISSED/PENDING
    body: str | None = None
    submitted_at: datetime | None = None


class GithubPRComment(BaseModel):
    """PR 리뷰 코멘트 (파일별 인라인 코멘트)"""
    author: GithubUser | None = None
    body: str
    path: str | None = None  # 파일 경로
    line: int | None = None  # 코멘트가 달린 라인
    original_line: int | None = None  # 코멘트 작성 시점의 라인 번호
    diff_hunk: str | None = None  # 대상 코드 (diff)
    created_at: datetime
    updated_at: datetime | None = None


class GithubPRCommitInfo(BaseModel):
    """PR에 포함된 커밋 정보 (간소화)"""
    sha: str
    message: str
    author_name: str | None = None
    author_login: str | None = None
    committed_at: datetime | None = None


class GithubPullRequest(BaseModel):
    """
    Github Pull Request

    - API 응답에서 파싱하여 생성
    - PGVector에 저장할 Document로 변환 가능
    """
    # 기본 식별
    number: int
    url: str  # API URL
    html_url: str  # Web URL

    # 내용
    title: str
    body: str | None = None
    state: str  # open/closed
    merged: bool = False

    # 브랜치 정보
    base_ref: str  # base branch (e.g., main)
    head_ref: str  # head branch (e.g., feat/new-feature)

    # 사람
    author: GithubUser | None = None
    assignees: list[GithubUser] = Field(default_factory=list)
    reviewers: list[GithubUser] = Field(default_factory=list)
    merged_by: GithubUser | None = None

    # 시간
    created_at: datetime
    updated_at: datetime
    merged_at: datetime | None = None
    closed_at: datetime | None = None

    # 코드 변경 통계
    changed_files: int = 0
    commits_count: int = 0

    # 리뷰 정보
    reviews: list[GithubPRReview] = Field(default_factory=list)

    # 리뷰 코멘트 (파일별 인라인 코멘트)
    comments: list[GithubPRComment] = Field(default_factory=list)

    # PR에 포함된 커밋 목록
    commits: list[GithubPRCommitInfo] = Field(default_factory=list)


# ============================================================
# Commit 관련 스키마
# ============================================================

class GithubCommitFile(BaseModel):
    """Commit에서 변경된 파일"""
    filename: str
    status: str  # added/modified/removed/renamed
    additions: int = 0
    deletions: int = 0
    changes: int = 0
    patch: str | None = None
    previous_filename: str | None = None


class GithubCommit(BaseModel):
    """
    Github Commit

    - API 응답에서 파싱하여 생성
    - PGVector에 저장할 Document로 변환 가능
    """
    # 기본 식별
    sha: str
    url: str  # API URL
    html_url: str  # Web URL

    # 커밋 내용
    message: str

    # 작성자 정보
    author: GithubUser | None = None  # Github 계정 연결된 경우
    author_name: str | None = None  # Git 커밋 author name
    author_email: str | None = None  # Git 커밋 author email
    committer: GithubUser | None = None
    committer_name: str | None = None
    committer_email: str | None = None

    # 시간
    committed_at: datetime

    # 통계
    additions: int = 0
    deletions: int = 0
    total_changes: int = 0

    # 변경 파일
    files: list[GithubCommitFile] = Field(default_factory=list)

    # 관계
    pr_number: int | None = None  # 연결된 PR
    parent_shas: list[str] = Field(default_factory=list)


# ============================================================
# Repository 관련 스키마
# ============================================================

class GithubRepository(BaseModel):
    """
    Github Repository

    - RDBMS에 저장 (정적 참조 데이터)
    """
    # 기본 식별
    id: int
    node_id: str | None = None
    name: str
    full_name: str  # owner/repo
    html_url: str

    # 내용
    description: str | None = None
    topics: list[str] = Field(default_factory=list)
    language: str | None = None
    default_branch: str = "main"

    # Owner 정보
    owner: GithubUser

    # 통계
    stargazers_count: int = 0
    forks_count: int = 0
    watchers_count: int = 0
    open_issues_count: int = 0
    size: int = 0

    # 상태
    private: bool = False
    archived: bool = False
    disabled: bool = False
    fork: bool = False

    # 시간
    created_at: datetime
    updated_at: datetime
    pushed_at: datetime | None = None


# ============================================================
# Webhook Payload 스키마 (Github App 설치/관리 이벤트)
# ============================================================

class GithubAccount(BaseModel):
    """Github App이 설치된 계정 (Organization 또는 User)"""
    id: int
    login: str
    type: str  # "Organization" or "User"
    avatar_url: Optional[str] = None


class GithubInstallationInfo(BaseModel):
    id: int
    account: GithubAccount
    app_id: int
    repository_selection: Optional[str] = None  # "all" or "selected"
    suspended_at: Optional[datetime] = None


class GithubSender(BaseModel):
    id: int
    login: str


class InstallationWebhookPayload(BaseModel):
    """
    Github App Installation Webhook Payload
    - action: created, deleted, suspend, unsuspend, new_permissions_accepted
    """
    action: str
    installation: GithubInstallationInfo
    sender: GithubSender


class InstallationRepositoriesWebhookPayload(BaseModel):
    """
    Installation Repositories Webhook Payload
    - action: added, removed
    """
    action: str
    installation: GithubInstallationInfo
    repositories_added: list = Field(default_factory=list)
    repositories_removed: list = Field(default_factory=list)
    sender: GithubSender

# =================================================================
#                 Webhook Event Payload Schema
# =================================================================

class IssueWebhookPayload(BaseModel):
    action: str
    issue: dict
    repository: dict
    installation: dict
    sender: GithubSender

class PullRequestWebhookPayload(BaseModel):
    action: str
    pull_request: dict
    repository: dict
    installation: dict
    sender: GithubSender

# =================================================================
#                 Sync Request Schema
# =================================================================

class FullSyncRequest(BaseModel):
    """전체 동기화 요청"""
    repo_ids: list[int] | None = Field(
        default=None,
        description="동기화할 Repository ID 목록. None이면 모든 접근 가능 레포"
    )
