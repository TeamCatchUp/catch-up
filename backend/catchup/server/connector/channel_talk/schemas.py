from __future__ import annotations

from pydantic import BaseModel


class ChannelTalkStatusResponse(BaseModel):
    installed: bool
    channel_id: str | None = None
    channel_name: str | None = None
    credential_last_verified_at: str | None = None
    webhook_token_configured: bool = False
    status_reason: str | None = None


class ChannelTalkConnectResponse(ChannelTalkStatusResponse):
    status: str = "connected"
    message: str = "Channel Talk credentials saved."


class ChannelTalkUninstallResponse(BaseModel):
    status: str
    message: str
    installed: bool = False


class ChannelTalkDocumentStatusResponse(BaseModel):
    installed: bool
    channel_id: str | None = None
    space_id: str | None = None
    space_name: str | None = None
    credential_last_verified_at: str | None = None
    association_status: str | None = None
    status_reason: str | None = None


class ChannelTalkDocumentConnectResponse(ChannelTalkDocumentStatusResponse):
    status: str = "connected"
    message: str = "Channel Talk Documents credentials saved."


class ChannelTalkDocumentUninstallResponse(BaseModel):
    status: str
    message: str
    installed: bool = False
