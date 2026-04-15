from typing import Dict, List

from pydantic import BaseModel, EmailStr

from catchup.db.models import UserRole, UserStatus


class CurrentUserInfo(BaseModel):
    user_id: int | None = None
    email: EmailStr
    name: str
    role: str
    status: UserStatus


class CurrentUserProfile(BaseModel):
    name: str
    email: EmailStr
    picture: str
    department: str
    job_level: str
    role: UserRole


class IntegrationProfileItem(BaseModel):
    avatar_url: str | None = None
    name: str | None = None
    email: EmailStr | None = None


class IntegrationProfileResponse(BaseModel):
    github: IntegrationProfileItem | None = None
    jira: IntegrationProfileItem | None = None
    confluence: IntegrationProfileItem | None = None
    slack: IntegrationProfileItem | None = None


class JiraSyncableProject(BaseModel):
    project_key: str
    project_name: str


class GithubSyncableRepository(BaseModel):
    full_name: str
    repo_id: int


class ConfluenceSyncableSpace(BaseModel):
    space_name: str
    space_key: str


JiraSyncableResponse = Dict[str, List[JiraSyncableProject]]
GithubSyncableResponse = Dict[str, List[GithubSyncableRepository]]
ConfluenceSyncableResponse = Dict[str, List[ConfluenceSyncableSpace]]
