import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any
from typing import Optional

from sqlalchemy import CheckConstraint
from sqlalchemy import ForeignKey
from sqlalchemy import Index
from sqlalchemy import UniqueConstraint
from sqlalchemy import func
from sqlalchemy import inspect
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship
from sqlalchemy.types import BigInteger
from sqlalchemy.types import Boolean
from sqlalchemy.types import DateTime
from sqlalchemy.types import Integer
from sqlalchemy.types import String
from sqlalchemy.types import Text


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


class UserRoleHistoryAction(StrEnum):
    PROMOTE = "promote"
    REVOKE = "revoke"


class UserStatusHistoryAction(StrEnum):
    DEACTIVATE = "deactivate"
    DELETE = "delete"


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
    prompt_settings: Mapped[Optional["UserPromptSetting"]] = relationship(
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )


class JobRole(StrEnum):
    PM = "기획자 (PM)"
    DEVELOPER = "개발자"
    DESIGNER = "디자이너"
    CS_OPERATIONS = "CS·운영"
    MANAGEMENT_STRATEGY = "경영·전략"
    SALES = "세일즈"
    CUSTOM = "직접 입력"


class SelectedOption(StrEnum):
    INCLUDE_TERMINOLOGY = "용어 설명 포함"
    INCLUDE_WORK_CONTEXT = "작업 배경 설명"
    AUTO_SHOW_ASSIGNEE = "담당자 자동 표시"
    ATTACH_SIMILAR_CASES = "유사 사례 첨부"
    SPECIFY_IMPL_SCOPE = "구현 영향 범위 명시"
    SPECIFY_UX_IMPACT = "화면·UX 영향 명시"


class UserPromptSetting(Base):
    __tablename__ = "user_prompt_settings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, nullable=False)
    
    job_role: Mapped[str | None] = mapped_column(String(50), nullable=True)
    custom_job_text: Mapped[str | None] = mapped_column(String(50), nullable=True)
    job_description: Mapped[str | None] = mapped_column(String(200), nullable=True)
    selected_options: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    custom_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="prompt_settings")


class UserRoleHistory(Base):
    __tablename__ = "user_role_histories"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    actor_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    action: Mapped[UserRoleHistoryAction] = mapped_column(String(20), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    before_role: Mapped[UserRole] = mapped_column(String(20), nullable=False)
    after_role: Mapped[UserRole] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("idx_user_role_histories_user_created_at", "user_id", "created_at"),
    )


