from datetime import datetime
from email.policy import default
from enum import StrEnum, auto, unique
import time

from sqlalchemy import func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import String, Boolean, Integer, BigInteger, DateTime


class Base(DeclarativeBase):
    pass


class UserRole(StrEnum):
    USER = "user"
    ADMIN = "admin"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    given_name: Mapped[str] = mapped_column(String(50), nullable=True)
    family_name: Mapped[str] = mapped_column(String(50), nullable=True)
    picture: Mapped[str] = mapped_column(String(500), nullable=True)
    role: Mapped[UserRole] = mapped_column(
        String(20), default=UserRole.USER, server_default=str(UserRole.USER)
    )
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    refresh_token: Mapped[str] = mapped_column(String(500), nullable=True)

class JiraAccountType(StrEnum):
    ATLASSIAN = "atlassian" # 일반 사용자
    APP = "app"             # Bot
    CUSTOMER = "customer"   # Jira Service Management에서 사용하는 계정 (사용 빈도 거의 없음)

class JiraUser(Base):
    __tablename__ = "jira_users"

    cloud_id: Mapped[str] = mapped_column(
        String(128), primary_key=True, comment="Jira Cloud ID"
    )
    account_id: Mapped[str] = mapped_column(
        String(128), primary_key=True, comment="Atlassian Account ID"
    )
    account_type: Mapped[JiraAccountType] = mapped_column(
        String(20), nullable=False, comment="atlassian/app/customer"
    )
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, comment="활성 상태"
    )
    display_name: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="표시 이름"
    )
    email_address: Mapped[str | None] = mapped_column(
        String(255), nullable=True, comment="이메일 (권한에 따라 수집 불가)"
    )
    avatar_url: Mapped[str | None] = mapped_column(
        String(500), nullable=True, comment="프로필 이미지 URL"
    )
    self_url: Mapped[str | None] = mapped_column(
        String(500), nullable=True, comment="Jira API self URL"
    )
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class JiraProjectType(StrEnum):
    SOFTWARE = "software"
    BUSINESS = "business"
    SERVICE_DESK = "service_desk"


class JiraProject(Base):
    __tablename__ = "jira_projects"

    cloud_id: Mapped[str] = mapped_column(
        String(128), primary_key=True, comment="Jira Cloud ID"
    )
    project_key: Mapped[str] = mapped_column(
        String(20), primary_key=True, comment="프로젝트 키 (CATCH)"
    )
    project_id: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="Jira 내부 ID"
    )
    project_name: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="프로젝트 이름"
    )
    description: Mapped[str | None] = mapped_column(
        String(4000), nullable=True, comment="프로젝트 설명"
    )
    project_type: Mapped[JiraProjectType | None] = mapped_column(
        String(32), nullable=True, comment="software/business/service_desk"
    )
    lead_account_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True, comment="프로젝트 리드 account_id"
    )
    lead_display_name: Mapped[str | None] = mapped_column(
        String(255), nullable=True, comment="프로젝트 리드 표시 이름"
    )
    url: Mapped[str | None] = mapped_column(
        String(512), nullable=True, comment="프로젝트 URL"
    )
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class JiraSprintState(StrEnum):
    FUTURE = "future"
    ACTIVE = "active"
    CLOSED = "closed"


class JiraSprint(Base):
    __tablename__ = "jira_sprints"

    cloud_id: Mapped[str] = mapped_column(
        String(128), primary_key=True, comment="Jira Cloud ID"
    )
    sprint_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, comment="Sprint ID"
    )
    sprint_name: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="스프린트 이름"
    )
    state: Mapped[JiraSprintState | None] = mapped_column(
        String(20), nullable=True, comment="future/active/closed"
    )
    goal: Mapped[str | None] = mapped_column(
        String(2000), nullable=True, comment="스프린트 목표"
    )
    project_key: Mapped[str | None] = mapped_column(
        String(20), nullable=True, index=True, comment="연결된 프로젝트 키"
    )
    board_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="보드 ID"
    )
    start_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    end_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    complete_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class SlackWorkspace(Base):
    """
    Slack 워크스페이스 정보 (정적 데이터, RDBMS 저장)
    """
    __tablename__ = "slack_workspaces"

    id: Mapped[str] = mapped_column(String(20), primary_key=True, comment="Team ID (T123ABC)")
    name: Mapped[str] = mapped_column(String(255), nullable=False, comment="워크스페이스 이름")
    domain: Mapped[str] = mapped_column(String(255), nullable=False, comment="{domain}.slack.com")
    url: Mapped[str] = mapped_column(String(512), nullable=False, comment="https://{domain}.slack.com/")
    email_domain: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="허용 이메일 도메인")
    icon_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    enterprise_id: Mapped[str | None] = mapped_column(String(32), nullable=True, comment="Enterprise Grid ID")
    enterprise_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class SlackChannelType(StrEnum):
    PUBLIC = "public"
    PRIVATE = "private"
    DM = "dm"
    MPIM = "mpim"


