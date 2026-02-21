from pydantic import BaseModel, EmailStr

from catchup.db.models import UserStatus


class CurrentUserInfo(BaseModel):
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

    


class TokenRefreshResponse(BaseModel):
    status: str
    detail: str


class GithubConnectorStatus(BaseModel):
    tool_name: str = "github"
    connected: bool
    oldest: str | None
    latest: str | None
    repositories: list[str]


class JiraConnectorStatus(BaseModel):
    tool_name: str = "jira"
    connected: bool
    oldest: str | None
    latest: str | None
    projects: list[str]
