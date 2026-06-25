from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any

from pydantic import AliasChoices
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import ValidationInfo
from pydantic import field_validator

from catchup.connectors.channel_talk.schemas._parsing import _parse_manager_ids
from catchup.connectors.channel_talk.schemas._parsing import _parse_metadata_page
from catchup.connectors.channel_talk.schemas._parsing import _PayloadReader
from catchup.connectors.channel_talk.schemas._parsing import _required_reader_text
from catchup.connectors.channel_talk.schemas._parsing import _validation_field_name
from catchup.utils.validation import require_text


class ChannelTalkChannel(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    channel_id: str = Field(validation_alias=AliasChoices("id"))
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
        return require_text(value, _validation_field_name(info))

    @classmethod
    def from_api_payload(cls, payload: Any) -> "ChannelTalkChannel":
        if not isinstance(payload, Mapping):
            raise ValueError("channel payload must be an object")

        reader = _PayloadReader(payload)
        source = reader.nested("channel") or reader
        channel_id = _required_reader_text(
            source,
            "channel payload missing channel id",
            "id",
        )

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
                id=manager_reader.text("id"),
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
class ChannelTalkGroupManagerMembership(BaseModel):
    channel_id: str
    group_id: str
    manager_id: str

    @field_validator("channel_id", "group_id", "manager_id")
    @classmethod
    def validate_membership_required_text(cls, value: str, info: ValidationInfo) -> str:
        return require_text(value, _validation_field_name(info))
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
    role_id: str | None = None
    removed: bool | None = None
    display_as_channel: bool | None = None
    avatar_url: str | None = None
    remote_created_at: datetime | None = None

    @field_validator("manager_id")
    @classmethod
    def validate_manager_id(cls, value: str) -> str:
        return require_text(value, "manager_id")

    @classmethod
    def from_api_payload(cls, payload: Any) -> "ChannelTalkManagerMetadata":

        if not isinstance(payload, Mapping):
            raise ValueError("manager payload must be an object")

        reader = _PayloadReader(payload)
        manager_id = _required_reader_text(
            reader,
            "manager payload missing manager id",
            "id",
        )

        return cls(
            channel_id=reader.text("channelId"),
            manager_id=manager_id,
            account_id=reader.text("accountId"),
            name=reader.text("name", "username"),
            description=reader.text("description"),
            email=reader.text("email"),
            mobile_number=reader.text("mobileNumber", "mobile_number"),
            role_id=reader.text("roleId"),
            removed=reader.boolean("removed"),
            display_as_channel=reader.boolean("displayAsChannel"),
            avatar_url=reader.text("avatarUrl"),
            remote_created_at=reader.moment("createdAt"),
        )

class ChannelTalkManagerMetadataPage(BaseModel):
    managers: list[ChannelTalkManagerMetadata]
    next_page_token: str | None = None

    @classmethod
    def from_api_payload(cls, payload: Any) -> "ChannelTalkManagerMetadataPage":
        managers, next_page_token = _parse_metadata_page(
            payload,
            item_keys=("managers",),
            parse_item=ChannelTalkManagerMetadata.from_api_payload,
            error_message="manager list payload must be an object or list",
        )

        return cls(
            managers=managers,
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
        return require_text(value, _validation_field_name(info))

    @classmethod
    def from_api_payload(cls, payload: Any) -> "ChannelTalkGroupMetadata":
        if not isinstance(payload, Mapping):
            raise ValueError("group payload must be an object")

        reader = _PayloadReader(payload)
        group_id = _required_reader_text(
            reader,
            "group payload missing group id",
            "id",
        )

        return cls(
            channel_id=reader.text("channelId"),
            group_id=group_id,
            group_name=reader.text("name") or group_id,
            scope=reader.text("scope"),
            description=reader.text("description"),
            icon_url=reader.text("icon"),
            active=reader.boolean("active"),
            remote_created_at=reader.moment("createdAt"),
            remote_updated_at=reader.moment("updatedAt"),
            manager_ids=_parse_manager_ids(reader),
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
        groups, next_page_token = _parse_metadata_page(
            payload,
            item_keys=("groups",),
            parse_item=ChannelTalkGroupMetadata.from_api_payload,
            error_message="group list payload must be an object or list",
        )

        return cls(
            groups=groups,
            next_page_token=next_page_token,
        )
