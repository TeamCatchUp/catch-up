from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from typing import Protocol

from pydantic import BaseModel
from pydantic import Field


class ConnectionType(StrEnum):
    OAUTH_TOKEN = "oauth_token"
    CREDENTIAL = "credential"
    INSTALLATION = "installation"


class ConnectionStatusItem(BaseModel):
    id: str
    name: str | None = None
    connected_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConnectionStatus(BaseModel):
    vendor: str
    connected: bool
    connection_type: ConnectionType
    count: int
    items: list[ConnectionStatusItem] = Field(default_factory=list)


class ConnectionStatusProvider(Protocol):
    def list_github_installation_items(self) -> list[ConnectionStatusItem]: ...

    def list_slack_oauth_token_items(self) -> list[ConnectionStatusItem]: ...

    def list_atlassian_oauth_token_items(self) -> list[ConnectionStatusItem]: ...

    def list_channel_talk_credential_items(self) -> list[ConnectionStatusItem]: ...
