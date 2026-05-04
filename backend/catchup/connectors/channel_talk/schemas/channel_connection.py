from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel
from pydantic import ValidationInfo
from pydantic import field_validator

from catchup.connectors.channel_talk.schemas._parsing import _validation_field_name
from catchup.connectors.channel_talk.schemas.channel_metadata import (
    ChannelTalkCurrentChannel,
)
from catchup.utils.validation import require_text


class ChannelTalkConnectRequest(BaseModel):
    access_key: str
    access_secret: str
    webhook_token: str

    @field_validator("access_key", "access_secret", "webhook_token")
    @classmethod
    def validate_required_text(cls, value: str, info: ValidationInfo) -> str:
        return require_text(value, _validation_field_name(info))

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
        return require_text(value, _validation_field_name(info))

    @property
    def webhook_token_configured(self) -> bool:
        return bool(str(self.webhook_token or "").strip())

class ChannelTalkCredentialsUpsert(BaseModel):
    access_key: str
    access_secret: str
    webhook_token: str
    current_channel: ChannelTalkCurrentChannel
    credential_last_verified_at: datetime

    @field_validator("access_key", "access_secret", "webhook_token")
    @classmethod
    def validate_upsert_required_text(cls, value: str, info: ValidationInfo) -> str:
        return require_text(value, _validation_field_name(info))

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