class SlackChannel(Base):
    """
    Slack 채널 정보 (정적 데이터, RDBMS 저장)
    """
    __tablename__ = "slack_channels"

    id: Mapped[str] = mapped_column(String(20), primary_key=True, comment="Channel ID (C456DEF)")
    team_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True, comment="Workspace ID")
    name: Mapped[str] = mapped_column(String(255), nullable=False, comment="채널 이름")
    channel_type: Mapped[SlackChannelType] = mapped_column(
        String(16), nullable=False, comment="public/private/dm/mpim"
    )
    topic: Mapped[str | None] = mapped_column(String(1000), nullable=True, comment="채널 토픽")
    purpose: Mapped[str | None] = mapped_column(String(1000), nullable=True, comment="채널 목적")
    creator_id: Mapped[str | None] = mapped_column(String(20), nullable=True, comment="생성자 user_id")
    member_count: Mapped[int] = mapped_column(Integer, default=0, comment="멤버 수")
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, comment="아카이브 여부")
    is_private: Mapped[bool] = mapped_column(Boolean, default=False, comment="비공개 여부")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, comment="채널 생성 시간"
    )
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class SlackUser(Base):
    """
    Slack 사용자 정보 (정적 데이터, RDBMS 저장)
    """
    __tablename__ = "slack_users"

    team_id: Mapped[str] = mapped_column(String(20), primary_key=True, comment="WorkSpaceId")
    user_id: Mapped[str] = mapped_column(String(20), primary_key=True, comment="UserId")
    name: Mapped[str] = mapped_column(String(255), nullable=False, comment="Login Name Used for Mention")
    real_name: Mapped[str] = mapped_column(String(255), nullable=False, comment="실제 이름")
    deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="비활성 사용자 여부")

    # Profile
    email: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="직함")
    phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tz: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="타임존 ID")
    tz_label: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="타임존 라벨")
    is_bot: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_owner: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_restricted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="Guest User")
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="프로필 업데이트 시간"
    )
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class GitHubOrganizationRole(StrEnum):
    ADMIN = "ADMIN"
    MEMBER = "MEMBER"


class GitHubUser(Base):
    """
    TODO : Organization에서 Email Private으로 설정했을 경우 UnifiedMember Matching 계획
    TODO : USER Fetching API에서 GraphQL 적용

    - login: username (변경 가능)
    - name: display name
    - email: Public 설정 시에만 반환
    """
    __tablename__ = "github_users"

    database_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    login: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True,comment="Login ID")
    name: Mapped[str] = mapped_column(String(255), nullable=True, comment="Display Name")
    email: Mapped[str] = mapped_column(String(255), nullable=True, index=True)
    avatar_url: Mapped[str] = mapped_column(String(500), nullable=True)
    org_role: Mapped[GitHubOrganizationRole] = mapped_column(String(20), nullable=True)

class GithubInstallationType(StrEnum):
    USER = "user"
    ORGANIZATION = "organization"


class GithubRepositorySelection(StrEnum):
    ALL = "all"
    SELECTED = "selected"


class GithubInstallation(Base):
    """
    Github App Installation 정보
    - Organization Admin이 App을 설치하면 Webhook으로 Installation 정보 수신
    - Installation Access Token 발급 시 installation_id 사용
    """
    __tablename__ = "github_installation"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Github에서 발급하는 Installation ID
    installation_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    account_type: Mapped[GithubInstallationType] = mapped_column(String(20), nullable=False)
    account_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="GitHub Account ID")
    account_login: Mapped[str] = mapped_column(String(255), nullable=False, comment="Organization or User login name")
    account_avatar_url: Mapped[str] = mapped_column(String(500), nullable=True)
    repository_selection: Mapped[GithubRepositorySelection] = mapped_column(
        String(20), nullable=True, comment="all: 모든 레포 접근 / selected: 선택된 레포만"
    )

    suspended_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True, comment="일시 중지된 경우")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        nullable=False, 
        server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        nullable=False, 
        server_default=func.now(),
        onupdate=func.now()
    )

    @classmethod
    def from_webhook_payload(cls, payload: "InstallationWebhookPayload") -> "GithubInstallation":
        from catchup.connectors.github.schemas import InstallationWebhookPayload

        account = payload.installation.account
        installation = payload.installation

        # repository_selection 변환
        repo_selection = None
        if installation.repository_selection:
            repo_selection = GithubRepositorySelection(installation.repository_selection)

        return cls(
            installation_id=installation.id,
            account_type=GithubInstallationType(account.type.lower()),
            account_id=account.id,
            account_login=account.login,
            account_avatar_url=account.avatar_url,
            repository_selection=repo_selection,
            suspended_at=installation.suspended_at,
        )