class UserStatusHistory(Base):
    __tablename__ = "user_status_histories"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    actor_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    action: Mapped[UserStatusHistoryAction] = mapped_column(String(20), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    before_status: Mapped[UserStatus] = mapped_column(String(20), nullable=False)
    after_status: Mapped[UserStatus] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("idx_user_status_histories_user_created_at", "user_id", "created_at"),
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
    CHANNEL_TALK = "channel_talk"


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
    # Channel Talk: manager_id
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
# Workflow Studio Credentials
# =================
class WorkflowCredentialVendor(StrEnum):
    GITHUB = "github"
    SLACK = "slack"
    ATLASSIAN = "atlassian"
    CHANNEL_TALK = "channel_talk"


class WorkflowCredentialAuthType(StrEnum):
    OAUTH2_USER = "oauth2_user"
    BOT_TOKEN = "bot_token"
    APP_INSTALLATION = "app_installation"
    API_TOKEN = "api_token"
    SERVICE_ACCOUNT = "service_account"
    PERSONAL_ACCESS_TOKEN = "personal_access_token"


class WorkflowCredentialOwnershipType(StrEnum):
    WORKSPACE_SHARED = "workspace_shared"
    USER_PERSONAL = "user_personal"


class WorkflowCredentialStatus(StrEnum):
    ACTIVE = "active"
    NEEDS_REAUTH = "needs_reauth"
    EXPIRED = "expired"
    REVOKED = "revoked"
    ERROR = "error"


class WorkflowCredential(Base):
    """
    Workflow Studio에서 사용하는 공통 Credential 저장소.

    Credential은 안전한 기본값으로 개인 소유를 기본값으로 하며, 전사 공유
    Credential은 명시적으로 workspace_shared ownership을 지정해야 한다.
    """
    __tablename__ = "workflow_credentials"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)

    vendor: Mapped[WorkflowCredentialVendor] = mapped_column(String(32), nullable=False)
    auth_type: Mapped[WorkflowCredentialAuthType] = mapped_column(String(32), nullable=False)

    ownership_type: Mapped[WorkflowCredentialOwnershipType] = mapped_column(
        String(32),
        nullable=False,
        default=WorkflowCredentialOwnershipType.USER_PERSONAL,
        server_default=text(f"'{WorkflowCredentialOwnershipType.USER_PERSONAL.value}'"),
        comment="workspace_shared: 전사 공유 / user_personal: 개인 소유",
    )

    # CatchUp Workspace / User
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), nullable=False)
    owner_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
        comment="user_personal Credential 소유자",
    )
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
        index=True,
        comment="Credential을 등록한 사용자",
    )

    # External Workspace / User
    external_tenant_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Slack team_id, Atlassian cloud_id, GitHub installation/account/server 식별자",
    )
    external_tenant_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    external_account_id: Mapped[str] = mapped_column(String(255), nullable=False)
    external_account_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    external_account_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    server_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    scopes: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
        comment="Vendor에서 부여한 OAuth/API 권한 목록",
    )
    capabilities: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
        comment="Runtime에 해당 Credential으로 할 수 있는 행동",
    )
    encrypted_data: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
        comment="암호화된 access_token, refresh_token, API token, webhook URL 등",
    )
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
        comment="vendor별 보조 메타데이터",
    )

    status: Mapped[WorkflowCredentialStatus] = mapped_column(
        String(32),
        nullable=False,
        default=WorkflowCredentialStatus.ACTIVE,
        server_default=text(f"'{WorkflowCredentialStatus.ACTIVE.value}'"),
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    workspace: Mapped["Workspace"] = relationship()
    owner_user: Mapped[Optional["User"]] = relationship(foreign_keys=[owner_user_id])
    created_by_user: Mapped[Optional["User"]] = relationship(foreign_keys=[created_by_user_id])

    __table_args__ = (
        CheckConstraint(
            "vendor IN ('github', 'slack', 'atlassian', 'channel_talk')",
            name="ck_workflow_credentials_vendor",
        ),
        CheckConstraint(
            "auth_type IN ("
            "'oauth2_user', "
            "'bot_token', "
            "'app_installation', "
            "'api_token', "
            "'service_account', "
            "'personal_access_token'"
            ")",
            name="ck_workflow_credentials_auth_type",
        ),
        CheckConstraint(
            "ownership_type IN ('workspace_shared', 'user_personal')",
            name="ck_workflow_credentials_ownership_type",
        ),
        CheckConstraint(
            "status IN ('active', 'needs_reauth', 'expired', 'revoked', 'error')",
            name="ck_workflow_credentials_status",
        ),
        CheckConstraint(
            "("
            "ownership_type = 'user_personal' AND owner_user_id IS NOT NULL"
            ") OR ("
            "ownership_type = 'workspace_shared' AND owner_user_id IS NULL"
            ")",
            name="ck_workflow_credentials_owner_matches_ownership",
        ),
        Index(
            "uq_workflow_credentials_workspace_shared_identity",
            "vendor",
            "auth_type",
            "workspace_id",
            "external_tenant_id",
            "external_account_id",
            unique=True,
            postgresql_where=text("ownership_type = 'workspace_shared'"),
        ),
        Index(
            "uq_workflow_credentials_user_personal_identity",
            "vendor",
            "auth_type",
            "workspace_id",
            "owner_user_id",
            "external_tenant_id",
            "external_account_id",
            unique=True,
            postgresql_where=text("ownership_type = 'user_personal'"),
        ),
        Index(
            "idx_workflow_credentials_workspace_owner_user",
            "workspace_id",
            "owner_user_id",
        ),
        Index(
            "idx_workflow_credentials_workspace_ownership_vendor_status",
            "workspace_id",
            "ownership_type",
            "vendor",
            "status",
        ),
    )


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


class ChannelTalkCredentials(Base):
    __tablename__ = "channel_talk_credentials"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    channel_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        comment="Validated Channel Talk channel ID",
    )
    channel_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Validated Channel Talk channel name",
    )
    access_key: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
        comment="Channel Talk access key",
    )
    access_secret: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
        comment="Channel Talk access secret",
    )
    webhook_token: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
        comment="CatchUp-managed webhook token",
    )
    credential_last_verified_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Last successful credential validation time",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        UniqueConstraint(
            "channel_id",
            name="uq_channel_talk_credentials_channel_id",
        ),
    )


