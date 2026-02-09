"""
GitHub Connector Schemas
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ============================================================
# 공통 서브 모델
# ============================================================

class GitHubUser(BaseModel):
    """GitHub 사용자 정보"""
    id: int
    login: str
    avatar_url: str | None = None
    html_url: str | None = None


class GitHubLabel(BaseModel):
    """Issue/PR 라벨"""
    id: int
    name: str
    color: str | None = None
    description: str | None = None


class GitHubMilestone(BaseModel):
    """Milestone 정보"""
    id: int
    number: int
    title: str
    state: str  # open/closed
    description: str | None = None
    due_on: datetime | None = None


class GitHubReaction(BaseModel):
    """리액션 카운트"""
    total_count: int = 0
    plus_one: int = Field(default=0, alias="+1")
    minus_one: int = Field(default=0, alias="-1")
    laugh: int = 0
    hooray: int = 0
    confused: int = 0
    heart: int = 0
    rocket: int = 0
    eyes: int = 0

    class Config:
        populate_by_name = True


# ============================================================
# Issue 관련 스키마
# ============================================================

class GitHubIssueComment(BaseModel):
    """Issue 코멘트"""
    id: int
    author: GitHubUser | None = None
    body: str
    created_at: datetime
    updated_at: datetime | None = None
    reactions: GitHubReaction | None = None


class GitHubIssue(BaseModel):
    """
    GitHub Issue

    - API 응답에서 파싱하여 생성
    - PGVector에 저장할 Document로 변환 가능
    """
    # 기본 식별
    number: int
    id: int
    node_id: str | None = None
    url: str  # API URL
    html_url: str  # Web URL

    # 내용
    title: str
    body: str | None = None
    state: str  # open/closed
    state_reason: str | None = None  # completed/not_planned/reopened

    # 담당자
    author: GitHubUser | None = None
    assignees: list[GitHubUser] = Field(default_factory=list)

    # 분류
    labels: list[GitHubLabel] = Field(default_factory=list)
    milestone: GitHubMilestone | None = None

    # 시간
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None = None

    # 부가정보
    comments_count: int = 0
    comments: list[GitHubIssueComment] = Field(default_factory=list)
    reactions: GitHubReaction | None = None

    # 관계 (body에서 파싱)
    linked_pr_numbers: list[int] = Field(default_factory=list)
    referenced_issues: list[int] = Field(default_factory=list)


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


class GitHubPRReview(BaseModel):
    """PR 리뷰"""
    id: int
    author: GitHubUser | None = None
    state: str  # APPROVED/CHANGES_REQUESTED/COMMENTED/DISMISSED/PENDING
    body: str | None = None
    submitted_at: datetime | None = None


class GitHubPRComment(BaseModel):
    """PR 리뷰 코멘트 (파일별 인라인 코멘트)"""
    id: int
    author: GitHubUser | None = None
    body: str
    path: str | None = None  # 파일 경로
    line: int | None = None  # 코멘트가 달린 라인
    original_line: int | None = None  # 코멘트 작성 시점의 라인 번호
    diff_hunk: str | None = None  # 대상 코드 (diff)
    created_at: datetime
    updated_at: datetime | None = None


class GitHubPRCommitInfo(BaseModel):
    """PR에 포함된 커밋 정보 (간소화)"""
    sha: str
    message: str
    author_name: str | None = None
    author_login: str | None = None
    committed_at: datetime | None = None


class GitHubPullRequest(BaseModel):
    """
    GitHub Pull Request

    - API 응답에서 파싱하여 생성
    - PGVector에 저장할 Document로 변환 가능
    """
    # 기본 식별
    number: int
    id: int
    node_id: str | None = None
    url: str  # API URL
    html_url: str  # Web URL

    # 내용
    title: str
    body: str | None = None
    state: str  # open/closed
    draft: bool = False
    merged: bool = False

    # 브랜치 정보
    base_ref: str  # base branch (e.g., main)
    head_ref: str  # head branch (e.g., feat/new-feature)
    base_sha: str | None = None
    head_sha: str | None = None

    # 담당자
    author: GitHubUser | None = None
    assignees: list[GitHubUser] = Field(default_factory=list)
    requested_reviewers: list[GitHubUser] = Field(default_factory=list)

    # 분류
    labels: list[GitHubLabel] = Field(default_factory=list)
    milestone: GitHubMilestone | None = None

    # 시간
    created_at: datetime
    updated_at: datetime
    merged_at: datetime | None = None
    closed_at: datetime | None = None

    # 코드 변경 통계
    additions: int = 0
    deletions: int = 0
    changed_files: int = 0
    commits_count: int = 0

    # 리뷰 정보
    reviews: list[GitHubPRReview] = Field(default_factory=list)

    # 리뷰 코멘트 (파일별 인라인 코멘트)
    comments: list[GitHubPRComment] = Field(default_factory=list)

    # PR에 포함된 커밋 목록
    commits: list[GitHubPRCommitInfo] = Field(default_factory=list)

    # 관계 (body에서 파싱: "closes #123", "fixes #456")
    linked_issue_numbers: list[int] = Field(default_factory=list)


# ============================================================
# Commit 관련 스키마
# ============================================================

class GitHubCommitFile(BaseModel):
    """Commit에서 변경된 파일"""
    filename: str
    status: str  # added/modified/removed/renamed
    additions: int = 0
    deletions: int = 0
    changes: int = 0
    patch: str | None = None
    previous_filename: str | None = None


class GitHubCommit(BaseModel):
    """
    GitHub Commit

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
    author: GitHubUser | None = None  # GitHub 계정 연결된 경우
    author_name: str | None = None  # Git 커밋 author name
    author_email: str | None = None  # Git 커밋 author email
    committer: GitHubUser | None = None
    committer_name: str | None = None
    committer_email: str | None = None

    # 시간
    committed_at: datetime

    # 통계
    additions: int = 0
    deletions: int = 0
    total_changes: int = 0

    # 변경 파일
    files: list[GitHubCommitFile] = Field(default_factory=list)

    # 관계
    pr_number: int | None = None  # 연결된 PR
    parent_shas: list[str] = Field(default_factory=list)


# ============================================================
# Repository 관련 스키마
# ============================================================

class GitHubRepository(BaseModel):
    """
    GitHub Repository

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
    owner: GitHubUser

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
# Webhook Payload 스키마 (GitHub App 설치/관리 이벤트)
# ============================================================

class GitHubAccount(BaseModel):
    """GitHub App이 설치된 계정 (Organization 또는 User)"""
    id: int
    login: str
    type: str  # "Organization" or "User"
    avatar_url: Optional[str] = None


class GitHubInstallationInfo(BaseModel):
    id: int
    account: GitHubAccount
    app_id: int
    repository_selection: Optional[str] = None  # "all" or "selected"
    suspended_at: Optional[datetime] = None


class GitHubSender(BaseModel):
    id: int
    login: str


class InstallationWebhookPayload(BaseModel):
    """
    GitHub App Installation Webhook Payload
    - action: created, deleted, suspend, unsuspend, new_permissions_accepted
    """
    action: str
    installation: GitHubInstallationInfo
    sender: GitHubSender


class InstallationRepositoriesWebhookPayload(BaseModel):
    """
    Installation Repositories Webhook Payload
    - action: added, removed
    """
    action: str
    installation: GitHubInstallationInfo
    repositories_added: list = Field(default_factory=list)
    repositories_removed: list = Field(default_factory=list)
    sender: GitHubSender
