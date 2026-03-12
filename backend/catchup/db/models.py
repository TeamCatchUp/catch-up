import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any, Optional
from sqlalchemy import CheckConstraint, ForeignKey, Index, UniqueConstraint, func, inspect, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import String, Boolean, Integer, BigInteger, DateTime, Text


class Base(DeclarativeBase):
    def to_snapshot(self):
        ins = inspect(self)
        data = {c.key: getattr(self, c.key) for c in ins.mapper.column_attrs}
        data["__type__"] = self.__class__.__name__
        
        for rel in ins.mapper.relationships:
            if rel.key not in ins.unloaded:
                value = getattr(self, rel.key)
                if value is None:
                    data[rel.key] = None
                elif isinstance(value, list):
                    data[rel.key] =[i.to_snapshot() for i in value]
                else:
                    data[rel.key] = value.to_snapshot()
                    
        return data


class UserRole(StrEnum):
    USER = "user"
    ADMIN = "admin"
    

class CompanySize(StrEnum):
    SMALL = "small"  # 1 ~ 5인
    MEDIUM = "medium" # 6 ~ 20인
    LARGE = "large"  # 51 ~ 100인
    ENTERPRISE = "enterprise"  # 100인 이상


class JobLevel(StrEnum):
    EXECUTIVE = "executive"  # 경영진
    LEADER = "leader"  # 팀장
    MEMBER = "member"  # 팀원


class UserStatus(StrEnum):
    NEW = "new"  # Oauth 로그인만 마친 상태
    ACTIVE = "active"  # 회원가입 후 승인 완료 상태
    INACTIVE = "inactive"  # 관리자에 의해 비활성화된 상태
    DELETED = "deleted" # 관리자에 의해 삭제된 상태


class Company(Base):
    __tablename__ = "companies"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=True)
    size: Mapped[CompanySize] = mapped_column(String(20), nullable=False, server_default=text(f"'{CompanySize.SMALL.value}'"))
    location: Mapped[str] = mapped_column(String(255), nullable=True)
    logo_url: Mapped[str] = mapped_column(String(500), nullable=True)
    
    workspaces: Mapped[list["Workspace"]] = relationship(back_populates="company")


class Workspace(Base):
    __tablename__ = "workspaces"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
    
    company: Mapped["Company"] = relationship(back_populates="workspaces")
    user_links: Mapped[list["UserWorkspace"]] = relationship(
        back_populates="workspace",
        cascade="all, delete-orphan"
    )
    users: Mapped[list["User"]] = association_proxy("user_links", "user")
    knowledge_sources: Mapped[list["KnowledgeSource"]] = relationship(back_populates="workspace")


class User(Base):
    __tablename__ = "users"

    # Columns   
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    given_name: Mapped[str] = mapped_column(String(50), nullable=True)
    family_name: Mapped[str] = mapped_column(String(50), nullable=True)
    picture: Mapped[str] = mapped_column(String(500), nullable=True)
    role: Mapped[UserRole] = mapped_column(
        String(20),
        default=UserRole.USER,
        server_default=text(f"'{UserRole.USER}'")
    )
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    refresh_token: Mapped[str] = mapped_column(String(500), nullable=True)
    
    department: Mapped[str] = mapped_column(
        String(50), 
        nullable=False, 
        default="unregistered", 
        server_default=text("'unregistered'")
    )
    job_level: Mapped[JobLevel] = mapped_column(
        String(20), 
        nullable=False, 
        default=JobLevel.MEMBER, 
        server_default=text(f"'{JobLevel.MEMBER}'")
    )
    status: Mapped[UserStatus] = mapped_column(String(10), nullable=False)
    custom_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    
    # Objects
    workspace_links: Mapped[list["UserWorkspace"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan"
    )
    workspaces: Mapped[list["Workspace"]] = association_proxy("workspace_links", "workspace")
    oauth_user: Mapped["OAuthUser"] = relationship(back_populates="user")


class InactiveUser(Base):
    __tablename__ = "inactive_users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    deactivated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    reactivated: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    admin_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    __table_args__ = (
        UniqueConstraint("user_id", "deactivated_at", name="uq_inactive_user_timestamp"),
        Index("idx_inactive_users_user_id", "user_id"),
    )

class UserWorkspace(Base):
    __tablename__ = "user_workspaces"
    
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), primary_key=True)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    
    user: Mapped["User"] = relationship(back_populates="workspace_links")
    workspace: Mapped["Workspace"] = relationship(back_populates="user_links")


class SourceType(StrEnum):
    CONFLUENCE = "confluence"
    JIRA = "jira"
    GITHUB = "github"
    SLACK = "slack"


