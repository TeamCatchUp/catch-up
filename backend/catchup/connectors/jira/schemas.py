"""
Jira 엔티티 Pydantic 스키마

Jira API 응답을 파싱하고, PGVector Document로 변환하기 위한 중간 모델.
Transformer에서 이 스키마들을 사용하여 LangChain Document를 생성.

우선순위:
- P0 (필수): Issue, Epic
- P1 (권장): Project
- P2 (선택): Sprint
- P3 (선택): Component
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ============================================================
# 공통 서브 모델
# ============================================================

class JiraUser(BaseModel):
    """Jira 사용자 정보 (assignee, reporter 등)"""
    account_id: str | None = None
    display_name: str | None = None
    email_address: str | None = None


class JiraMention(BaseModel):
    """코멘트 내 @멘션"""
    account_id: str
    display_name: str | None = None
    text: str | None = None  # @멘션 텍스트 (예: "@John Doe")


class JiraInlineAttachment(BaseModel):
    """코멘트 본문에 포함된 인라인 미디어/첨부파일"""
    id: str
    collection: str | None = None  # Atlassian Media Collection ID
    type: str | None = None  # image, file, video 등
    alt: str | None = None  # 대체 텍스트 (이미지 설명)
    filename: str | None = None  # 파일명 (있을 경우)
    url: str | None = None  # 첨부파일 접근 URL


class JiraComment(BaseModel):
    """이슈 코멘트"""
    id: str
    author: str  # display_name
    author_account_id: str | None = None  # 작성자 account_id (멘션 매칭용)
    body: str    # 텍스트로 변환된 본문
    created: datetime
    # 코멘트 내 @멘션 목록
    mentions: list[JiraMention] = Field(default_factory=list)
    # 코멘트 본문에 포함된 인라인 미디어/첨부파일
    inline_attachments: list[JiraInlineAttachment] = Field(default_factory=list)


class JiraLinkedIssue(BaseModel):
    """연결된 이슈"""
    key: str
    summary: str | None = None
    status: str | None = None
    link_type: str  # "blocks", "is blocked by", "relates to" 등


class JiraAttachment(BaseModel):
    """첨부파일 메타데이터"""
    filename: str
    author: str | None = None
    mime_type: str | None = None
    url: str | None = None


class JiraSprintInfo(BaseModel):
    """이슈에 포함된 Sprint 정보 (Sprint 필드에서 추출)"""
    id: int
    name: str
    state: str | None = None  # future, active, closed


# ============================================================
# Issue
# ============================================================

class JiraIssue(BaseModel):
    """
    Jira 이슈 스키마 (Task, Story, Bug, Subtask 등)

    Epic을 제외한 모든 이슈 타입에 사용.
    Epic은 JiraEpic 스키마 사용.
    """
    # 기본 식별
    key: str                          # "CATCH-145"
    id: str                           # Jira 내부 ID
    url: str                          # 브라우저 URL

    # 분류
    project_key: str
    project_name: str
    issue_type: str                   # Task, Story, Bug, Subtask
    status: str
    priority: str | None = None
    resolution: str | None = None

    # 내용
    summary: str
    description: str | None = None    # 텍스트로 변환된 description

    # 담당자
    assignee: JiraUser | None = None
    reporter: JiraUser | None = None
    creator: JiraUser | None = None

    # 시간
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None = None
    due_date: str | None = None       # "2024-02-10" (날짜만)

    # 계층 구조
    parent_key: str | None = None     # 부모 이슈 키 (Epic, Task 등)
    parent_name: str | None = None    # 부모 이슈 제목
    subtask_keys: list[str] = Field(default_factory=list)

    # Agile
    sprint: JiraSprintInfo | None = None
    story_points: float | None = None

    # 분류 태그
    components: list[str] = Field(default_factory=list)
    labels: list[str] = Field(default_factory=list)
    fix_versions: list[str] = Field(default_factory=list)
    affects_versions: list[str] = Field(default_factory=list)

    # 시간 추적
    time_spent_seconds: int | None = None

    # 관계
    linked_issues: list[JiraLinkedIssue] = Field(default_factory=list)

    # 부가 정보
    comments: list[JiraComment] = Field(default_factory=list)
    attachments: list[JiraAttachment] = Field(default_factory=list)

    # 커스텀 필드 (ID → 이름으로 변환된 상태)
    # TODO: Development 필드 (GitHub PR, Branch, Commits) 포함 여부 확인
    custom_fields: dict[str, Any] = Field(default_factory=dict)


# ============================================================
# P0: Epic
# ============================================================

class JiraEpic(BaseModel):
    """
    Jira Epic 스키마

    Epic은 Issue의 특수 타입이지만 다른 Issue들을 묶는 상위 개념.
    별도 entity_type으로 저장.
    """
    # 기본 식별
    key: str
    id: str
    url: str

    # Epic 특화
    epic_name: str                    # Epic Name 필드
    epic_color: str | None = None     # Epic 컬러

    # 분류
    project_key: str
    project_name: str
    status: str
    priority: str | None = None

    # 내용
    summary: str
    description: str | None = None

    # 담당자 (Epic Owner)
    assignee: JiraUser | None = None
    reporter: JiraUser | None = None

    # 시간
    created_at: datetime
    updated_at: datetime

    # Epic 하위 이슈들
    issues_in_epic_keys: list[str] = Field(default_factory=list)
    issues_in_epic_count: int = 0
    completed_issues_count: int = 0
    in_progress_issues_count: int = 0
    todo_issues_count: int = 0

    # 분류 태그
    components: list[str] = Field(default_factory=list)
    labels: list[str] = Field(default_factory=list)
    fix_versions: list[str] = Field(default_factory=list)

    # 부가 정보
    comments: list[JiraComment] = Field(default_factory=list)
    custom_fields: dict[str, Any] = Field(default_factory=dict)


# ============================================================
# P1: Project
# ============================================================

class JiraProject(BaseModel):
    """
    Jira 프로젝트 스키마

    프로젝트당 1개 Document. 상위 레벨 컨텍스트 제공.
    """
    # 기본 식별
    key: str                          # "CATCH"
    id: str
    name: str
    url: str

    # 프로젝트 정보
    description: str | None = None
    project_type: str | None = None   # software, business, service_desk
    project_category: str | None = None

    # 담당자
    lead: JiraUser | None = None

    # 구성 요소
    components: list[str] = Field(default_factory=list)
    versions: list[str] = Field(default_factory=list)

    # 통계 (동기화 시점 기준)
    issue_count: int = 0
    open_issues: int = 0
    in_progress_issues: int = 0
    done_issues: int = 0
    epic_count: int = 0

    # 시간
    created_at: datetime | None = None
    updated_at: datetime | None = None


# ============================================================
# P2: Sprint
# ============================================================

class JiraSprint(BaseModel):
    """
    Jira 스프린트 스키마

    Agile API에서 조회. Sprint 단위 검색/분석에 사용.
    """
    # 기본 식별
    id: int
    name: str
    url: str | None = None

    # 스프린트 정보
    project_key: str | None = None
    board_id: int | None = None
    state: str                        # future, active, closed
    goal: str | None = None

    # 시간
    start_date: datetime | None = None
    end_date: datetime | None = None
    complete_date: datetime | None = None

    # 이슈 목록
    issue_keys: list[str] = Field(default_factory=list)
    completed_issue_keys: list[str] = Field(default_factory=list)
    incomplete_issue_keys: list[str] = Field(default_factory=list)

    # 통계
    total_issues: int = 0
    completed_issues: int = 0
    incomplete_issues: int = 0
    total_story_points: float = 0
    completed_story_points: float = 0


# ============================================================
# P3: Component
# ============================================================

class JiraComponent(BaseModel):
    """
    Jira 컴포넌트 스키마

    상세 설명이 있는 경우에만 저장 권장.
    """
    # 기본 식별
    id: str
    name: str
    project_key: str

    # 컴포넌트 정보
    description: str | None = None
    lead: JiraUser | None = None
    assignee_type: str | None = None  # COMPONENT_LEAD, PROJECT_LEAD, UNASSIGNED

    # 통계
    total_issues: int = 0
    open_issues: int = 0


# ============================================================
# OAuth / 인증 관련 스키마
# ============================================================

class JiraOAuthTokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int = Field(description="Access Token의 만료 시간(초 단위)")
    scope: str = ""

class JiraAccessibleResource(BaseModel):
    id: str = Field(description="Jira Cloud ID")
    name: str = Field(description="Jira Site Name")
    url: str = Field(description="Jira Site URL")
    scopes: list[str] = Field(default_factory=list, description="Jira Site Scopes")
    avatar_url: str | None = Field(default=None, description="Jira Site Avatar URL")


class JiraUserInfo(BaseModel):
    account_id: str
    email: str | None = None
    name: str | None = None
    picture: str | None = None


class JiraInstallationStatus(BaseModel):
    installed: bool
    resources: list[JiraAccessibleResource] = Field(default_factory=list)

class JiraOAuthCallbackResponse(BaseModel):
    status: str
    message: str
    resources_connected: int = 0
