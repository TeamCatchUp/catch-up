from datetime import datetime

from pydantic import BaseModel, Field


class SlackTeamInfo(BaseModel):
    id: str = Field(default="", description="Team ID")
    name: str = Field(default="", description="Team Name")


class SlackAuthedUser(BaseModel):
    id: str


class SlackIncomingWebhook(BaseModel):
    channel: str
    channel_id: str
    configuration_url: str
    url: str


class SlackOAuthTokenResponse(BaseModel):
    ok: bool
    access_token: str = Field(description="Bot Access Token (xoxb-)")
    token_type: str = Field(default="bot")
    scope: str = Field(default="", description="Bot Token scopes")
    bot_user_id: str = Field(default="", description="Bot User ID")
    app_id: str = Field(default="")

    team: SlackTeamInfo = Field(default_factory=SlackTeamInfo)
    authed_user: SlackAuthedUser | None = None
    incoming_webhook: SlackIncomingWebhook | None = None
    refresh_token: str | None = None
    expires_in: int | None = None


class SlackWorkspaceInfo(BaseModel):
    team_id: str
    team_name: str
    bot_user_id: str
    scopes: list[str]
    connected_at: datetime


class SlackInstallationStatus(BaseModel):
    installed: bool
    workspaces: list[SlackWorkspaceInfo] = Field(default_factory=list)