class KnowledgeSource(Base):
    __tablename__ = "knowledge_sources"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), nullable=False)
    source_type: Mapped[SourceType] = mapped_column(String(20), nullable=False)
    display_name: Mapped[str] = mapped_column(String(20), nullable=False)
    external_identifier: Mapped[str] = mapped_column(String(128), nullable=False, index=True)  # 논리적 연결
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    
    workspace: Mapped["Workspace"] = relationship(back_populates="knowledge_sources")    

    
class UserSourceMapping(Base):
    __tablename__ = "user_source_mappings"
       
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    source_type: Mapped[SourceType] = mapped_column(String(20), nullable=False)
    
    external_user_identifier: Mapped[str] = mapped_column(String(128), nullable=False)
    
    __table_args__ = (
        UniqueConstraint("user_id", "source_type", name="uq_user_source"),
    )


class PreMappingBuffer(Base):
    __tablename__ = "pre_mapping_buffers"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    
    sub: Mapped[str] = mapped_column(String(128), nullable=False)
    email: Mapped[str] = mapped_column(String(255), index=True, comment="OAuth 사용자 이메일 (예: Keycloak 이메일)")
    name: Mapped[str] = mapped_column(String(100), comment="IDP에 등록된 임직원 실명") 
    
    source_type: Mapped[SourceType] = mapped_column(String(20), nullable=False)
    
    # Slack: user_id
    # Github: login_id
    # Atlassian: account_id
    external_user_identifier: Mapped[str] = mapped_column(String(128), nullable=False)
    
    is_registered: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    
    # (사내 이메일, 툴 종류) 중복 방지
    __table_args__ = (
        UniqueConstraint("email", "source_type", name="uq_email_source_buffer"),
    )


class OAuthUser(Base):
    __tablename__ = "oauth_users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    sub: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    email: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    picture: Mapped[str] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=True)
    
    user: Mapped["User"] = relationship(back_populates="oauth_user")


# =================
# Integration
# =================
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
 
class SlackChannelMember(Base):
    """
    Slack Channel - User 매핑 테이블
    """
    __tablename__ = "slack_channel_members"

    team_id: Mapped[str] = mapped_column(
        String(20), primary_key=True, comment="WorkspaceID"
    )
    channel_id: Mapped[str] = mapped_column(
        String(20), primary_key=True, comment="ChannelID"
    )
    user_id: Mapped[str] = mapped_column(
        String(20), primary_key=True, comment="UserID"
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

class AtlassianOAuthToken(Base):
    __tablename__ = "atlassian_oauth_tokens"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    atlassian_account_id: Mapped[str] = mapped_column(String(128), nullable=False)
    cloud_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    site_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    site_url: Mapped[str |None] = mapped_column(String(500), nullable=True)

    access_token: Mapped[str] = mapped_column(String(4096), nullable=False)
    refresh_token: Mapped[str] = mapped_column(String(4096), nullable=False)
    token_type: Mapped[str] = mapped_column(String(50), default="Bearer")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, comment="Access Token 만료 시간")

    scopes: Mapped[str | None] = mapped_column(String(1000), nullable=True, comment="Jira + Confluence + Atlassian 공통 Scope 포함")
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

