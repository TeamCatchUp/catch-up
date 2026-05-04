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


class ChannelTalkValidateResponse(BaseModel):
    status: str = "validated"
    channel_id: str
    channel_name: str
    manager_id: str | None = None
    manager_name: str | None = None
    webhook_token_configured: bool = False


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
    polling_cycle_hours: int = 1
    last_incremental_polled_at: str | None = None
    last_incremental_poll_started_at: str | None = None
    last_incremental_poll_error: str | None = None
    status_reason: str | None = None


class ChannelTalkDocumentConnectResponse(ChannelTalkDocumentStatusResponse):
    status: str = "connected"
    message: str = "Channel Talk Documents credentials saved."


class ChannelTalkDocumentValidateResponse(BaseModel):
    status: str = "validated"
    channel_id: str
    space_id: str
    space_name: str
    association_status: str


class ChannelTalkDocumentUninstallResponse(BaseModel):
    status: str
    message: str
    installed: bool = False
