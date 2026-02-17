"""Atlassian OAuth schemas.

Atlassian OAuth 2.0 인증 응답/상태 DTO.
"""

from pydantic import BaseModel, Field


class AtlassianOAuthTokenResponse(BaseModel):
    """토큰 교환/갱신 응답"""

    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int = Field(description="Access Token의 만료 시간(초 단위)")
    scope: str = ""


class AtlassianAccessibleResource(BaseModel):
    """accessible-resources API 응답 항목"""

    id: str = Field(description="Atlassian Cloud ID")
    name: str = Field(description="Atlassian Site Name")
    url: str = Field(description="Atlassian Site URL")
    scopes: list[str] = Field(default_factory=list, description="부여된 스코프")
    avatar_url: str | None = Field(default=None, description="Site Avatar URL")


class AtlassianUserInfo(BaseModel):
    """/me API 응답 DTO."""

    account_id: str
    email: str | None = None
    name: str | None = None
    picture: str | None = None


class AtlassianInstallationStatus(BaseModel):
    """Atlassian 설치 상태 응답 DTO."""

    installed: bool
    resources: list[AtlassianAccessibleResource] = Field(default_factory=list)
