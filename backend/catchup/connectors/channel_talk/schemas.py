from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from datetime import timezone
from enum import StrEnum
from typing import Any
from typing import Callable
from typing import TypeVar

from pydantic import AliasChoices
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import ValidationInfo
from pydantic import field_validator

from catchup.connector_core.domain.structure import ConnectorKey
from catchup.connector_core.ports.metadata_sync import MetadataSyncRequest
from catchup.connector_core.ports.metadata_sync import MetadataSyncResult
from catchup.utils.validation import require_text

ParsedMetadataItem = TypeVar("ParsedMetadataItem")


class ChannelTalkConnectRequest(BaseModel):
    access_key: str
    access_secret: str
    webhook_token: str

    @field_validator("access_key", "access_secret", "webhook_token")
    @classmethod
    def validate_required_text(cls, value: str, info: ValidationInfo) -> str:
        return require_text(value, info.field_name)


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
        return require_text(value, info.field_name)

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
        return require_text(value, info.field_name)

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
        return require_text(value, info.field_name)

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
        return require_text(value, "channel_id")

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
        return require_text(value, info.field_name)


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
            role_id=reader.text("roleId", "role_id", "role"),
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
        managers, next_page_token = _parse_metadata_page(
            payload,
            item_keys=("managers", "results", "items"),
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
        return require_text(value, info.field_name)

    @classmethod
    def from_api_payload(cls, payload: Any) -> "ChannelTalkGroupMetadata":
        if not isinstance(payload, Mapping):
            raise ValueError("group payload must be an object")

        reader = _PayloadReader(payload)
        group_id = reader.text("id", "groupId", "group_id")
        if group_id is None:
            raise ValueError("group payload missing group id")

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
            item_keys=("groups", "results", "items"),
            parse_item=ChannelTalkGroupMetadata.from_api_payload,
            error_message="group list payload must be an object or list",
        )

        return cls(
            groups=groups,
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
        return require_text(value, "external_user_id")

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


class FullSyncQuotaSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bucket: str | None = None
    limit: int | None = None
    remaining: int | None = None
    reset_at: datetime | None = None
    retry_after_seconds: int | None = None
    source_headers_present: bool = False


class ChannelTalkUserChatState(StrEnum):
    OPENED = "opened"
    CLOSED = "closed"
    SNOOZED = "snoozed"


class ChannelTalkUserChatListItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    user_chat_id: str
    state: ChannelTalkUserChatState
    ordering_marker: datetime | None = None
    user_id: str | None = None
    member_id: str | None = None

    @field_validator("user_chat_id")
    @classmethod
    def validate_user_chat_id(cls, value: str) -> str:
        return require_text(value, "user_chat_id")

    @classmethod
    def from_api_payload(
        cls,
        payload: Any,
        *,
        state: ChannelTalkUserChatState,
        root_users: list[Mapping[str, Any]] | None = None,
    ) -> "ChannelTalkUserChatListItem":
        if not isinstance(payload, Mapping):
            raise ValueError("user chat payload must be an object")

        source = _read_user_chat_source(payload)
        user_chat_id = _resolve_user_chat_id(
            source,
            user_chat_id=None,
            error_message="user chat payload missing user_chat_id",
        )

        user_id, member_id = _read_user_identity(
            source,
            root_users=root_users,
        )
        resolved_state = source.text("state") or state.value

        return cls(
            user_chat_id=user_chat_id,
            state=ChannelTalkUserChatState(resolved_state),
            ordering_marker=_read_user_chat_ordering_marker(source),
            user_id=user_id,
            member_id=member_id,
        )


class ChannelTalkUserChatListPage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ChannelTalkUserChatListItem]
    next_cursor: str | None = None
    quota_snapshot: FullSyncQuotaSnapshot = Field(default_factory=FullSyncQuotaSnapshot)

    @classmethod
    def from_api_payload(
        cls,
        payload: Any,
        *,
        state: ChannelTalkUserChatState,
        headers: Mapping[str, Any] | None = None,
    ) -> "ChannelTalkUserChatListPage":
        root_reader = _PayloadReader(payload) if isinstance(payload, Mapping) else None
        root_users = []
        if root_reader is not None:
            root_users = [
                value for value in root_reader.items("users")
                if isinstance(value, Mapping)
            ]

        parsed_items, next_cursor = _parse_metadata_page(
            payload,
            item_keys=("userChats", "user_chats", "results", "items"),
            parse_item=lambda item: ChannelTalkUserChatListItem.from_api_payload(
                item,
                state=state,
                root_users=root_users,
            ),
            error_message="user chat list payload must be an object or list",
        )

        return cls(
            items=parsed_items,
            next_cursor=next_cursor,
            quota_snapshot=_parse_quota_snapshot(headers),
        )


class ChannelTalkUserChatManagerRef(BaseModel):
    model_config = ConfigDict(extra="ignore")

    manager_id: str
    name: str | None = None
    email: str | None = None
    role_id: str | None = None

    @field_validator("manager_id")
    @classmethod
    def validate_manager_id(cls, value: str) -> str:
        return require_text(value, "manager_id")

    @classmethod
    def from_api_payload(cls, payload: Any) -> "ChannelTalkUserChatManagerRef":
        if not isinstance(payload, Mapping):
            raise ValueError("manager ref payload must be an object")

        reader = _PayloadReader(payload)
        manager_id = reader.text("id", "managerId", "manager_id")
        if manager_id is None:
            raise ValueError("manager ref payload missing manager id")

        return cls(
            manager_id=manager_id,
            name=reader.text("name", "displayName", "display_name"),
            email=reader.text("email"),
            role_id=reader.text("roleId", "role_id", "role"),
        )


