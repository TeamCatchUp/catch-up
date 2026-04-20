from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from datetime import timezone
from typing import Any

from pydantic import AliasChoices
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import ValidationInfo
from pydantic import field_validator

from catchup.connector_core.domain.structure import ConnectorKey
from catchup.connector_core.ports.metadata_sync import MetadataSyncRequest
from catchup.connector_core.ports.metadata_sync import MetadataSyncResult


class ChannelTalkConnectRequest(BaseModel):
    access_key: str
    access_secret: str
    webhook_token: str

    @field_validator("access_key", "access_secret", "webhook_token")
    @classmethod
    def validate_required_text(cls, value: str, info: ValidationInfo) -> str:
        return _require_text(value, info.field_name)


class ChannelTalkChannel(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    channel_id: str = Field(validation_alias=AliasChoices("id", "channelId", "channel_id"))
    channel_name: str = Field(
        validation_alias=AliasChoices("name", "channelName", "channel_name")
    )
    description: str | None = None
    bot_name: str | None = None
    homepage_url: str | None = None
    domain: str | None = None
    subdomain: str | None = None
    avatar_url: str | None = None
    country: str | None = None
    time_zone: str | None = None

    @field_validator("channel_id", "channel_name")
    @classmethod
    def validate_channel_required_text(cls, value: str, info: ValidationInfo) -> str:
        return _require_text(value, info.field_name)

    @classmethod
    def from_api_payload(cls, payload: Any) -> "ChannelTalkChannel":
        if not isinstance(payload, Mapping):
            raise ValueError("channel payload must be an object")

        reader = _PayloadReader(payload)
        source = reader.nested("channel") or reader
        channel_id = source.text("id", "channelId", "channel_id")
        if channel_id is None:
            raise ValueError("channel payload missing channel id")

        return cls(
            channel_id=channel_id,
            channel_name=source.text("name", "channelName", "channel_name") or channel_id,
            description=source.text("description"),
            bot_name=source.text("botName", "defaultBotName", "bot_name"),
            homepage_url=source.text("homepage", "homepageUrl", "homepage_url"),
            domain=source.text("domain", "customDomain", "custom_domain"),
            subdomain=source.text("subdomainName", "subdomain", "subdomain_name"),
            avatar_url=source.text("avatarUrl", "avatarURL", "avatar_url"),
            country=source.text("country"),
            time_zone=source.text("timeZone", "time_zone"),
        )

    @property
    def id(self) -> str:
        return self.channel_id

    @property
    def name(self) -> str:
        return self.channel_name


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

        reader = _PayloadReader(payload)

        manager_reader = reader.nested("manager")
        manager: ChannelTalkManager | None = None
        if manager_reader is not None:
            manager = ChannelTalkManager(
                id=manager_reader.text("id", "memberId", "member_id"),
                name=manager_reader.text("name", "displayName", "display_name"),
                email=manager_reader.text("email"),
                mobile_number=manager_reader.text("mobileNumber", "mobile_number"),
            )

        return cls(
            channel=ChannelTalkChannel.from_api_payload(payload),
            manager=manager,
        )

    @property
    def channel_id(self) -> str:
        return self.channel.channel_id

    @property
    def channel_name(self) -> str:
        return self.channel.channel_name


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


class ChannelTalkMetadataSyncRequest(BaseModel):
    channel_id: str

    @field_validator("channel_id")
    @classmethod
    def validate_channel_id(cls, value: str) -> str:
        return _require_text(value, "channel_id")

    def to_core_request(self) -> MetadataSyncRequest:
        # outer/domain layer의 channel_id를
        # generic core request의 tenant_id로 바꿔 넘긴다.
        return MetadataSyncRequest(
            connector=ConnectorKey.CHANNEL_TALK,
            tenant_id=self.channel_id,
        )


class ChannelTalkGroupManagerMembership(BaseModel):
    channel_id: str
    group_id: str
    manager_id: str

    @field_validator("channel_id", "group_id", "manager_id")
    @classmethod
    def validate_membership_required_text(cls, value: str, info: ValidationInfo) -> str:
        return _require_text(value, info.field_name)


class ChannelTalkMetadataSyncResult(BaseModel):
    connector: ConnectorKey
    channel_id: str
    channel_synced: bool = False
    managers_synced: int = 0
    groups_synced: int = 0
    group_manager_links_synced: int = 0

    @classmethod
    def from_core_result(cls, result: MetadataSyncResult) -> "ChannelTalkMetadataSyncResult":
        # core result는 generic step map만 알기 때문에,
        # Channel Talk에서 읽기 좋은 요약값으로 여기서 다시 조립한다.
        channel_step = result.step_result("channel")
        managers_step = result.step_result("managers")
        groups_step = result.step_result("groups")
        group_memberships_step = result.step_result("group_memberships")

        return cls(
            connector=result.connector,
            channel_id=result.tenant_id,
            channel_synced=(channel_step.synced_count > 0) if channel_step else False,
            managers_synced=managers_step.synced_count if managers_step else 0,
            groups_synced=groups_step.synced_count if groups_step else 0,
            group_manager_links_synced=(
                group_memberships_step.synced_count if group_memberships_step else 0
            ),
        )


ChannelTalkChannelMetadata = ChannelTalkChannel


class ChannelTalkManagerMetadata(BaseModel):
    model_config = ConfigDict(extra="ignore")

    channel_id: str | None = None
    manager_id: str
    account_id: str | None = None
    name: str | None = None
    description: str | None = None
    email: str | None = None
    mobile_number: str | None = None
    role: str | None = None
    removed: bool | None = None
    display_as_channel: bool | None = None
    avatar_url: str | None = None
    remote_created_at: datetime | None = None

    @field_validator("manager_id")
    @classmethod
    def validate_manager_id(cls, value: str) -> str:
        return _require_text(value, "manager_id")

    @classmethod
    def from_api_payload(cls, payload: Any) -> "ChannelTalkManagerMetadata":

        if not isinstance(payload, Mapping):
            raise ValueError("manager payload must be an object")

        reader = _PayloadReader(payload)
        manager_id = reader.text("id", "managerId", "manager_id")
        if manager_id is None:
            raise ValueError("manager payload missing manager id")

        return cls(
            channel_id=reader.text("channelId", "channel_id"),
            manager_id=manager_id,
            account_id=reader.text("accountId", "account_id"),
            name=reader.text("name", "username"),
            description=reader.text("description"),
            email=reader.text("email"),
            mobile_number=reader.text("mobileNumber", "mobile_number"),
            role=reader.text("role"),
            removed=reader.boolean("removed"),
            display_as_channel=reader.boolean("displayAsChannel", "display_as_channel"),
            avatar_url=reader.text("avatarUrl", "avatarURL", "avatar_url"),
            remote_created_at=reader.moment("createdAt", "remoteCreatedAt", "remote_created_at"),
        )

class ChannelTalkManagerMetadataPage(BaseModel):
    managers: list[ChannelTalkManagerMetadata]
    next_page_token: str | None = None

    @classmethod
    def from_api_payload(cls, payload: Any) -> "ChannelTalkManagerMetadataPage":

        if isinstance(payload, list):
            items = payload
            next_page_token = None
        elif isinstance(payload, Mapping):
            reader = _PayloadReader(payload)
            items = reader.items("managers", "results", "items")
            next_page_token = reader.text("next", "nextId", "nextCursor")
        else:
            raise ValueError("manager list payload must be an object or list")

        return cls(
            managers=[
                ChannelTalkManagerMetadata.from_api_payload(item)
                for item in items
                if isinstance(item, Mapping)
            ],
            next_page_token=next_page_token,
        )


class ChannelTalkGroupMetadata(BaseModel):
    model_config = ConfigDict(extra="ignore")

    channel_id: str | None = None
    group_id: str
    group_name: str
    scope: str | None = None
    description: str | None = None
    icon_url: str | None = None
    active: bool | None = None
    remote_created_at: datetime | None = None
    remote_updated_at: datetime | None = None
    manager_ids: tuple[str, ...] = ()

    @field_validator("group_id", "group_name")
    @classmethod
    def validate_group_required_text(cls, value: str, info: ValidationInfo) -> str:
        return _require_text(value, info.field_name)

    @classmethod
    def from_api_payload(cls, payload: Any) -> "ChannelTalkGroupMetadata":

        if not isinstance(payload, Mapping):
            raise ValueError("group payload must be an object")

        reader = _PayloadReader(payload)
        group_id = reader.text("id", "groupId", "group_id")
        if group_id is None:
            raise ValueError("group payload missing group id")

        manager_ids: list[str] = []
        for value in reader.items("managerIds", "manager_ids", "managers"):
            if isinstance(value, Mapping):
                manager_id = _PayloadReader(value).text("id", "managerId", "manager_id")
            else:
                manager_id = str(value).strip() or None
            if manager_id is not None:
                manager_ids.append(manager_id)

        return cls(
            channel_id=reader.text("channelId", "channel_id"),
            group_id=group_id,
            group_name=reader.text("name", "groupName", "group_name") or group_id,
            scope=reader.text("scope"),
            description=reader.text("description"),
            icon_url=reader.text("iconUrl", "iconURL", "icon_url", "icon"),
            active=reader.boolean("active"),
            remote_created_at=reader.moment("createdAt", "remoteCreatedAt", "remote_created_at"),
            remote_updated_at=reader.moment("updatedAt", "remoteUpdatedAt", "remote_updated_at"),
            manager_ids=tuple(manager_ids),
        )

    def to_memberships(self, channel_id: str) -> tuple[ChannelTalkGroupManagerMembership, ...]:

        return tuple(
            ChannelTalkGroupManagerMembership(
                channel_id=channel_id,
                group_id=self.group_id,
                manager_id=manager_id,
            )
            for manager_id in self.manager_ids
        )


class ChannelTalkGroupMetadataPage(BaseModel):
    groups: list[ChannelTalkGroupMetadata]
    next_page_token: str | None = None

    @classmethod
    def from_api_payload(cls, payload: Any) -> "ChannelTalkGroupMetadataPage":
        if isinstance(payload, list):
            items = payload
            next_page_token = None
        elif isinstance(payload, Mapping):
            reader = _PayloadReader(payload)
            items = reader.items("groups", "results", "items")
            next_page_token = reader.text("next", "nextId", "nextCursor")
        else:
            raise ValueError("group list payload must be an object or list")

        return cls(
            groups=[
                ChannelTalkGroupMetadata.from_api_payload(item)
                for item in items
                if isinstance(item, Mapping)
            ],
            next_page_token=next_page_token,
        )


class ChannelTalkUserFoundation(BaseModel):
    model_config = ConfigDict(extra="ignore")

    channel_id: str | None = None
    external_user_id: str
    veil_id: str | None = None
    unified_id: str | None = None
    member_id: str | None = None
    user_type: str | None = None
    name: str | None = None
    email: str | None = None
    mobile_number: str | None = None
    avatar_url: str | None = None
    blocked: bool | None = None
    language: str | None = None
    country: str | None = None
    city: str | None = None
    last_seen_at: datetime | None = None
    remote_created_at: datetime | None = None
    remote_updated_at: datetime | None = None
    profile: dict[str, Any] | None = None

    @field_validator("external_user_id")
    @classmethod
    def validate_external_user_id(cls, value: str) -> str:
        return _require_text(value, "external_user_id")

    @classmethod
    def from_api_payload(cls, payload: Any) -> "ChannelTalkUserFoundation":

        if not isinstance(payload, Mapping):
            raise ValueError("user payload must be an object")

        reader = _PayloadReader(payload)
        source = reader.nested("user") or reader
        profile = source.nested("profile")
        external_user_id = source.text(
            "id",
            "userId",
            "externalUserId",
            "external_user_id",
        )
        if external_user_id is None:
            raise ValueError("user payload missing user id")

        return cls(
            channel_id=source.text("channelId", "channel_id"),
            external_user_id=external_user_id,
            veil_id=source.text("veilId", "veil_id"),
            unified_id=source.text("unifiedId", "unified_id"),
            member_id=source.text("memberId", "member_id"),
            user_type=source.text("type", "userType", "user_type"),
            name=source.text("name") or (profile and profile.text("name")),
            email=source.text("email") or (profile and profile.text("email")),
            mobile_number=source.text("mobileNumber", "mobile_number")
            or (profile and profile.text("mobileNumber", "mobile_number")),
            avatar_url=source.text("avatarUrl", "avatarURL", "avatar_url")
            or (profile and profile.text("avatarUrl", "avatarURL", "avatar_url")),
            blocked=source.boolean("blocked"),
            language=source.text("language") or (profile and profile.text("language")),
            country=source.text("country") or (profile and profile.text("country")),
            city=source.text("city") or (profile and profile.text("city")),
            last_seen_at=source.moment("lastSeenAt", "last_seen_at"),
            remote_created_at=source.moment("createdAt", "remoteCreatedAt", "remote_created_at"),
            remote_updated_at=source.moment("updatedAt", "remoteUpdatedAt", "remote_updated_at"),
            profile=dict(profile.payload) if profile is not None else None,
        )


def _require_text(value: str, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field_name} is required")
    return text


class _PayloadReader:
    """Channel Talk payload에서 필요한 값을 읽는 최소 parsing atom."""

    def __init__(self, payload: Mapping[str, Any]) -> None:
        self.payload = payload

    def text(self, *keys: str) -> str | None:
        for key in keys:
            value = self.payload.get(key)
            if value is None:
                continue
            text = str(value).strip()
            if text:
                return text
        return None

    def boolean(self, *keys: str) -> bool | None:
        for key in keys:
            value = self.payload.get(key)
            if value is None:
                continue
            if isinstance(value, bool):
                return value
            if isinstance(value, (int, float)):
                return bool(value)

            text = str(value).strip().lower()
            if text in {"true", "1", "yes"}:
                return True
            if text in {"false", "0", "no"}:
                return False
        return None

    def moment(self, *keys: str) -> datetime | None:
        for key in keys:
            value = self.payload.get(key)
            parsed = self._parse_datetime(value)
            if parsed is not None:
                return parsed
        return None

    def mapping(self, *keys: str) -> Mapping[str, Any] | None:
        for key in keys:
            value = self.payload.get(key)
            if isinstance(value, Mapping):
                return value
        return None

    def items(self, *keys: str) -> list[Any]:
        for key in keys:
            value = self.payload.get(key)
            if isinstance(value, list):
                return value
        return []

    def nested(self, *keys: str) -> "_PayloadReader | None":
        nested_payload = self.mapping(*keys)
        if nested_payload is None:
            return None
        return _PayloadReader(nested_payload)

    @classmethod
    def _parse_datetime(cls, value: Any) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            if value.tzinfo is not None:
                return value
            return value.replace(tzinfo=timezone.utc)
        if isinstance(value, (int, float)):
            seconds = float(value)
            if abs(seconds) >= 1_000_000_000_000:
                seconds /= 1000
            return datetime.fromtimestamp(seconds, tz=timezone.utc)

        text = str(value).strip()
        if not text:
            return None
        if text.isdigit():
            return cls._parse_datetime(int(text))

        normalized = text.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            return None
        if parsed.tzinfo is not None:
            return parsed
        return parsed.replace(tzinfo=timezone.utc)
