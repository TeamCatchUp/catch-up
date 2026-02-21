from typing import List, Optional

from pydantic import BaseModel, EmailStr

from catchup.db.models import JobLevel, UserStatus


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
