from datetime import datetime
from enum import StrEnum
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, EmailStr

from catchup.db.models import UserRole
from catchup.db.models import JobLevel, UserRole, UserStatus


class PreMappingInfo(BaseModel):
    name: str | None = None
    identifier: str | None = None  # email 또는 github login
    picture: str | None = None


class SourceUserCount(BaseModel):
    users: int
    premap: int


class SyncStatusCounts(BaseModel):
    jira: SourceUserCount
    slack: SourceUserCount
    github: SourceUserCount
    confluence: SourceUserCount


class UserSyncMapping(BaseModel):
    sub: str  # OAuth 사용자 식별자
    name: str
    email: str
    atlassian: PreMappingInfo | None = None
    slack: PreMappingInfo | None = None
    github: PreMappingInfo | None = None


class UserSyncStatusResponse(BaseModel):
    counts: SyncStatusCounts
    mappings: List[UserSyncMapping]
    

class ToolUserResponse(BaseModel):
    id: str
    name: str
    identifier: str | None = None  # email 또는 github login
    picture: str | None = None


class ConnectorStatusSource(StrEnum):
    GITHUB = "github"
    JIRA = "jira"
    SLACK = "slack"
    CONFLUENCE = "confluence"


class ConnectorResourceType(StrEnum):
    REPOSITORIES = "repositories"
    PROJECTS = "projects"
    CHANNELS = "channels"
    SPACES = "spaces"


class AdminConnectorTargetRangeResponse(BaseModel):
    scope_id: str
    target_id: str
    target_name: str
    event_id: str
    sync_status: str
    last_succeeded_at: str | None
    last_failed_at: str | None
    oldest: str | None
    latest: str | None


class AdminConnectorStatusResponse(BaseModel):
    source: ConnectorStatusSource
    resource_type: ConnectorResourceType
    total_targets: int
    targets: list[AdminConnectorTargetRangeResponse]


# 1. 프론트엔드에서 받을 Request Schema (변수명 통일 및 필수값 추가)
class PreMappingUpdateItem(BaseModel):
    sub: str  # 내부 시스템 사용자 고유 ID
    email: str  # DB Insert 시 필수
    name: str  # DB Insert 시 필수
    is_ignored: bool  # True: 미사용 (삭제) / False: 사용 (추가 또는 수정)
    external_user_identifier: Optional[str] = None  # 협업툴 사용자 식별자

class PreMappingBulkUpdateRequest(BaseModel):
    items: List[PreMappingUpdateItem]

# =====================
# Admin user management
# =====================
class AdminUserListItem(BaseModel):
    id: int
    name: str
    department: str
    jobLevel: JobLevel
    role: UserRole
    status: UserStatus


class AdminUserListResponse(BaseModel):
    total: int
    users: List[AdminUserListItem]


class JiraAccount(BaseModel):
    accountId: str
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    avatarUrl: Optional[str] = None


class GithubAccount(BaseModel):
    login: str
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    avatarUrl: Optional[str] = None


class SlackAccount(BaseModel):
    userId: str
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    avatarUrl: Optional[str] = None


class ConfluenceAccount(BaseModel):
    accountId: str
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    avatarUrl: Optional[str] = None


class UserIntegrations(BaseModel):
    jira: Optional[JiraAccount] = None
    github: Optional[GithubAccount] = None
    slack: Optional[SlackAccount] = None
    confluence: Optional[ConfluenceAccount] = None


class AdminUserDetailResponse(BaseModel):
    id: int
    name: str
    email: EmailStr
    department: str
    jobLevel: JobLevel
    status: UserStatus
    integrations: UserIntegrations


# =====================
# Admin user state change
# =====================
class DeactivateUserRequest(BaseModel):
    userId: int
    reason: str


class DeleteUserRequest(BaseModel):
    userId: int
    reason: str


class PromoteUserRequest(BaseModel):
    userId: int
    reason: str


class DeactivateUserResponse(BaseModel):
    userId: int
    status: UserStatus
    deactivatedAt: str
    reason: str


class DeleteUserResponse(BaseModel):
    userId: int
    status: UserStatus
    deletedAt: str
    reason: str


class PromoteUserResponse(BaseModel):
    user_id: int
    role: UserRole


class RevokeUserResponse(BaseModel):
    user_id: int
    role: UserRole


# =====================
# Confluence utilities
# =====================
class ConfluenceCloudIdListResponse(BaseModel):
    cloudIds: List[str]
    

class UserResponse(BaseModel):
    id: int
    email: str
    role: UserRole
    department: str
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class OAuthUserResponse(BaseModel):
    sub: str
    name: str
    email: str
    picture: str | None = None
    
    model_config = ConfigDict(from_attributes=True)