class ChannelTalkDocumentCredentials(Base):
    __tablename__ = "channel_talk_document_credentials"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    channel_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        comment="Locally associated Channel Talk channel ID",
    )
    space_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        comment="Validated Channel Talk Documents space ID",
    )
    space_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Validated Channel Talk Documents space name",
    )
    access_key: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
        comment="Channel Talk Documents access key",
    )
    access_secret: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
        comment="Channel Talk Documents access secret",
    )
    credential_last_verified_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Last successful Documents credential validation time",
    )
    association_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="api_verified/local_trusted/unverified/failed",
    )
    polling_cycle_hours: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default=text("1"),
        comment="Document Space incremental polling cycle in hours",
    )
    last_incremental_polled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last completed incremental poll time",
    )
    last_incremental_poll_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last started incremental poll time",
    )
    last_incremental_poll_error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Last incremental poll error summary",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        UniqueConstraint(
            "space_id",
            name="uq_channel_talk_document_credentials_space_id",
        ),
        Index(
            "idx_channel_talk_document_credentials_channel_id",
            "channel_id",
        ),
        CheckConstraint(
            "association_status IN ('api_verified', 'local_trusted', 'unverified', 'failed')",
            name="ck_channel_talk_document_credentials_association_status",
        ),
    )


class ChannelTalkChannel(Base):
    __tablename__ = "channel_talk_channels"

    channel_id: Mapped[str] = mapped_column(
        String(128),
        primary_key=True,
        comment="Channel Talk channel ID",
    )
    channel_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Channel Talk channel name",
    )
    description: Mapped[str | None] = mapped_column(
        String(2000),
        nullable=True,
        comment="Channel description",
    )
    bot_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Default bot display name",
    )
    homepage_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="Channel homepage URL",
    )
    domain: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Channel custom domain",
    )
    subdomain: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Channel subdomain",
    )
    avatar_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="Channel avatar URL",
    )
    country: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        comment="Channel country code or country label",
    )
    time_zone: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Channel time zone",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="Metadata row creation time",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="Metadata row last update time",
    )


class ChannelTalkManager(Base):
    __tablename__ = "channel_talk_managers"


    channel_id: Mapped[str] = mapped_column(
        String(128),
        primary_key=True,
        comment="Owning Channel Talk channel ID",
    )
    manager_id: Mapped[str] = mapped_column(
        String(128),
        primary_key=True,
        comment="Channel Talk manager ID",
    )
    account_id: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
        comment="Account ID linked to the manager",
    )
    name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Manager display name",
    )
    description: Mapped[str | None] = mapped_column(
        String(2000),
        nullable=True,
        comment="Manager description",
    )
    email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
        comment="Manager email address",
    )
    mobile_number: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        comment="Manager mobile number",
    )
    role_id: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Manager role ID",
    )
    removed: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
        comment="Whether the manager has been removed",
    )
    display_as_channel: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
        comment="Whether the manager is displayed as the channel",
    )
    avatar_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="Manager avatar URL",
    )
    remote_created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Manager created timestamp from Channel Talk",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="Metadata row creation time",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="Metadata row last update time",
    )


class ChannelTalkGroup(Base):
    __tablename__ = "channel_talk_groups"

    channel_id: Mapped[str] = mapped_column(
        String(128),
        primary_key=True,
        comment="Owning Channel Talk channel ID",
    )
    group_id: Mapped[str] = mapped_column(
        String(128),
        primary_key=True,
        comment="Channel Talk group ID",
    )
    group_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Group name",
    )
    scope: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Group scope returned by Channel Talk",
    )
    description: Mapped[str | None] = mapped_column(
        String(2000),
        nullable=True,
        comment="Group description",
    )
    icon_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="Group icon URL",
    )
    active: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
        comment="Whether the group is active",
    )
    remote_created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Group created timestamp from Channel Talk",
    )
    remote_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Group updated timestamp from Channel Talk",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="Metadata row creation time",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="Metadata row last update time",
    )


class ChannelTalkGroupManager(Base):
    __tablename__ = "channel_talk_group_managers"

    channel_id: Mapped[str] = mapped_column(
        String(128),
        primary_key=True,
        comment="Owning Channel Talk channel ID",
    )
    group_id: Mapped[str] = mapped_column(
        String(128),
        primary_key=True,
        comment="Channel Talk group ID",
    )
    manager_id: Mapped[str] = mapped_column(
        String(128),
        primary_key=True,
        comment="Channel Talk manager ID",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="Relation row creation time",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="Relation row last update time",
    )