class JiraOAuthToken(Base):
    __tablename__ = "jira_oauth_tokens"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    atlassian_account_id: Mapped[str] = mapped_column(String(128), nullable=False)
    cloud_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    site_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    site_url: Mapped[str |None] = mapped_column(String(500), nullable=True)

    access_token: Mapped[str] = mapped_column(String(4096), nullable=False)
    refresh_token: Mapped[str] = mapped_column(String(4096), nullable=False)
    token_type: Mapped[str] = mapped_column(String(50), default="Bearer")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, comment="Access Token 만료 시간")
    scopes: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="부여된 권한 범위")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        nullable=False, 
        server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        nullable=False, 
        server_default=func.now(),
        onupdate=func.now()
    )


class SlackOAuthToken(Base):
    """
    Slack OAuth Token 저장
    - Workspace(Team) 단위로 관리
    - Bot Token 저장 (기본적으로 만료 없음, Token Rotation 활성화 시 갱신 필요)
    """
    __tablename__ = "slack_oauth_tokens"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Workspace 식별 정보
    team_id: Mapped[str] = mapped_column(
        String(20), nullable=False, unique=True, index=True,
        comment="Slack Workspace ID"
    )
    team_name: Mapped[str | None] = mapped_column(
        String(255), nullable=True,
        comment="Slack Workspace 이름"
    )

    # Bot Token (필수)
    bot_user_id: Mapped[str] = mapped_column(
        String(20), nullable=False,
        comment="Bot User ID"
    )
    bot_access_token: Mapped[str] = mapped_column(
        String(512), nullable=False,
        comment="Bot Access Token (xoxb-)"
    )
    bot_scopes: Mapped[str] = mapped_column(
        String(1000), nullable=False,
        comment="Bot Token에 부여된 scopes"
    )

    # OAuth 인증 사용자 정보
    authed_user_id: Mapped[str | None] = mapped_column(
        String(20), nullable=True,
        comment="OAuth 인증한 사용자 ID"
    )

    bot_refresh_token: Mapped[str | None] = mapped_column(
        String(512), nullable=True,
        comment="Bot Refresh Token (Token Rotation 사용 시)"
    )
    bot_token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="Bot Token 만료 시간 (Token Rotation 사용 시)"
    )

    incoming_webhook_url: Mapped[str | None] = mapped_column(
        String(500), nullable=True,
        comment="Incoming Webhook URL"
    )
    incoming_webhook_channel: Mapped[str | None] = mapped_column(
        String(100), nullable=True,
        comment="Incoming Webhook 채널"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        server_default=func.now(), onupdate=func.now()
    )


class JiraSyncStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"


class JiraEntityType(StrEnum):
    ISSUE = "issue"
    EPIC = "epic"
    PROJECT = "project"
    SPRINT = "sprint"
    COMPONENT = "component"


class JiraSyncState(Base):
    """
    Jira 엔티티 동기화 상태 추적을 위한 테이블

    - Entity Type별로 동기화 상태 관리 -> 타입별로 병렬처리 및 재시도 가능
    - 증분 동기화 : last_successful_sync_at 기준으로 이후 변경된 엔티티만 동기화
    """
    __tablename__ = "jira_sync_states"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Jira Cloud 인스턴스 식별
    cloud_id: Mapped[str] = mapped_column(
        String(128), nullable=False, index=True,
        comment="Jira Cloud ID"
    )
    entity_type: Mapped[JiraEntityType] = mapped_column(
        String(50), nullable=False,
        comment="issue, epic, project, sprint, component"
    )

    # 동기화 상태
    last_sync_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="마지막 동기화 시작 시간"
    )
    last_successful_sync_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="마지막 성공적인 동기화 시간 (증분 동기화 기준)"
    )
    last_sync_status: Mapped[JiraSyncStatus | None] = mapped_column(
        String(20), nullable=True,
        comment="pending, in_progress, success, failed"
    )
    last_sync_error: Mapped[str | None] = mapped_column(
        String(1000), nullable=True,
        comment="마지막 에러 메시지"
    )

    # 진행 상황
    total_entities: Mapped[int] = mapped_column(
        Integer, default=0,
        comment="동기화 대상 총 엔티티 수"
    )
    synced_entities: Mapped[int] = mapped_column(
        Integer, default=0,
        comment="동기화 완료된 엔티티 수"
    )

    # 데이터 범위 (기간 제한 동기화용)
    oldest_entity_created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="동기화된 엔티티 중 가장 오래된 생성 시간 (이 시점 이후 데이터만 보유)"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        server_default=func.now(), onupdate=func.now()
    )


