from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import field_validator

from catchup.connectors.channel_talk.schemas._parsing import _parse_manager_ids
from catchup.connectors.channel_talk.schemas._parsing import _parse_metadata_page
from catchup.connectors.channel_talk.schemas._parsing import _PayloadReader
from catchup.connectors.channel_talk.schemas._parsing import _read_channel_id
from catchup.connectors.channel_talk.schemas._parsing import _read_header_datetime
from catchup.connectors.channel_talk.schemas._parsing import _read_header_int
from catchup.connectors.channel_talk.schemas._parsing import _read_header_text
from catchup.connectors.channel_talk.schemas.user import ChannelTalkUserFoundation
from catchup.connectors.channel_talk.schemas.user import _parse_user_foundation
from catchup.connectors.channel_talk.schemas.user import _read_user_identity
from catchup.utils.validation import require_text


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
            item_keys=("userChats",),
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
        manager_id = reader.text("id")
        if manager_id is None:
            raise ValueError("manager ref payload missing manager id")

        return cls(
            manager_id=manager_id,
            name=reader.text("name", "displayName", "display_name"),
            email=reader.text("email"),
            role_id=reader.text("roleId"),
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
                key=reader.text("key"),
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
    description: str | None = None
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
            description=source.text("description"),
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
                front_message_id=source.text("frontMessageId"),
                desk_message_id=source.text("deskMessageId"),
                user_last_message_id=source.text("userLastMessageId"),
            ),
            tags=_parse_user_chat_tags(source),
            raw_payload=dict(payload),
        )

def _read_user_chat_source(payload: Mapping[str, Any]) -> "_PayloadReader":
    """우선 canonical user-chat 객체를 읽고, 없으면 루트 payload로 fallback한다.

    Channel Talk 응답은 어떤 경우에는 실제 채팅 본문이 `userChat` 아래에 중첩되고,
    어떤 경우에는 같은 필드가 top-level에 평평하게 들어온다.
    """
    reader = _PayloadReader(payload)
    return reader.nested("userChat") or reader


def _resolve_user_chat_id(
    reader: "_PayloadReader",
    *,
    user_chat_id: str | None,
    error_message: str,
) -> str:
    """공식 UserChat 객체의 `id`만 내부 `user_chat_id`로 정규화한다."""
    requested_user_chat_id = (
        require_text(user_chat_id, "user_chat_id")
        if user_chat_id is not None
        else None
    )
    resolved_user_chat_id = reader.text("id")
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

def _parse_user_chat_assignment(
    reader: "_PayloadReader",
    *,
    root_reader: _PayloadReader | None = None,
) -> ChannelTalkUserChatAssignment:
    # 내부 계약에서는 assignee 필드를 하나로만 유지한다.
    # 다만 upstream은 nested assignee object 또는 `assigneeId` 둘 중 하나로 표현할 수 있다.
    assignee_reader = reader.nested("assignee", "manager")
    assignee = _parse_manager_ref(assignee_reader.payload) if assignee_reader is not None else None
    assignee_id = reader.text("assigneeId") or (
        assignee.manager_id if assignee is not None else None
    )
    first_assignee_id_after_open = reader.text("firstAssigneeIdAfterOpen")
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
    root_reader: _PayloadReader | None = None,
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