class ChannelTalkDocumentAuthor(Base):
    __tablename__ = "channel_talk_document_authors"

    channel_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    space_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    author_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class ChannelTalkDocumentNavNode(Base):
    __tablename__ = "channel_talk_document_nav_nodes"

    channel_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    space_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    nav_node_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    parent_node_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    node_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    entity_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    language: Mapped[str | None] = mapped_column(String(32), nullable=True)
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        Index(
            "idx_channel_talk_document_nav_entity",
            "channel_id",
            "space_id",
            "entity_type",
            "entity_id",
        ),
    )


class ChannelTalkUser(Base):
    __tablename__ = "channel_talk_users"

    channel_id: Mapped[str] = mapped_column(
        String(128),
        primary_key=True,
        comment="Owning Channel Talk channel ID",
    )
    external_user_id: Mapped[str] = mapped_column(
        String(128),
        primary_key=True,
        comment="Channel Talk userId",
    )
    veil_id: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
        comment="Veil ID returned by Channel Talk",
    )
    unified_id: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
        comment="Unified ID returned by Channel Talk",
    )
    member_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
        comment="External memberId tied to the customer",
    )
    user_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Channel Talk user type such as member",
    )
    name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Customer display name",
    )
    email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
        comment="Customer email address",
    )
    mobile_number: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        comment="Customer mobile number",
    )
    avatar_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="Customer avatar URL",
    )
    blocked: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
        comment="Whether the user is blocked",
    )
    language: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Preferred language",
    )
    country: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        comment="Country",
    )
    city: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
        comment="City",
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last seen timestamp from Channel Talk",
    )
    remote_created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="User created timestamp from Channel Talk",
    )
    remote_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="User updated timestamp from Channel Talk",
    )
    profile: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Raw or normalized customer profile payload",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="Metadata row creation time",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="Metadata row last update time",
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
    CHANNEL_TALK = "channel_talk"


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
    WAITING_FULL_SYNC = "waiting_full_sync"
    QUEUED = "queued"
    PROCESSING = "processing"
    RETRY_WAIT = "retry_wait"
    DEAD = "dead"
    SYNCED = "synced"
    RECOVERED = "recovered"


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
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    embedding_tokens_used: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default=text("0")
    )
    summary_tokens_used: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default=text("0")
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
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
            (
                "status IN ("
                "'pending', 'in_progress', 'success', 'failed', 'retrying'"
                ")"
            ),
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
            "idx_sync_events_connector_status_next_retry_at",
            "connector",
            "status",
            "next_retry_at",
        ),
        Index(
            "idx_sync_events_publish_status_requested_at",
            "publish_status",
            "requested_at",
        ),
        Index("idx_sync_events_stream_message_id", "stream_message_id"),
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
            "status IN ('debouncing', 'waiting_full_sync', 'queued', 'processing', 'retry_wait', 'dead', 'synced', 'recovered')",
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
        Index(
            "idx_incremental_stream_outbox_stream_message_id",
            "stream_message_id",
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
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
        index=True,
        comment="메시지 발신 유저 (Slack 멀티유저 귀속용, 레거시 레코드는 NULL)"
    )
    trace_id: Mapped[str] = mapped_column(
        String(64),
        nullable=True,
        comment="Langfuse trace에 사용자 피드백을 사후 반영하기 위한 식별자"
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
    
    # TODO : 추후에 피드백 테이블을 별도로 분리하여 관리하지만, Slack Bot v0에서는 임시로 해당 테이블에 feedback_user 필드를 추가하여 관리한다.
    feedback_user: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Slack Bot v0 : 피드백은 답변 생성 요청자 관계 없이 누구나 한번만 피드백을 남길 수 있다."
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

    pipeline_result: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="role=assistant일 때 RAG 파이프라인 노드별 status 이벤트"
    )

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


class SlackChatThread(Base):
    __tablename__ = "slack_chat_threads"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    team_id: Mapped[str] = mapped_column(String(20), nullable=False)
    channel_id: Mapped[str] = mapped_column(String(20), nullable=False)
    thread_ts: Mapped[str] = mapped_column(String(32), nullable=False)
    # Slack Thread <-> RAG Session 매핑 키
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        unique=True,
        index=True,
    )
    # 답변 생성 이후 chat_room_id가 배정되므로 Nullable
    chat_room_id: Mapped[int | None] = mapped_column(
        ForeignKey("chat_rooms.id"),
        nullable=True,
        index=True,
    )
    # CatchUp User 
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    # Slack User
    slack_user_id: Mapped[str] = mapped_column(String(20), nullable=False)
    # 멘션 태그를 포함하는 본문
    last_raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_answer_in_progress: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    in_progress_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Slack Thread ts 단위 채팅방 관리 (후속질문 처리)
    __table_args__ = (
        UniqueConstraint(
            "team_id",
            "channel_id",
            "thread_ts",
            name="uq_slack_chat_threads_thread",
        ),
    )