# ============================================================
# Slack Sync State
# ============================================================

class SlackSyncStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"


class SlackEntityType(StrEnum):
    MESSAGE = "message"
    CHANNEL = "channel"
    USER = "user"
    FILE = "file"
    WORKSPACE = "workspace"


class SlackSyncState(Base):
    """
    Slack 엔티티 동기화 상태 추적을 위한 테이블

    - Entity Type별로 동기화 상태 관리 -> 타입별로 병렬처리 및 재시도 가능
    - 증분 동기화 : last_successful_sync_at 기준으로 이후 변경된 엔티티만 동기화
    """
    __tablename__ = "slack_sync_states"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Slack Workspace 식별
    team_id: Mapped[str] = mapped_column(
        String(128), nullable=False, index=True,
        comment="Slack Team/Workspace ID"
    )
    entity_type: Mapped[SlackEntityType] = mapped_column(
        String(50), nullable=False,
        comment="message, channel, user, file, workspace"
    )

    # 동기화 상태
    last_sync_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="마지막 동기화 시작 시간"
    )
    last_successful_sync_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="마지막 성공적인 동기화 시간 (증분 동기화 기준)"
    )
    last_sync_status: Mapped[SlackSyncStatus | None] = mapped_column(
        String(20), nullable=True,
        comment="pending, in_progress, success, failed"
    )
    last_sync_error: Mapped[str | None] = mapped_column(
        String(1000), nullable=True,
        comment="마지막 에러 메시지"
    )

    # 진행 상황
    total_entities: Mapped[int] = mapped_column(
        Integer, default=0,
        comment="동기화 대상 총 엔티티 수"
    )
    synced_entities: Mapped[int] = mapped_column(
        Integer, default=0,
        comment="동기화 완료된 엔티티 수"
    )

    # 날짜 범위 (사용자 지정 동기화용)
    oldest_ts: Mapped[str | None] = mapped_column(
        String(50), nullable=True,
        comment="동기화 시작 Slack timestamp (oldest 파라미터)"
    )
    latest_ts: Mapped[str | None] = mapped_column(
        String(50), nullable=True,
        comment="동기화 종료 Slack timestamp (latest 파라미터)"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        server_default=func.now(), onupdate=func.now()
    )


class SlackChannelSyncState(Base):
    """
    Slack 채널별 메시지 동기화 상태 추적을 위한 테이블

    - 채널별로 동기화 상태 관리 -> 실패 시 해당 채널만 재시도 가능
    - last_successful_sync_at 기준으로 재시도 시작점 결정
    - SlackSyncState는 전체 동기화 상태, 이 테이블은 채널별 상세 상태
    """
    __tablename__ = "slack_channel_sync_states"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Slack Workspace 및 채널 식별
    team_id: Mapped[str] = mapped_column(
        String(128), nullable=False, index=True,
        comment="Slack Team/Workspace ID"
    )
    channel_id: Mapped[str] = mapped_column(
        String(128), nullable=False, index=True,
        comment="Slack Channel ID"
    )
    channel_name: Mapped[str | None] = mapped_column(
        String(255), nullable=True,
        comment="채널명 (디버깅/로깅용)"
    )

    # 동기화 상태
    last_sync_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="마지막 동기화 시작 시간"
    )
    last_successful_sync_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="마지막 성공적인 동기화 시간 (재시도 기준점)"
    )
    last_sync_status: Mapped[SlackSyncStatus | None] = mapped_column(
        String(20), nullable=True,
        comment="pending, in_progress, success, failed"
    )
    last_sync_error: Mapped[str | None] = mapped_column(
        String(1000), nullable=True,
        comment="마지막 에러 메시지"
    )

    # 진행 상황
    synced_count: Mapped[int] = mapped_column(
        Integer, default=0,
        comment="동기화 완료된 메시지 수"
    )

    # Slack timestamp 범위 (재시도 지원)
    oldest_ts: Mapped[str | None] = mapped_column(
        String(50), nullable=True,
        comment="동기화 시작 Slack timestamp"
    )
    latest_synced_ts: Mapped[str | None] = mapped_column(
        String(50), nullable=True,
        comment="마지막으로 성공한 메시지의 timestamp (재시도 시작점)"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        # team_id + channel_id 복합 유니크 인덱스
        {"comment": "채널별 동기화 상태 추적"},
    )