class ConfluenceSpace(Base):
    """
    Confluence Space Metadata
    """
    __tablename__ = "confluence_spaces"

    cloud_id: Mapped[str] = mapped_column(
        String(128), primary_key=True
    )
    space_id: Mapped[str] = mapped_column(
        String(32), primary_key=True
    )
    space_key: Mapped[str] = mapped_column(
        String(128), nullable=False
    )
    space_name: Mapped[str] = mapped_column(
        String(255), nullable=False
    )
    space_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False
    )
    homepage_id: Mapped[str | None] = mapped_column(
        String(32), nullable=True
    )
    description: Mapped[str | None] = mapped_column(
        String(2000), nullable=True
    )
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ConfluenceUser(Base):
    """
    Confluence User Metadata
    """

    __tablename__ = "confluence_users"

    cloud_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    account_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    account_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    public_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    time_zone: Mapped[str | None] = mapped_column(String(100), nullable=True)
    locale: Mapped[str | None] = mapped_column(String(50), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_external_collaborator: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


# ============================================================
# Confluence Sync State
# ============================================================

class ConfluenceSyncStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"


class ConfluenceEntityType(StrEnum):
    PAGE = "page"
    BLOGPOST = "blogpost"


class ConfluenceSyncState(Base):
    """
    Confluence Space별 동기화 상태 추적 테이블

    - Space + Entity Type별로 동기화 상태 관리 -> 타입별로 병렬처리 및 재시도 가능
    - 증분 동기화 : last_successful_sync_at 기준으로 이후 변경된 엔티티만 동기화
    """
    __tablename__ = "confluence_sync_states"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Atlassian Cloud + Space 식별
    cloud_id: Mapped[str] = mapped_column(
        String(128), nullable=False, index=True,
        comment="Atlassian Cloud ID"
    )
    space_key: Mapped[str] = mapped_column(
        String(128), nullable=False,
        comment="Confluence Space Key"
    )
    entity_type: Mapped[ConfluenceEntityType] = mapped_column(
        String(50), nullable=False,
        comment="page, blogpost"
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
    last_sync_status: Mapped[ConfluenceSyncStatus | None] = mapped_column(
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


class JiraWebhookSubscription(Base):
    """
    Jira Dynamic Webhook 등록 상태 저장

    cloud_id 단위로 등록된 webhook ID와 만료 시각을 관리한다.
    """
    __tablename__ = "jira_webhook_subscriptions"
    __table_args__ = (
        UniqueConstraint(
            "cloud_id",
            "webhook_id",
            name="uq_jira_webhook_subscriptions_cloud_webhook",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    cloud_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    webhook_id: Mapped[int] = mapped_column(Integer, nullable=False)

    callback_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    jql_filter: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    events_csv: Mapped[str | None] = mapped_column(String(2000), nullable=True)

    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
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
    project_key: Mapped[str | None] = mapped_column(
        String(50), nullable = True, index = True,
        comment = "Jira Project Key",
    )
    entity_type: Mapped[JiraEntityType] = mapped_column(
        String(50), nullable=False,
        comment="issue, epic, project, sprint"
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

class GithubSyncStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"


class GithubEntityType(StrEnum):
    ISSUE = "issue"
    PULL_REQUEST = "pull_request"
    COMMIT = "commit"
    REPOSITORY = "repository"
    USER = "user"


class GithubSyncState(Base):
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
    entity_type: Mapped[GithubEntityType] = mapped_column(
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
    last_sync_status: Mapped[GithubSyncStatus | None] = mapped_column(
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


class GithubRepository(Base):
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
# ===========
# Common Full Sync Job/Event
# ===========
class SyncConnector(StrEnum):
    SLACK = "slack"
    GITHUB = "github"
    JIRA = "jira"
    CONFLUENCE = "confluence"


class SyncType(StrEnum):
    FULL = "full"
    INCREMENTAL = "incremental"


class SyncJobStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"


class SyncEventStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"
    RETRYING = "retrying"


class SyncEventPublishStatus(StrEnum):
    PENDING = "pending"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    FAILED = "failed"


class IncrementalRecordStatus(StrEnum):
    DEBOUNCING = "debouncing"
    QUEUED = "queued"
    PROCESSING = "processing"
    RETRY_WAIT = "retry_wait"
    DEAD = "dead"
    SYNCED = "synced"


class IncrementalOutboxStatus(StrEnum):
    PENDING = "pending"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    SKIPPED = "skipped"
    FAILED = "failed"

class SyncJob(Base):
    __tablename__ = "sync_jobs"

    job_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    connector: Mapped[SyncConnector] = mapped_column(String(32), nullable=False)
    sync_type: Mapped[SyncType] = mapped_column(String(16), nullable=False)
    scope_id: Mapped[str] = mapped_column(String(255), nullable=False)

    status: Mapped[SyncJobStatus] = mapped_column(
        String(20),
        nullable=False,
        default=SyncJobStatus.PENDING,
        server_default=text("'pending'"),
    )

    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    succeeded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    embedding_tokens_used: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default=text("0")
    )
    summary_tokens_used: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default=text("0")
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    
    events: Mapped[list["SyncEvent"]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'in_progress', 'success', 'failed')",
            name="ck_sync_jobs_status",
        ),
        Index(
            "idx_sync_jobs_connector_status_requested_at",
            "connector",
            "status",
            "requested_at",
        ),
        Index(
            "idx_sync_jobs_scope_id_requested_at",
            "scope_id",
            "requested_at",
        ),
    )

    
class SyncEvent(Base):
    __tablename__ = "sync_events"

    event_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    job_id: Mapped[str] = mapped_column(
        ForeignKey("sync_jobs.job_id", ondelete="CASCADE"),
        nullable=False,
    )
    connector: Mapped[SyncConnector] = mapped_column(String(32), nullable=False)

    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(255), nullable=False)
    resource_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )

    status: Mapped[SyncEventStatus] = mapped_column(
        String(20),
        nullable=False,
        default=SyncEventStatus.PENDING,
        server_default=text("'pending'"),
    )
    publish_status: Mapped[SyncEventPublishStatus] = mapped_column(
        String(20),
        nullable=False,
        default=SyncEventPublishStatus.PENDING,
        server_default=text(f"'{SyncEventPublishStatus.PENDING.value}'"),
    )
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3, server_default=text("3"))
    publish_attempt: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )

    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    succeeded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    embedding_tokens_used: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default=text("0")
    )
    summary_tokens_used: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default=text("0")
    )
    stream_message_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    publish_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    job: Mapped["SyncJob"] = relationship(back_populates="events")

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'in_progress', 'success', 'failed', 'retrying')",
            name="ck_sync_events_status",
        ),
        CheckConstraint(
            "publish_status IN ('pending', 'publishing', 'published', 'failed')",
            name="ck_sync_events_publish_status",
        ),
        CheckConstraint("attempt >= 0", name="ck_sync_events_attempt_non_negative"),
        CheckConstraint("max_attempts >= 1", name="ck_sync_events_max_attempts_positive"),
        CheckConstraint("attempt <= max_attempts", name="ck_sync_events_attempt_lte_max"),
        CheckConstraint("publish_attempt >= 0", name="ck_sync_events_publish_attempt_non_negative"),
        Index("idx_sync_events_job_id_status", "job_id", "status"),
        Index(
            "idx_sync_events_connector_status_requested_at",
            "connector",
            "status",
            "requested_at",
        ),
        Index("idx_sync_events_job_id_requested_at", "job_id", "requested_at"),
        Index(
            "idx_sync_events_publish_status_requested_at",
            "publish_status",
            "requested_at",
        ),
    )