class TokenPurpose(StrEnum):
    SUMMARIZE = "summarize"
    CHAT = "chat"
    TITLE_GENERATION = "title_generation"


class ChatTokenUsage(Base):
    __tablename__ = "chat_token_usages"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), nullable=False)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
    message_id: Mapped[int | None] = mapped_column(
        ForeignKey("chat_histories.id"), nullable=True, comment="purpose가 title_generation인 경우 NULL 허용"
    )
    
    purpose: Mapped[TokenPurpose] = mapped_column(String(50), nullable=False)
    
    token_breakdown: Mapped[dict[str, dict[str, int]]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb")
    )
    rerank_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_chat_token_usages_user_time", "user_id", "created_at"),
        Index("idx_chat_token_usages_workspace_time", "workspace_id", "created_at"),
        Index("idx_chat_token_usages_company_time", "company_id", "created_at"),
    )


class ManualSearchHistory(Base):
    __tablename__ = "manual_search_histories"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_manual_search_histories_user_created_at", "user_id", "created_at"),
    )


# === Agent Studio ===
class AgentStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    INACTIVE = "inactive"


class AgentTriggerRunStatus(StrEnum):
    PENDING = "pending"
    DISPATCHING = "dispatching"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentSpec(Base):
    __tablename__ = "agent_specs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    agent_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    spec: Mapped[dict] = mapped_column(JSONB, nullable=False)
    user_input_values: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    status: Mapped[AgentStatus] = mapped_column(
        String(20), nullable=False, server_default=text(f"'{AgentStatus.DRAFT}'")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    triggers: Mapped[list["AgentTrigger"]] = relationship(back_populates="agent_spec")

    __table_args__ = (
        UniqueConstraint("agent_id", "version", name="uq_agent_specs_agent_id_version"),
    )


class AgentTrigger(Base):
    __tablename__ = "agent_triggers"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    agent_spec_id: Mapped[int] = mapped_column(
        ForeignKey("agent_specs.id", ondelete="CASCADE"), nullable=False
    )
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    type: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'webhook'")
    )
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    condition: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text(
            """'{"kind":"immediate","where":{"all":[]}}'::jsonb"""
        ),
    )
    concurrency_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    agent_spec: Mapped["AgentSpec"] = relationship(back_populates="triggers")
    runs: Mapped[list["AgentTriggerRun"]] = relationship(back_populates="trigger")

    __table_args__ = (
        UniqueConstraint(
            "agent_spec_id",
            "source",
            "event_type",
            name="uq_agent_triggers_agent_spec_source_event_type",
        ),
        Index(
            "idx_agent_triggers_lookup",
            "workspace_id",
            "source",
            "event_type",
        ),
        Index("idx_agent_triggers_agent_spec_id", "agent_spec_id"),
        Index("idx_agent_triggers_concurrency_key", "workspace_id", "concurrency_key"),
    )


class AgentTriggerRun(Base):
    __tablename__ = "agent_trigger_runs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    trigger_id: Mapped[int] = mapped_column(
        ForeignKey("agent_triggers.id", ondelete="CASCADE"), nullable=False
    )
    policy_kind: Mapped[str] = mapped_column(String(30), nullable=False)
    entity_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[AgentTriggerRunStatus] = mapped_column(
        String(30),
        nullable=False,
        server_default=text(f"'{AgentTriggerRunStatus.PENDING}'"),
    )
    run_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    start_event_id: Mapped[str] = mapped_column(String(255), nullable=False)
    latest_event_id: Mapped[str] = mapped_column(String(255), nullable=False)
    dispatch_token: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, default=uuid.uuid4
    )
    policy_metadata: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    trigger: Mapped["AgentTrigger"] = relationship(back_populates="runs")

    __table_args__ = (
        Index("idx_agent_trigger_runs_due", "status", "run_after"),
        Index(
            "idx_agent_trigger_runs_trigger_latest_event",
            "trigger_id",
            "latest_event_id",
        ),
        Index(
            "uq_agent_trigger_runs_active_trigger_entity",
            "trigger_id",
            "entity_key",
            unique=True,
            postgresql_where=text(
                "status IN ('pending', 'dispatching') AND entity_key IS NOT NULL"
            ),
        ),
    )
