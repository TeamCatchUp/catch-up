from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel
from pydantic import Field
from pydantic import ValidationInfo
from pydantic import field_validator

from catchup.connectors.channel_talk.schemas._parsing import _validation_field_name
from catchup.connectors.channel_talk.schemas.document_metadata import (
    ChannelTalkDocumentSpace,
)
from catchup.utils.validation import require_text


class ChannelTalkDocumentAssociationStatus(StrEnum):
    API_VERIFIED = "api_verified"
    LOCAL_TRUSTED = "local_trusted"
    UNVERIFIED = "unverified"
    FAILED = "failed"

class ChannelTalkDocumentConnectRequest(BaseModel):
    access_key: str
    access_secret: str
    polling_cycle_hours: int = Field(default=1, ge=1, le=168)

    @field_validator("access_key", "access_secret")
    @classmethod
    def validate_required_text(cls, value: str, info: ValidationInfo) -> str:
        return require_text(value, _validation_field_name(info))

class ChannelTalkDocumentCredentialsRecord(BaseModel):
    channel_id: str
    space_id: str
    space_name: str
    access_key: str | None = None
    access_secret: str | None = None
    credential_last_verified_at: datetime | None = None
    association_status: ChannelTalkDocumentAssociationStatus
    polling_cycle_hours: int = Field(default=1, ge=1, le=168)
    last_incremental_polled_at: datetime | None = None
    last_incremental_poll_started_at: datetime | None = None
    last_incremental_poll_error: str | None = None

    @field_validator("channel_id", "space_id", "space_name")
    @classmethod
    def validate_record_required_text(cls, value: str, info: ValidationInfo) -> str:
        return require_text(value, _validation_field_name(info))

class ChannelTalkDocumentCredentialsUpsert(BaseModel):
    channel_id: str
    access_key: str
    access_secret: str
    space: ChannelTalkDocumentSpace
    credential_last_verified_at: datetime
    association_status: ChannelTalkDocumentAssociationStatus
    polling_cycle_hours: int = Field(default=1, ge=1, le=168)

    @field_validator("channel_id", "access_key", "access_secret")
    @classmethod
    def validate_upsert_required_text(cls, value: str, info: ValidationInfo) -> str:
        return require_text(value, _validation_field_name(info))

    def to_record(self) -> ChannelTalkDocumentCredentialsRecord:
        return ChannelTalkDocumentCredentialsRecord(
            channel_id=self.channel_id,
            space_id=self.space.space_id,
            space_name=self.space.space_name,
            access_key=self.access_key,
            access_secret=self.access_secret,
            credential_last_verified_at=self.credential_last_verified_at,
            association_status=self.association_status,
            polling_cycle_hours=self.polling_cycle_hours,
        )

class ChannelTalkDocumentCredentialsStatus(BaseModel):
    installed: bool
    channel_id: str | None = None
    space_id: str | None = None
    space_name: str | None = None
    credential_last_verified_at: datetime | None = None
    association_status: ChannelTalkDocumentAssociationStatus | None = None
    polling_cycle_hours: int = 1
    last_incremental_polled_at: datetime | None = None
    last_incremental_poll_started_at: datetime | None = None
    last_incremental_poll_error: str | None = None

    @classmethod
    def disconnected(cls) -> "ChannelTalkDocumentCredentialsStatus":
        return cls(installed=False)

    @classmethod
    def from_record(
        cls,
        record: ChannelTalkDocumentCredentialsRecord | None,
    ) -> "ChannelTalkDocumentCredentialsStatus":
        if record is None:
            return cls.disconnected()
        return cls(
            installed=True,
            channel_id=record.channel_id,
            space_id=record.space_id,
            space_name=record.space_name,
            credential_last_verified_at=record.credential_last_verified_at,
            association_status=record.association_status,
            polling_cycle_hours=record.polling_cycle_hours,
            last_incremental_polled_at=record.last_incremental_polled_at,
            last_incremental_poll_started_at=record.last_incremental_poll_started_at,
            last_incremental_poll_error=record.last_incremental_poll_error,
        )

class ChannelTalkDocumentUninstallResult(BaseModel):
    success: bool = True
    removed: bool = False
    installed: bool = False