# ============================================================
# GitHub Sync State
# ============================================================

class GitHubSyncStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"


class GitHubEntityType(StrEnum):
    ISSUE = "issue"
    PULL_REQUEST = "pull_request"
    COMMIT = "commit"
    REPOSITORY = "repository"
    USER = "user"


class GitHubSyncState(Base):
    """
    GitHub 엔티티 동기화 상태 추적을 위한 테이블

    - Entity Type별로 동기화 상태 관리 -> 타입별로 병렬처리 및 재시도 가능
    - 증분 동기화 : last_successful_sync_at 기준으로 이후 변경된 엔티티만 동기화
    """
    __tablename__ = "github_sync_states"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # GitHub Installation 식별
    installation_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, index=True,
        comment="GitHub App Installation ID"
    )
    # Repository 식별 (owner/repo 형식)
    repository_full_name: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True,
        comment="Repository full name (owner/repo)"
    )
    entity_type: Mapped[GitHubEntityType] = mapped_column(
        String(50), nullable=False,
        comment="issue, pull_request, commit, repository"
    )

    # 동기화 상태
    last_sync_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="마지막 동기화 시작 시간"
    )
    last_successful_sync_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="마지막 성공적인 동기화 시간 (증분 동기화 기준)"
    )
    last_sync_status: Mapped[GitHubSyncStatus | None] = mapped_column(
        String(20), nullable=True,
        comment="pending, in_progress, success, failed"
    )
    last_sync_error: Mapped[str | None] = mapped_column(
        String(1000), nullable=True,
        comment="마지막 에러 메시지"
    )

    # 진행 상황
    total_entities: Mapped[int] = mapped_column(
        Integer, default=0,
        comment="동기화 대상 총 엔티티 수"
    )
    synced_entities: Mapped[int] = mapped_column(
        Integer, default=0,
        comment="동기화 완료된 엔티티 수"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        server_default=func.now(), onupdate=func.now()
    )


class GitHubRepository(Base):
    """
    GitHub Repository 정보 (정적 데이터, RDBMS 저장)
    - Installation에 연결된 Repository 목록 관리
    """
    __tablename__ = "github_repositories"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Installation 연결
    installation_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, index=True,
        comment="GitHub App Installation ID"
    )

    # Repository 식별
    repo_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, unique=True,
        comment="GitHub Repository ID"
    )
    owner: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True,
        comment="Repository owner (user or org)"
    )
    name: Mapped[str] = mapped_column(
        String(255), nullable=False,
        comment="Repository name"
    )
    full_name: Mapped[str] = mapped_column(
        String(512), nullable=False, unique=True, index=True,
        comment="Full name (owner/repo)"
    )

    # Repository 정보
    description: Mapped[str | None] = mapped_column(
        String(2000), nullable=True,
        comment="Repository description"
    )
    html_url: Mapped[str] = mapped_column(
        String(512), nullable=False,
        comment="Repository URL"
    )
    default_branch: Mapped[str] = mapped_column(
        String(255), nullable=False, default="main",
        comment="Default branch name"
    )
    language: Mapped[str | None] = mapped_column(
        String(100), nullable=True,
        comment="Primary programming language"
    )
    topics: Mapped[str | None] = mapped_column(
        String(1000), nullable=True,
        comment="Repository topics (JSON array as string)"
    )

    # 통계
    stargazers_count: Mapped[int] = mapped_column(
        Integer, default=0, comment="Star count"
    )
    forks_count: Mapped[int] = mapped_column(
        Integer, default=0, comment="Fork count"
    )
    open_issues_count: Mapped[int] = mapped_column(
        Integer, default=0, comment="Open issues count"
    )

    # 상태
    private: Mapped[bool] = mapped_column(
        Boolean, default=False, comment="Private repository"
    )
    archived: Mapped[bool] = mapped_column(
        Boolean, default=False, comment="Archived repository"
    )
    disabled: Mapped[bool] = mapped_column(
        Boolean, default=False, comment="Disabled repository"
    )

    # 시간
    pushed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="마지막 push 시간"
    )
    repo_created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="Repository 생성 시간"
    )
    repo_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="Repository 업데이트 시간"
    )
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )