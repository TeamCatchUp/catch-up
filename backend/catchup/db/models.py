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

    account_id: Mapped[str] = mapped_column(String(128), primary_key=True, nullable=False)
    account_type: Mapped[JiraAccountType] = mapped_column(String(20), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    # TODO : Jira Third Party App으로 Email 수집 가능 여부 체크 후 nullable 옵션 수정
    email_address: Mapped[str] = mapped_column(String(255), nullable=True)
    avatar_url: Mapped[str] = mapped_column(String(500), nullable=True)
    self_url: Mapped[str] = mapped_column(String(500), nullable=True)


class SlackUser(Base):
    __tablename__ = "slack_users"

    team_id: Mapped[str] = mapped_column(String(20), primary_key=True, comment="WorkSpaceId")
    user_id: Mapped[str] = mapped_column(String(20), primary_key=True, comment="UserId")
    name: Mapped[str] = mapped_column(String(255), nullable=False, comment="Login Name Used for Mention")
    real_name: Mapped[str] = mapped_column(String(255), nullable=False, comment="실제 이름")
    deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="비활성 사용자 여부")

    # Profile
    email: Mapped[str] = mapped_column(String(255), nullable=True, index=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    avatar_url: Mapped[str] = mapped_column(String(500), nullable=True)
    is_bot: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_restricted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="Guest User")


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
    def from_webhook_payload(cls, payload: "InstallationWebhookPayload")-> "GithubInstallation":
        from catchup.auth.github.schemas import InstallationWebhookPayload

        account = payload.installation.account
        return cls(
            installation_id = payload.installation.id,
            account_type = GithubInstallationType(account.type.lower()),
            account_id = account.id,
            account_login = account.login,
            account_avatar_url = account.avatar_url,
            suspended_at = payload.installation.suspended_at,
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