class ChannelTalkUserChatTag(BaseModel):
    model_config = ConfigDict(extra="ignore")

    key: str | None = None
    name: str | None = None

    @classmethod
    def from_api_payload(cls, payload: Any) -> "ChannelTalkUserChatTag":
        if isinstance(payload, Mapping):
            reader = _PayloadReader(payload)
            return cls(
                key=reader.text("key", "id", "tagId", "tag_id"),
                name=reader.text("name", "label", "displayName", "display_name"),
            )

        text = str(payload or "").strip()
        return cls(
            key=text or None,
            name=text or None,
        )


class ChannelTalkUserChatAssignment(BaseModel):
    model_config = ConfigDict(extra="ignore")

    manager_ids: tuple[str, ...] = ()
    managers: list[ChannelTalkUserChatManagerRef] = Field(default_factory=list)
    assignee_id: str | None = None
    assignee_name: str | None = None
    assignee_email: str | None = None
    first_assignee_id_after_open: str | None = None


class ChannelTalkUserChatTiming(BaseModel):
    model_config = ConfigDict(extra="ignore")

    created_at: datetime | None = None
    updated_at: datetime | None = None
    first_opened_at: datetime | None = None
    opened_at: datetime | None = None
    first_asked_at: datetime | None = None
    first_replied_at: datetime | None = None
    first_replied_at_after_open: datetime | None = None
    front_updated_at: datetime | None = None
    desk_updated_at: datetime | None = None
    follow_up_triggered_at: datetime | None = None
    closed_at: datetime | None = None
    snoozed_at: datetime | None = None


class ChannelTalkUserChatMetrics(BaseModel):
    model_config = ConfigDict(extra="ignore")

    waiting_time: int | None = None
    avg_reply_time: int | None = None
    total_reply_time: int | None = None
    reply_count: int | None = None
    operation_waiting_time: int | None = None
    operation_avg_reply_time: int | None = None
    operation_total_reply_time: int | None = None
    operation_reply_count: int | None = None


class ChannelTalkUserChatAnchors(BaseModel):
    model_config = ConfigDict(extra="ignore")

    front_message_id: str | None = None
    desk_message_id: str | None = None
    user_last_message_id: str | None = None


class ChannelTalkUserChatDetail(BaseModel):
    model_config = ConfigDict(extra="ignore")

    channel_id: str | None = None
    user_chat_id: str
    state: ChannelTalkUserChatState
    managed: bool | None = None
    priority: str | None = None
    name: str | None = None
    goal_state: str | None = None
    customer: ChannelTalkUserFoundation | None = None
    assignment: ChannelTalkUserChatAssignment = Field(default_factory=ChannelTalkUserChatAssignment)
    timing: ChannelTalkUserChatTiming = Field(default_factory=ChannelTalkUserChatTiming)
    metrics: ChannelTalkUserChatMetrics = Field(default_factory=ChannelTalkUserChatMetrics)
    anchors: ChannelTalkUserChatAnchors = Field(default_factory=ChannelTalkUserChatAnchors)
    tags: list[ChannelTalkUserChatTag] = Field(default_factory=list)
    raw_payload: dict[str, Any] | None = None

    @field_validator("user_chat_id")
    @classmethod
    def validate_user_chat_id(cls, value: str) -> str:
        return require_text(value, "user_chat_id")

    @classmethod
    def from_api_payload(
        cls,
        payload: Any,
        *,
        user_chat_id: str | None = None,
    ) -> "ChannelTalkUserChatDetail":
        if not isinstance(payload, Mapping):
            raise ValueError("user chat detail payload must be an object")

        root_reader = _PayloadReader(payload)
        source = _read_user_chat_source(payload)
        resolved_user_chat_id = _resolve_user_chat_id(
            source,
            user_chat_id=user_chat_id,
            error_message="user chat detail payload missing user_chat_id",
        )

        resolved_state = source.text("state")
        if resolved_state is None:
            raise ValueError("user chat detail payload missing state")

        customer = _parse_user_foundation(source, root_reader=root_reader)

        return cls(
            channel_id=_read_channel_id(source),
            user_chat_id=resolved_user_chat_id,
            state=ChannelTalkUserChatState(resolved_state),
            managed=source.boolean("managed"),
            priority=source.text("priority"),
            name=source.text("name", "displayName", "display_name"),
            goal_state=source.text("goalState", "goal_state"),
            customer=customer,
            assignment=_parse_user_chat_assignment(source, root_reader=root_reader),
            timing=ChannelTalkUserChatTiming(
                created_at=source.moment("createdAt", "created_at"),
                updated_at=source.moment("updatedAt", "updated_at"),
                first_opened_at=source.moment("firstOpenedAt", "first_opened_at"),
                opened_at=source.moment("openedAt", "opened_at"),
                first_asked_at=source.moment("firstAskedAt", "first_asked_at"),
                first_replied_at=source.moment("firstRepliedAt", "first_replied_at"),
                first_replied_at_after_open=source.moment(
                    "firstRepliedAtAfterOpen",
                    "first_replied_at_after_open",
                ),
                front_updated_at=source.moment("frontUpdatedAt", "front_updated_at"),
                desk_updated_at=source.moment("deskUpdatedAt", "desk_updated_at"),
                follow_up_triggered_at=source.moment(
                    "followUpTriggeredAt",
                    "follow_up_triggered_at",
                ),
                closed_at=source.moment("closedAt", "closed_at"),
                snoozed_at=source.moment("snoozedAt", "snoozed_at"),
            ),
            metrics=ChannelTalkUserChatMetrics(
                waiting_time=source.integer("waitingTime", "waiting_time"),
                avg_reply_time=source.integer("avgReplyTime", "avg_reply_time"),
                total_reply_time=source.integer("totalReplyTime", "total_reply_time"),
                reply_count=source.integer("replyCount", "reply_count"),
                operation_waiting_time=source.integer(
                    "operationWaitingTime",
                    "operation_waiting_time",
                ),
                operation_avg_reply_time=source.integer(
                    "operationAvgReplyTime",
                    "operation_avg_reply_time",
                ),
                operation_total_reply_time=source.integer(
                    "operationTotalReplyTime",
                    "operation_total_reply_time",
                ),
                operation_reply_count=source.integer(
                    "operationReplyCount",
                    "operation_reply_count",
                ),
            ),
            anchors=ChannelTalkUserChatAnchors(
                front_message_id=source.text("frontMessageId", "front_message_id"),
                desk_message_id=source.text("deskMessageId", "desk_message_id"),
                user_last_message_id=source.text(
                    "userLastMessageId",
                    "user_last_message_id",
                ),
            ),
            tags=_parse_user_chat_tags(source),
            raw_payload=dict(payload),
        )


class ChannelTalkUserChatMessageAuthor(BaseModel):
    model_config = ConfigDict(extra="ignore")

    author_type: str | None = None
    bot_id: str | None = None
    user_id: str | None = None
    member_id: str | None = None
    manager_id: str | None = None
    name: str | None = None
    email: str | None = None
    role_id: str | None = None
    bot_name: str | None = None
    is_bot: bool = False


class ChannelTalkUserChatMessageAttachment(BaseModel):
    model_config = ConfigDict(extra="ignore")

    file_key: str | None = None
    name: str | None = None
    content_type: str | None = None
    size: int | None = None
    url: str | None = None


class ChannelTalkUserChatMessageButton(BaseModel):
    model_config = ConfigDict(extra="ignore")

    text: str | None = None
    action: str | None = None
    value: str | None = None
    url: str | None = None


class ChannelTalkUserChatMessageBlock(BaseModel):
    model_config = ConfigDict(extra="ignore")

    block_type: str | None = None
    text: str | None = None
    label: str | None = None
    name: str | None = None
    value: str | None = None
    raw_payload: dict[str, Any] | None = None


class ChannelTalkUserChatMessageLog(BaseModel):
    model_config = ConfigDict(extra="ignore")

    action: str | None = None
    log_type: str | None = None
    actor_name: str | None = None
    raw_payload: dict[str, Any] | None = None


class ChannelTalkUserChatMessageFormInput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    label: str | None = None
    input_type: str | None = None
    data_type: str | None = None
    binding_key: str | None = None
    value: str | None = None


class ChannelTalkUserChatMessageForm(BaseModel):
    model_config = ConfigDict(extra="ignore")

    form_type: str | None = None
    submitted_at: datetime | None = None
    inputs: list[ChannelTalkUserChatMessageFormInput] = Field(default_factory=list)
    raw_payload: dict[str, Any] | None = None


class ChannelTalkUserChatMessageWebPage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    url: str | None = None
    title: str | None = None
    site_name: str | None = None
    publisher: str | None = None
    author: str | None = None
    raw_payload: dict[str, Any] | None = None


class ChannelTalkUserChatMessage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message_id: str
    user_chat_id: str
    message_type: str | None = None
    person_type: str | None = None
    author: ChannelTalkUserChatMessageAuthor | None = None
    plain_text: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    is_private: bool | None = None
    attachments: list[ChannelTalkUserChatMessageAttachment] = Field(default_factory=list)
    buttons: list[ChannelTalkUserChatMessageButton] = Field(default_factory=list)
    blocks: list[ChannelTalkUserChatMessageBlock] = Field(default_factory=list)
    log: ChannelTalkUserChatMessageLog | None = None
    form: ChannelTalkUserChatMessageForm | None = None
    web_page: ChannelTalkUserChatMessageWebPage | None = None
    raw_payload: dict[str, Any] | None = None

    @field_validator("message_id", "user_chat_id")
    @classmethod
    def validate_required_text(cls, value: str, info: ValidationInfo) -> str:
        return require_text(value, info.field_name)

    @classmethod
    def from_api_payload(
        cls,
        payload: Any,
        *,
        user_chat_id: str,
        root_bots: list[Mapping[str, Any]] | None = None,
    ) -> "ChannelTalkUserChatMessage":
        if not isinstance(payload, Mapping):
            raise ValueError("user chat message payload must be an object")

        reader = _PayloadReader(payload)
        message_id = reader.text("id", "messageId", "message_id")
        if message_id is None:
            raise ValueError("user chat message payload missing message id")

        requested_user_chat_id = require_text(user_chat_id, "user_chat_id")
        payload_user_chat_id = reader.text("userChatId", "user_chat_id")
        if payload_user_chat_id is not None and payload_user_chat_id != requested_user_chat_id:
            raise ValueError("user chat message payload user_chat_id mismatch")

        resolved_user_chat_id = payload_user_chat_id or requested_user_chat_id
        attachments = _parse_message_attachments(reader)
        buttons = _parse_message_buttons(reader)
        blocks = _parse_message_blocks(reader)
        message_log = _parse_message_log(reader)
        message_form = _parse_message_form(reader)
        message_web_page = _parse_message_web_page(reader)

        return cls(
            message_id=message_id,
            user_chat_id=require_text(resolved_user_chat_id, "user_chat_id"),
            message_type=reader.text("type", "messageType", "message_type"),
            person_type=reader.text("personType", "person_type"),
            author=_parse_user_chat_message_author(reader, root_bots=root_bots),
            plain_text=_read_message_plain_text(
                reader,
                blocks=blocks,
                message_log=message_log,
                message_form=message_form,
                message_web_page=message_web_page,
            ),
            created_at=reader.moment("createdAt", "created_at"),
            updated_at=reader.moment("updatedAt", "updated_at"),
            is_private=_read_message_is_private(reader),
            attachments=attachments,
            buttons=buttons,
            blocks=blocks,
            log=message_log,
            form=message_form,
            web_page=message_web_page,
            raw_payload=dict(payload),
        )


class ChannelTalkUserChatMessagePage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    messages: list[ChannelTalkUserChatMessage]
    next_cursor: str | None = None
    quota_snapshot: FullSyncQuotaSnapshot = Field(default_factory=FullSyncQuotaSnapshot)

    @classmethod
    def from_api_payload(
        cls,
        payload: Any,
        *,
        user_chat_id: str,
        headers: Mapping[str, Any] | None = None,
    ) -> "ChannelTalkUserChatMessagePage":
        root_reader = _PayloadReader(payload) if isinstance(payload, Mapping) else None
        root_bots = []
        if root_reader is not None:
            root_bots = [
                value for value in root_reader.items("bots")
                if isinstance(value, Mapping)
            ]
        messages, next_cursor = _parse_metadata_page(
            payload,
            item_keys=("messages", "results", "items"),
            parse_item=lambda item: ChannelTalkUserChatMessage.from_api_payload(
                item,
                user_chat_id=user_chat_id,
                root_bots=root_bots,
            ),
            error_message="user chat message list payload must be an object or list",
        )

        return cls(
            messages=messages,
            next_cursor=next_cursor,
            quota_snapshot=_parse_quota_snapshot(headers),
        )


def _parse_metadata_page(
    payload: Any,
    *,
    item_keys: tuple[str, ...],
    parse_item: Callable[[Mapping[str, Any]], ParsedMetadataItem],
    error_message: str,
) -> tuple[list[ParsedMetadataItem], str | None]:
    if isinstance(payload, list):
        items = payload
        next_page_token = None
    elif isinstance(payload, Mapping):
        reader = _PayloadReader(payload)
        items = reader.items(*item_keys)
        next_page_token = reader.text("next", "nextId", "nextCursor")
    else:
        raise ValueError(error_message)

    return (
        [parse_item(item) for item in items if isinstance(item, Mapping)],
        next_page_token,
    )


def _parse_manager_ids(reader: "_PayloadReader") -> tuple[str, ...]:
    manager_ids: list[str] = []
    for value in reader.items("managerIds", "manager_ids", "managers"):
        manager_id = _read_manager_id(value)
        if manager_id is not None:
            manager_ids.append(manager_id)
    return tuple(manager_ids)


def _read_manager_id(value: Any) -> str | None:
    if isinstance(value, Mapping):
        return _PayloadReader(value).text("id", "managerId", "manager_id")

    return str(value).strip() or None


def _read_channel_id(reader: "_PayloadReader") -> str | None:
    return reader.text("channelId", "channel_id") or (
        reader.nested("channel") and reader.nested("channel").text("id", "channelId", "channel_id")
    )


def _read_user_chat_source(payload: Mapping[str, Any]) -> "_PayloadReader":
    """우선 canonical user-chat 객체를 읽고, 없으면 루트 payload로 fallback한다.

    Channel Talk 응답은 어떤 경우에는 실제 채팅 본문이 `userChat` 아래에 중첩되고,
    어떤 경우에는 같은 필드가 top-level에 평평하게 들어온다.
    """
    reader = _PayloadReader(payload)
    return reader.nested("userChat", "user_chat") or reader


def _resolve_user_chat_id(
    reader: "_PayloadReader",
    *,
    user_chat_id: str | None,
    error_message: str,
) -> str:
    """upstream chat-id alias를 하나의 필수 내부 필드로 정규화한다.

    우리 코드 내부에서는 canonical 이름을 `user_chat_id` 하나로만 유지한다.
    다만 API boundary에서는 `id` / `userChatId` 같은 관측된 upstream alias를
    받아들인 뒤, 요청에 사용한 chat id와 일치하는지도 함께 검증한다.
    """
    requested_user_chat_id = (
        require_text(user_chat_id, "user_chat_id")
        if user_chat_id is not None
        else None
    )
    resolved_user_chat_id = reader.text("id", "userChatId", "user_chat_id")
    if resolved_user_chat_id is None:
        if requested_user_chat_id is None:
            raise ValueError(error_message)
        return requested_user_chat_id
    if (
        requested_user_chat_id is not None
        and resolved_user_chat_id != requested_user_chat_id
    ):
        raise ValueError("user chat detail payload user_chat_id mismatch")
    return resolved_user_chat_id


def _read_user_identity(
    reader: "_PayloadReader",
    *,
    root_users: list[Mapping[str, Any]] | None = None,
) -> tuple[str | None, str | None]:
    """고객 식별자를 inline object -> local users -> root users 순서로 복구한다."""
    user_reader = reader.nested("user", "customer")
    user_id = reader.text(
        "userId",
        "user_id",
        "externalUserId",
        "external_user_id",
    ) or (user_reader and user_reader.text("id", "userId", "externalUserId"))
    member_id = reader.text("memberId", "member_id") or (
        user_reader and user_reader.text("memberId", "member_id")
    )
    if user_id is None or member_id is None:
        collection_user_id, collection_member_id = _read_users_identity(
            reader,
            root_users=root_users,
            expected_user_id=user_id,
            expected_member_id=member_id,
        )
        user_id = user_id or collection_user_id
        member_id = member_id or collection_member_id
    return user_id, member_id


def _read_users_identity(
    reader: "_PayloadReader",
    *,
    root_users: list[Mapping[str, Any]] | None = None,
    expected_user_id: str | None = None,
    expected_member_id: str | None = None,
) -> tuple[str | None, str | None]:
    local_candidates = [
        value for value in reader.items("users")
        if isinstance(value, Mapping)
    ]
    local_match = _select_user_identity_candidate(
        local_candidates,
        expected_user_id=expected_user_id,
        expected_member_id=expected_member_id,
        allow_singleton_fallback=(
            expected_user_id is None
            and expected_member_id is None
        ),
    )
    if local_match != (None, None):
        return local_match

    root_candidates = [value for value in (root_users or []) if isinstance(value, Mapping)]
    return _select_user_identity_candidate(
        root_candidates,
        expected_user_id=expected_user_id,
        expected_member_id=expected_member_id,
        allow_singleton_fallback=False,
    )


def _select_user_identity_candidate(
    candidates: list[Mapping[str, Any]],
    *,
    expected_user_id: str | None,
    expected_member_id: str | None,
    allow_singleton_fallback: bool,
) -> tuple[str | None, str | None]:
    normalized_expected_user_id = str(expected_user_id or "").strip() or None
    normalized_expected_member_id = str(expected_member_id or "").strip() or None
    parsed_candidates: list[tuple[str | None, str | None]] = []

    for value in candidates:
        item_reader = _PayloadReader(value)
        user_id = item_reader.text(
            "id",
            "userId",
            "externalUserId",
            "external_user_id",
        )
        member_id = item_reader.text("memberId", "member_id")
        if user_id is None and member_id is None:
            continue
        parsed_candidates.append((user_id, member_id))

    if not parsed_candidates:
        return None, None

    if normalized_expected_user_id is not None or normalized_expected_member_id is not None:
        for user_id, member_id in parsed_candidates:
            if (
                normalized_expected_user_id is not None
                and user_id == normalized_expected_user_id
            ) or (
                normalized_expected_member_id is not None
                and member_id == normalized_expected_member_id
            ):
                return user_id, member_id
        return None, None

    if allow_singleton_fallback and len(parsed_candidates) == 1:
        return parsed_candidates[0]

    return None, None


def _parse_user_foundation(
    reader: "_PayloadReader",
    *,
    root_reader: "_PayloadReader | None" = None,
) -> ChannelTalkUserFoundation | None:
    """가능하면 중첩된 user 객체로 customer foundation을 만든다.

    Channel Talk가 nested user object를 생략한 경우에는 현재 payload 전체를
    customer data로 취급하지 않고, allowlist에 포함된 user 성격의 키만 골라서 쓴다.
    """
    payload = (
        reader.mapping("user", "customer")
        or (root_reader and root_reader.mapping("user", "customer"))
    )
    if payload is None:
        if reader.text(
            "userId",
            "externalUserId",
            "external_user_id",
            "memberId",
            "member_id",
        ) is None:
            return None
        payload = {
            key: value
            for key, value in reader.payload.items()
            if key
            in {
                "channelId",
                "channel_id",
                "userId",
                "externalUserId",
                "external_user_id",
                "veilId",
                "veil_id",
                "unifiedId",
                "unified_id",
                "memberId",
                "member_id",
                "type",
                "userType",
                "user_type",
                "name",
                "email",
                "mobileNumber",
                "mobile_number",
                "avatarUrl",
                "avatarURL",
                "avatar_url",
                "blocked",
                "language",
                "country",
                "city",
                "lastSeenAt",
                "last_seen_at",
                "createdAt",
                "remoteCreatedAt",
                "remote_created_at",
                "updatedAt",
                "remoteUpdatedAt",
                "remote_updated_at",
                "profile",
            }
        }
        if not payload:
            return None

    try:
        return ChannelTalkUserFoundation.from_api_payload(payload)
    except ValueError:
        return None


def _parse_user_chat_assignment(
    reader: "_PayloadReader",
    *,
    root_reader: "_PayloadReader | None" = None,
) -> ChannelTalkUserChatAssignment:
    # 내부 계약에서는 assignee 필드를 하나로만 유지한다.
    # 다만 upstream은 nested assignee object 또는 `assigneeId` 둘 중 하나로 표현할 수 있다.
    assignee_reader = reader.nested("assignee", "assignedManager", "manager")
    assignee = _parse_manager_ref(assignee_reader.payload) if assignee_reader is not None else None
    assignee_id = reader.text("assigneeId", "assignee_id") or (
        assignee.manager_id if assignee is not None else None
    )
    first_assignee_id_after_open = reader.text(
        "firstAssigneeIdAfterOpen",
        "first_assignee_id_after_open",
    )
    manager_ids = tuple(
        dict.fromkeys(
            [
                *_parse_manager_ids(reader),
                *([assignee_id] if assignee_id is not None else []),
            ]
        )
    )
    managers = _parse_manager_refs(
        reader,
        root_reader=root_reader,
        relevant_manager_ids=manager_ids,
    )
    assignee_manager = assignee or next(
        (
            manager
            for manager in managers
            if manager.manager_id == assignee_id
        ),
        None,
    )

    return ChannelTalkUserChatAssignment(
        manager_ids=manager_ids,
        managers=managers,
        assignee_id=assignee_id,
        assignee_name=assignee_manager.name if assignee_manager else None,
        assignee_email=assignee_manager.email if assignee_manager else None,
        first_assignee_id_after_open=first_assignee_id_after_open,
    )


def _parse_manager_refs(
    reader: "_PayloadReader",
    *,
    root_reader: "_PayloadReader | None" = None,
    relevant_manager_ids: tuple[str, ...] = (),
) -> list[ChannelTalkUserChatManagerRef]:
    managers_by_id: dict[str, ChannelTalkUserChatManagerRef] = {}
    candidates = [*reader.items("managers")]
    if (
        root_reader is not None
        and root_reader.payload is not reader.payload
    ):
        candidates.extend(root_reader.items("managers"))
    for value in candidates:
        manager = _parse_manager_ref(value)
        if manager is not None:
            managers_by_id.setdefault(manager.manager_id, manager)

    if relevant_manager_ids:
        return [
            managers_by_id[manager_id]
            for manager_id in relevant_manager_ids
            if manager_id in managers_by_id
        ]

    return list(managers_by_id.values())


def _parse_manager_ref(value: Any) -> ChannelTalkUserChatManagerRef | None:
    if not isinstance(value, Mapping):
        return None

    try:
        return ChannelTalkUserChatManagerRef.from_api_payload(value)
    except ValueError:
        return None


def _parse_user_chat_tags(reader: "_PayloadReader") -> list[ChannelTalkUserChatTag]:
    tags: list[ChannelTalkUserChatTag] = []
    for value in reader.items("tags", "taggings"):
        tag = ChannelTalkUserChatTag.from_api_payload(value)
        if tag.key or tag.name:
            tags.append(tag)
    return tags


def _parse_message_attachments(reader: "_PayloadReader") -> list[ChannelTalkUserChatMessageAttachment]:
    attachments: list[ChannelTalkUserChatMessageAttachment] = []
    for value in [*reader.items("attachments"), *reader.items("files")]:
        if not isinstance(value, Mapping):
            continue
        item_reader = _PayloadReader(value)
        attachments.append(
            ChannelTalkUserChatMessageAttachment(
                file_key=item_reader.text("key", "fileKey", "file_key", "id"),
                name=item_reader.text("name", "filename", "fileName", "file_name"),
                content_type=item_reader.text(
                    "contentType",
                    "content_type",
                    "mimeType",
                    "mime_type",
                ),
                size=item_reader.integer("size", "contentLength", "content_length"),
                url=item_reader.text("url", "downloadUrl", "download_url"),
            )
        )
    return attachments


def _parse_message_buttons(reader: "_PayloadReader") -> list[ChannelTalkUserChatMessageButton]:
    buttons: list[ChannelTalkUserChatMessageButton] = []
    for value in reader.items("buttons"):
        if not isinstance(value, Mapping):
            continue
        item_reader = _PayloadReader(value)
        buttons.append(
            ChannelTalkUserChatMessageButton(
                text=item_reader.text("text", "title", "label", "name"),
                action=item_reader.text("action", "type"),
                value=item_reader.text("value", "payload", "id"),
                url=item_reader.text("url", "href"),
            )
        )
    return buttons


def _parse_message_blocks(reader: "_PayloadReader") -> list[ChannelTalkUserChatMessageBlock]:
    blocks: list[ChannelTalkUserChatMessageBlock] = []
    for value in reader.items("blocks"):
        if not isinstance(value, Mapping):
            continue
        item_reader = _PayloadReader(value)
        blocks.append(
            ChannelTalkUserChatMessageBlock(
                block_type=item_reader.text("type", "blockType", "block_type"),
                text=item_reader.text("text", "plainText", "plain_text", "label", "value"),
                label=item_reader.text("label", "title"),
                name=item_reader.text("name"),
                value=item_reader.text("value"),
                raw_payload=dict(value),
            )
        )
    return blocks


def _parse_message_log(reader: "_PayloadReader") -> ChannelTalkUserChatMessageLog | None:
    log_reader = reader.nested("log")
    if log_reader is None:
        return None
    return ChannelTalkUserChatMessageLog(
        action=log_reader.text("action", "name", "type"),
        log_type=log_reader.text("type"),
        actor_name=log_reader.text("name", "actorName", "actor_name"),
        raw_payload=dict(log_reader.payload),
    )


def _parse_message_form(reader: "_PayloadReader") -> ChannelTalkUserChatMessageForm | None:
    form_reader = reader.nested("form")
    if form_reader is None:
        return None

    inputs: list[ChannelTalkUserChatMessageFormInput] = []
    for value in form_reader.items("inputs"):
        if not isinstance(value, Mapping):
            continue
        item_reader = _PayloadReader(value)
        inputs.append(
            ChannelTalkUserChatMessageFormInput(
                label=item_reader.text("label", "name"),
                input_type=item_reader.text("type", "inputType", "input_type"),
                data_type=item_reader.text("dataType", "data_type"),
                binding_key=item_reader.text("bindingKey", "binding_key"),
                value=_stringify_message_value(item_reader.payload.get("value")),
            )
        )

    return ChannelTalkUserChatMessageForm(
        form_type=form_reader.text("type", "formType", "form_type"),
        submitted_at=form_reader.moment("submittedAt", "submitted_at"),
        inputs=inputs,
        raw_payload=dict(form_reader.payload),
    )


def _parse_message_web_page(reader: "_PayloadReader") -> ChannelTalkUserChatMessageWebPage | None:
    web_page_reader = reader.nested("webPage", "web_page")
    if web_page_reader is None:
        return None

    return ChannelTalkUserChatMessageWebPage(
        url=web_page_reader.text("url", "href"),
        title=web_page_reader.text("title", "name"),
        site_name=web_page_reader.text("siteName", "site_name"),
        publisher=web_page_reader.text("publisher"),
        author=web_page_reader.text("author"),
        raw_payload=dict(web_page_reader.payload),
    )


def _parse_user_chat_message_author(
    reader: "_PayloadReader",
    *,
    root_bots: list[Mapping[str, Any]] | None = None,
) -> ChannelTalkUserChatMessageAuthor | None:
    """여러 upstream author shape를 하나의 typed author object로 정규화한다.

    Live payload는 어떤 경우에는 `manager` / `user` 객체를 중첩해서 보내지만,
    어떤 경우에는 `personType` + `personId` 만 보낸다. 내부 필드명은 안정적으로
    유지하고, upstream alias 해석은 이 boundary에서만 처리한다.
    """
    manager_reader = reader.nested("manager")
    user_reader = reader.nested("user", "customer")
    bot_reader = _read_message_bot(reader, root_bots=root_bots)
    person_id = reader.text("personId", "person_id")
    bot_name = reader.text("botName", "bot_name") or (
        bot_reader and bot_reader.text("name", "botName", "bot_name")
    )
    bot_id = person_id if (
        bot_reader is not None
        or reader.text("personType", "person_type") == "bot"
        or bot_name is not None
    ) else None

    author_type = reader.text("personType", "authorType", "author_type")
    if author_type is None:
        if manager_reader is not None:
            author_type = "manager"
        elif user_reader is not None:
            author_type = "customer"
        elif bot_name is not None:
            author_type = "bot"

    if (
        author_type is None
        and manager_reader is None
        and user_reader is None
        and bot_name is None
    ):
        return None

    user_id = (user_reader and user_reader.text("id", "userId", "externalUserId")) or reader.text(
        "userId",
        "user_id",
    )
    if user_id is None and author_type in {"user", "customer"}:
        user_id = person_id

    manager_id = (
        (manager_reader and manager_reader.text("id", "managerId", "manager_id"))
        or reader.text("managerId", "manager_id")
    )
    if manager_id is None and author_type == "manager":
        manager_id = person_id

    return ChannelTalkUserChatMessageAuthor(
        author_type=author_type,
        bot_id=bot_id,
        user_id=user_id,
        member_id=(user_reader and user_reader.text("memberId", "member_id"))
        or reader.text("memberId", "member_id"),
        manager_id=manager_id,
        name=(manager_reader and manager_reader.text("name", "displayName"))
        or (user_reader and user_reader.text("name"))
        or (bot_reader and bot_reader.text("name", "botName", "bot_name"))
        or bot_name
        or reader.text("name"),
        email=(manager_reader and manager_reader.text("email"))
        or (user_reader and user_reader.text("email"))
        or reader.text("email"),
        role_id=(manager_reader and manager_reader.text("roleId", "role_id"))
        or reader.text("roleId", "role_id"),
        bot_name=bot_name,
        is_bot=bool(bot_name or bot_id) or (author_type == "bot"),
    )


def _read_message_bot(
    reader: "_PayloadReader",
    *,
    root_bots: list[Mapping[str, Any]] | None = None,
) -> "_PayloadReader | None":
    person_type = reader.text("personType", "person_type")
    person_id = reader.text("personId", "person_id")

    if person_type != "bot" or person_id is None:
        return None

    candidates = [
        *reader.items("bots"),
        *(root_bots or []),
    ]

    for value in candidates:
        if not isinstance(value, Mapping):
            continue

        item_reader = _PayloadReader(value)
        if item_reader.text("id", "botId", "bot_id") == person_id:
            return item_reader

    return None


def _read_message_plain_text(
    reader: "_PayloadReader",
    blocks: list[ChannelTalkUserChatMessageBlock] | None = None,
    message_log: ChannelTalkUserChatMessageLog | None = None,
    message_form: ChannelTalkUserChatMessageForm | None = None,
    message_web_page: ChannelTalkUserChatMessageWebPage | None = None,
) -> str | None:
    plain_text = reader.text("plainText", "plain_text", "text", "body")
    if plain_text is not None:
        return plain_text

    if message_log is not None and message_log.action is not None:
        return message_log.action

    if message_form is not None:
        form_text = _build_form_plain_text(message_form)
        if form_text is not None:
            return form_text

    if message_web_page is not None:
        web_page_text = "\n".join(
            value
            for value in [message_web_page.title, message_web_page.url]
            if value is not None
        )
        if web_page_text:
            return web_page_text

    blocks = blocks or _parse_message_blocks(reader)
    block_texts = [
        block.text
        for block in blocks
        if block.text is not None
    ]
    if block_texts:
        return "\n".join(block_texts)

    return None


def _build_form_plain_text(message_form: ChannelTalkUserChatMessageForm) -> str | None:
    parts = [
        _format_form_input_text(item)
        for item in message_form.inputs
    ]
    filtered_parts = [value for value in parts if value is not None]
    if filtered_parts:
        return "\n".join(filtered_parts)
    return message_form.form_type


def _format_form_input_text(item: ChannelTalkUserChatMessageFormInput) -> str | None:
    if item.label is not None and item.value is not None:
        return f"{item.label}: {item.value}"
    return item.value or item.label


def _stringify_message_value(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, Mapping):
        for key in ("text", "value", "label", "name", "url", "title"):
            text = _PayloadReader(value).text(key)
            if text is not None:
                return text
        return str(dict(value)).strip() or None
    if isinstance(value, list):
        parts = [_stringify_message_value(item) for item in value]
        filtered_parts = [part for part in parts if part is not None]
        return ", ".join(filtered_parts) or None
    text = str(value).strip()
    return text or None


def _read_message_is_private(reader: "_PayloadReader") -> bool | None:
    is_private = reader.boolean("private", "isPrivate", "is_private")
    if is_private is not None:
        return is_private

    for value in reader.items("options"):
        if isinstance(value, str) and value.strip().lower() == "private":
            return True

    return None


def _read_user_chat_ordering_marker(reader: "_PayloadReader") -> datetime | None:
    nested_message = reader.nested("lastMessage", "latestMessage", "last_message")
    return reader.moment(
        "updatedAt",
        "lastUpdatedAt",
        "closedAt",
        "snoozedAt",
        "openedAt",
        "createdAt",
        "updated_at",
        "created_at",
    ) or (
        nested_message and nested_message.moment("createdAt", "updatedAt", "timestamp")
    )


def _parse_quota_snapshot(headers: Mapping[str, Any] | None) -> FullSyncQuotaSnapshot:
    if not headers:
        return FullSyncQuotaSnapshot()

    normalized = {
        str(key).strip().lower(): str(value).strip()
        for key, value in headers.items()
        if key is not None and value is not None and str(value).strip()
    }
    source_headers_present = any(
        key in normalized
        for key in (
            "retry-after",
            "x-ratelimit-bucket",
            "x-rate-limit-bucket",
            "x-ratelimit-limit",
            "x-rate-limit-limit",
            "x-ratelimit-remaining",
            "x-rate-limit-remaining",
            "x-ratelimit-reset",
            "x-rate-limit-reset",
            "x-ratelimit-reset-at",
            "x-rate-limit-reset-at",
        )
    )

    return FullSyncQuotaSnapshot(
        bucket=_read_header_text(
            normalized,
            "x-ratelimit-bucket",
            "x-rate-limit-bucket",
        ),
        limit=_read_header_int(
            normalized,
            "x-ratelimit-limit",
            "x-rate-limit-limit",
        ),
        remaining=_read_header_int(
            normalized,
            "x-ratelimit-remaining",
            "x-rate-limit-remaining",
        ),
        reset_at=_read_header_datetime(
            normalized,
            "x-ratelimit-reset-at",
            "x-rate-limit-reset-at",
            "x-ratelimit-reset",
            "x-rate-limit-reset",
        ),
        retry_after_seconds=_read_header_int(normalized, "retry-after"),
        source_headers_present=source_headers_present,
    )


def _read_header_text(headers: Mapping[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = headers.get(key)
        if value:
            return str(value)
    return None


def _read_header_int(headers: Mapping[str, Any], *keys: str) -> int | None:
    value = _read_header_text(headers, *keys)
    if value is None:
        return None

    try:
        return max(0, int(float(value)))
    except (TypeError, ValueError):
        return None


def _read_header_datetime(headers: Mapping[str, Any], *keys: str) -> datetime | None:
    value = _read_header_text(headers, *keys)
    if value is None:
        return None
    return _PayloadReader._parse_datetime(value)


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

    def integer(self, *keys: str) -> int | None:
        for key in keys:
            value = self.payload.get(key)
            if value is None:
                continue
            try:
                return int(float(value))
            except (TypeError, ValueError):
                continue
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