class IncrementalRecordState(Base):
    __tablename__ = "incremental_record_states"

    record_key: Mapped[str] = mapped_column(String(255), primary_key=True)
    connector: Mapped[SyncConnector] = mapped_column(String(32), nullable=False)
    scope_id: Mapped[str] = mapped_column(String(255), nullable=False)
    record_type: Mapped[str] = mapped_column(String(64), nullable=False)
    record_id: Mapped[str] = mapped_column(String(255), nullable=False)
    parent_type: Mapped[str] = mapped_column(String(64), nullable=False)
    parent_id: Mapped[str] = mapped_column(String(255), nullable=False)
    event_kind: Mapped[str] = mapped_column(String(32), nullable=False)

    status: Mapped[IncrementalRecordStatus] = mapped_column(
        String(20),
        nullable=False,
        default=IncrementalRecordStatus.DEBOUNCING,
        server_default=text(f"'{IncrementalRecordStatus.DEBOUNCING.value}'"),
    )
    generation: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default=text("1"),
    )
    attempt: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )

    last_event_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    debounce_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    queued_generation: Mapped[int | None] = mapped_column(Integer, nullable=True)
    processing_generation: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    lease_owner: Mapped[str | None] = mapped_column(String(255), nullable=True)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    outbox_entries: Mapped[list["IncrementalStreamOutbox"]] = relationship(
        back_populates="record",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('debouncing', 'queued', 'processing', 'retry_wait', 'dead', 'synced')",
            name="ck_incremental_record_states_status",
        ),
        CheckConstraint("generation >= 1", name="ck_incremental_record_states_generation_positive"),
        CheckConstraint("attempt >= 0", name="ck_incremental_record_states_attempt_non_negative"),
        CheckConstraint(
            "queued_generation IS NULL OR queued_generation >= 1",
            name="ck_incremental_record_states_queued_generation_positive",
        ),
        CheckConstraint(
            "processing_generation IS NULL OR processing_generation >= 1",
            name="ck_incremental_record_states_processing_generation_positive",
        ),
        Index(
            "idx_incremental_record_states_connector_status_debounce_until",
            "connector",
            "status",
            "debounce_until",
        ),
        Index(
            "idx_incremental_record_states_connector_status_next_retry_at",
            "connector",
            "status",
            "next_retry_at",
        ),
        Index(
            "idx_incremental_record_states_parent_status",
            "connector",
            "scope_id",
            "parent_type",
            "parent_id",
            "status",
        ),
        Index(
            "idx_incremental_record_states_scope_updated_at",
            "scope_id",
            "updated_at",
        ),
    )


