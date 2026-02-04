from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class GitHubAccount(BaseModel):
    """GitHub App이 설치된 계정 (Organization 또는 User)"""
    id: int
    login: str
    type: str  # "Organization" or "User"
    avatar_url: Optional[str] = None


class GitHubInstallationInfo(BaseModel):
    id: int
    account: GitHubAccount
    app_id: int
    suspended_at: Optional[datetime] = None


class GitHubSender(BaseModel):
    id: int
    login: str


class InstallationWebhookPayload(BaseModel):
    """
    GitHub App Installation Webhook Payload
    - action: created, deleted, suspend, unsuspend, new_permissions_accepted
    """
    action: str
    installation: GitHubInstallationInfo
    sender: GitHubSender


class InstallationRepositoriesWebhookPayload(BaseModel):
    """
    Installation Repositories Webhook Payload
    - action: added, removed
    """
    action: str
    installation: GitHubInstallationInfo
    repositories_added: list = Field(default_factory=list)
    repositories_removed: list = Field(default_factory=list)
    sender: GitHubSender
