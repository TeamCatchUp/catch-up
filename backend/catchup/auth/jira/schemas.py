from pydantic import BaseModel, Field

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