class IncrementalStreamOutbox(Base):
    __tablename__ = "incremental_stream_outbox"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    record_key: Mapped[str] = mapped_column(
        ForeignKey("incremental_record_states.record_key", ondelete="CASCADE"),
        nullable=False,
    )
    generation: Mapped[int] = mapped_column(Integer, nullable=False)
    connector: Mapped[SyncConnector] = mapped_column(String(32), nullable=False)
    scope_id: Mapped[str] = mapped_column(String(255), nullable=False)
    parent_type: Mapped[str] = mapped_column(String(64), nullable=False)
    parent_id: Mapped[str] = mapped_column(String(255), nullable=False)
    event_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[IncrementalOutboxStatus] = mapped_column(
        String(20),
        nullable=False,
        default=IncrementalOutboxStatus.PENDING,
        server_default=text(f"'{IncrementalOutboxStatus.PENDING.value}'"),
    )
    attempt: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    stream_message_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    record: Mapped["IncrementalRecordState"] = relationship(back_populates="outbox_entries")

    __table_args__ = (
        UniqueConstraint(
            "record_key",
            "generation",
            name="uq_incremental_stream_outbox_record_generation",
        ),
        CheckConstraint(
            "status IN ('pending', 'publishing', 'published', 'skipped', 'failed')",
            name="ck_incremental_stream_outbox_status",
        ),
        CheckConstraint("generation >= 1", name="ck_incremental_stream_outbox_generation_positive"),
        CheckConstraint("attempt >= 0", name="ck_incremental_stream_outbox_attempt_non_negative"),
        Index(
            "idx_incremental_stream_outbox_status_created_at",
            "status",
            "created_at",
        ),
        Index(
            "idx_incremental_stream_outbox_connector_status_created_at",
            "connector",
            "status",
            "created_at",
        ),
    )


    
# ===========
# RAG Chat
# ===========
class ChatRoom(Base):
    __tablename__ = "chat_rooms"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        unique=True,
        index=True,
        default=uuid.uuid4
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    
    title: Mapped[str] = mapped_column(String(50), nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )
    
    chat_histories: Mapped[list["ChatHistory"]] = relationship(
        back_populates="chat_room",
        cascade="all, delete-orphan",
        order_by="ChatHistory.created_at"
    )


class SenderType(StrEnum):
    HUMAN = "human"
    ASSISTANT = "assistant"


class FeedbackLiteral(StrEnum):
    HALLUCINATION = "HALLUCINATION"
    OUTDATED = "OUTDATED"
    NO_CITATION = "NO_CITATION"
    MISSING_INFO = "MISSING_INFO"
    IRRELEVANT_SOURCE = "IRRELEVANT_SOURCE"
    IRRELEVANT_ANSWER = "IRRELEVANT_ANSWER"
    TOO_LONG = "TOO_LONG"
    OTHER = "OTHER"


class ChatHistory(Base):
    __tablename__ = "chat_histories"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    chat_room_id: Mapped[int] = mapped_column(
        ForeignKey("chat_rooms.id"), 
        nullable=False,
        index=True
    )
    
    content: Mapped[str] = mapped_column(Text, nullable=True)
    sender_type: Mapped[SenderType] = mapped_column(String(20), nullable=False)
    sources: Mapped[Optional[list[dict[str, Any]]]] = mapped_column(
        JSONB,
        nullable=True,
        server_default=text("'[]'::jsonb")
    )
    
    is_liked: Mapped[Optional[bool]] = mapped_column(
        Boolean,
        nullable=True,
        default=None,
        comment="True: 긍정, False: 부정, None: 평가 없음"
    )
    
    feedback_reasons: Mapped[Optional[list[str]]] = mapped_column(
        JSONB,
        nullable=True,
        server_default=text("'[]'::jsonb"),
        comment="사용자가 선택한 부정 피드백 사유 목록 (Json Array)"
    )
    
    feedback_comment: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="사용자가 직접 작성한 상세 피드백 내용"
    )
    
    is_displayed: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default=text("true"),
        nullable=False,
        comment="사용자가 수정한 쿼리인 경우에만 False이며 화면에 노출되지 않음."
    )
    
    is_saved: Mapped[bool] = mapped_column(
        Boolean, 
        default=False, 
        server_default=text("false"),
        nullable=False,
        index=True,
        comment="사용자가 저장한 답변"
    )
    
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    
    chat_room: Mapped["ChatRoom"] = relationship(back_populates="chat_histories")
    
    @property
    def session_id(self) -> uuid.UUID:
        return self.chat_room.session_id
    
    __table_args__ = (
        Index(
            "ix_chat_histories_is_saved_true",
            "is_saved",
            postgresql_where=text("is_saved IS TRUE") # 내부에서는 문자열이나 text() 권장
        ),
        
        Index(
            "idx_chat_history_content_bigm",
            "content",
            postgresql_using="gin",
            postgresql_ops={"content": "gin_bigm_ops"}
        ),
    )
