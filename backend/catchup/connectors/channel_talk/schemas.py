from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import ValidationInfo
from pydantic import field_validator


def _require_text(value: str, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field_name} is required")
    return text


def _maybe_text(value: Any) -> str | None:
    if value is None:
        return None

    text = str(value).strip()
    return text or None


def _pick_text(payload: Mapping[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = payload.get(key)
        text = _maybe_text(value)
        if text is not None:
            return text
    return None


class ChannelTalkConnectRequest(BaseModel):
    access_key: str
    access_secret: str
    webhook_token: str

    @field_validator("access_key", "access_secret", "webhook_token")
    @classmethod
    def validate_required_text(cls, value: str, info: ValidationInfo) -> str:
        return _require_text(value, info.field_name)


class ChannelTalkChannel(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    name: str
    subdomain: str | None = None
    avatar_url: str | None = None
    country: str | None = None
    time_zone: str | None = None


class ChannelTalkManager(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str | None = None
    name: str | None = None
    email: str | None = None
    mobile_number: str | None = None


class ChannelTalkCurrentChannel(BaseModel):
    channel: ChannelTalkChannel
    manager: ChannelTalkManager | None = None

    @classmethod
    def from_api_payload(cls, payload: Any) -> "ChannelTalkCurrentChannel":
        if not isinstance(payload, Mapping):
            raise ValueError("channel response payload must be an object")

        channel_payload = payload.get("channel")
        if isinstance(channel_payload, Mapping):
            source = channel_payload
        else:
            source = payload

        channel_id = _pick_text(source, "id", "channelId", "channel_id")
        if channel_id is None:
            raise ValueError("channel response missing channel id")

        channel_name = _pick_text(source, "name", "channelName", "channel_name") or channel_id

        manager_payload = payload.get("manager")
        manager: ChannelTalkManager | None = None
        if isinstance(manager_payload, Mapping):
            manager = ChannelTalkManager(
                id=_pick_text(manager_payload, "id", "memberId", "member_id"),
                name=_pick_text(manager_payload, "name", "displayName", "display_name"),
                email=_pick_text(manager_payload, "email"),
                mobile_number=_pick_text(manager_payload, "mobileNumber", "mobile_number"),
            )

        return cls(
            channel=ChannelTalkChannel(
                id=channel_id,
                name=channel_name,
                subdomain=_pick_text(source, "subdomainName", "subdomain", "subdomain_name"),
                avatar_url=_pick_text(source, "avatarUrl", "avatarURL", "avatar_url"),
                country=_pick_text(source, "country"),
                time_zone=_pick_text(source, "timeZone", "time_zone"),
            ),
            manager=manager,
        )

    @property
    def channel_id(self) -> str:
        return self.channel.id

    @property
    def channel_name(self) -> str:
        return self.channel.name


class ChannelTalkCredentialsRecord(BaseModel):
    channel_id: str
    channel_name: str
    access_key: str | None = None
    access_secret: str | None = None
    webhook_token: str | None = None
    credential_last_verified_at: datetime | None = None
    manager_id: str | None = None
    manager_name: str | None = None

    @field_validator("channel_id", "channel_name")
    @classmethod
    def validate_record_required_text(cls, value: str, info: ValidationInfo) -> str:
        return _require_text(value, info.field_name)

    @property
    def webhook_token_configured(self) -> bool:
        return _maybe_text(self.webhook_token) is not None


class ChannelTalkCredentialsUpsert(BaseModel):
    access_key: str
    access_secret: str
    webhook_token: str
    current_channel: ChannelTalkCurrentChannel
    credential_last_verified_at: datetime

    @field_validator("access_key", "access_secret", "webhook_token")
    @classmethod
    def validate_upsert_required_text(cls, value: str, info: ValidationInfo) -> str:
        return _require_text(value, info.field_name)

    def to_record(self) -> ChannelTalkCredentialsRecord:
        return ChannelTalkCredentialsRecord(
            channel_id=self.current_channel.channel_id,
            channel_name=self.current_channel.channel_name,
            access_key=self.access_key,
            access_secret=self.access_secret,
            webhook_token=self.webhook_token,
            credential_last_verified_at=self.credential_last_verified_at,
            manager_id=self.current_channel.manager.id if self.current_channel.manager else None,
            manager_name=self.current_channel.manager.name if self.current_channel.manager else None,
        )


class ChannelTalkCredentialsStatus(BaseModel):
    installed: bool
    channel_id: str | None = None
    channel_name: str | None = None
    credential_last_verified_at: datetime | None = None
    webhook_token_configured: bool = False
    manager_id: str | None = None
    manager_name: str | None = None

    @classmethod
    def disconnected(cls) -> "ChannelTalkCredentialsStatus":
        return cls(installed=False)

    @classmethod
    def from_record(
        cls,
        record: ChannelTalkCredentialsRecord | None,
    ) -> "ChannelTalkCredentialsStatus":
        if record is None:
            return cls.disconnected()

        return cls(
            installed=True,
            channel_id=record.channel_id,
            channel_name=record.channel_name,
            credential_last_verified_at=record.credential_last_verified_at,
            webhook_token_configured=record.webhook_token_configured,
            manager_id=record.manager_id,
            manager_name=record.manager_name,
        )


class ChannelTalkUninstallResult(BaseModel):
    success: bool = True
    removed: bool = False
    installed: bool = False
