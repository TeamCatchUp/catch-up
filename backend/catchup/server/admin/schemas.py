from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr

from catchup.db.models import UserRole

from catchup.db.models import JobLevel, UserRole, UserStatus


class SourceUserCount(BaseModel):
    users: int
    premap: int


class SyncStatusCounts(BaseModel):
    jira: SourceUserCount
    slack: SourceUserCount
    github: SourceUserCount
    confluence: SourceUserCount


class UserSyncMapping(BaseModel):
    name: str
    githubLogin: Optional[str] = None
    atlassianEmail: Optional[EmailStr] = None
    slackEmail: Optional[EmailStr] = None


class UserSyncStatusResponse(BaseModel):
    counts: SyncStatusCounts
    mappings: List[UserSyncMapping]


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
    reason: str


class DeactivateUserResponse(BaseModel):
    userId: int
    status: UserStatus
    inactiveRecordId: int
    deactivatedAt: str
    reason: str


class DeleteUserResponse(BaseModel):
    userId: int
    status: UserStatus


class PromoteUserResponse(BaseModel):
    userId: int
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
