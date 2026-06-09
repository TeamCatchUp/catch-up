from __future__ import annotations

from typing import Protocol

from catchup.connectors.channel_talk.core.user_chat_ids import build_user_chat_desk_url
from catchup.connectors.channel_talk.core.user_chat_ids import (
    build_user_chat_document_id,
)
from catchup.connectors.channel_talk.core.user_chat_message_renderer import (
    UserChatMessageRenderer,
)
from catchup.connectors.channel_talk.schemas.channel_metadata import (
    ChannelTalkManagerMetadata,
)
from catchup.sync.ingestion.adapters.channel_talk.user_chat_models import (
    ChannelTalkFetchedUserChat,
)
from catchup.sync.ingestion.adapters.channel_talk.user_chat_models import (
    ChannelTalkUserChatPreparedDocument,
)
from catchup.sync.ingestion.document_format import ChannelTalkUserChatAnchorsMetadata
from catchup.sync.ingestion.document_format import ChannelTalkUserChatAssignmentMetadata
from catchup.sync.ingestion.document_format import ChannelTalkUserChatChatMetadata
from catchup.sync.ingestion.document_format import ChannelTalkUserChatChunkMetadata
from catchup.sync.ingestion.document_format import ChannelTalkUserChatCoreMetadata
from catchup.sync.ingestion.document_format import ChannelTalkUserChatCustomerMetadata
from catchup.sync.ingestion.document_format import ChannelTalkUserChatLogicalMetadata
from catchup.sync.ingestion.document_format import ChannelTalkUserChatMessageMetadata
from catchup.sync.ingestion.document_format import ChannelTalkUserChatMetricsMetadata
from catchup.sync.ingestion.document_format import ChannelTalkUserChatTagsMetadata
from catchup.sync.ingestion.document_format import ChannelTalkUserChatTimingMetadata
from catchup.sync.ingestion.document_format import DocumentBaseMetadata
from catchup.sync.ingestion.schemas import SyncWindow


class UserChatExecution(Protocol):
    @property
    def channel_id(self) -> str: ...


class UserChatTransformer:
    def __init__(self, renderer: UserChatMessageRenderer | None = None) -> None:
        self._renderer = renderer or UserChatMessageRenderer()

    def build(
        self,
        *,
        execution: UserChatExecution,
        sync_window: SyncWindow,
        bundle: ChannelTalkFetchedUserChat,
        managers_by_id: dict[str, ChannelTalkManagerMetadata],
    ) -> ChannelTalkUserChatPreparedDocument:
        detail = bundle.detail
        assignment = detail.assignment
        messages = bundle.messages
        included_messages, excluded_count = self._renderer.partition_messages(messages)
        message_timestamps = [
            timestamp
            for message in messages
            if (timestamp := self._renderer.message_timestamp(message)) is not None
        ]
        last_message_at = max(message_timestamps, default=None)
        author_types = tuple(
            dict.fromkeys(
                filter(
                    None,
                    [
                        (
                            message.author.author_type
                            if message.author is not None
                            else message.person_type
                        )
                        or message.person_type
                        for message in messages
                    ],
                )
            )
        )
        contains_bot_messages = any(
            message.author is not None and message.author.is_bot for message in messages
        )
        contains_private_events = any(
            message.is_private is True for message in messages
        )
        contains_form_messages = any(message.form is not None for message in messages)

        contextual_content = self._renderer.build_contextual_content(
            detail=detail,
            included_messages=included_messages,
            managers_by_id=managers_by_id,
        )
        customer = detail.customer
        assignee_id = assignment.assignee_id
        assignee_manager = (
            managers_by_id.get(assignee_id) if assignee_id is not None else None
        )
        assignee_name = assignment.assignee_name or (
            assignee_manager.name if assignee_manager is not None else None
        )
        assignee_email = assignment.assignee_email or (
            assignee_manager.email if assignee_manager is not None else None
        )
        manager_names = self._renderer.resolve_manager_names(
            manager_ids=assignment.manager_ids,
            managers_by_id=managers_by_id,
            fallback_managers=assignment.managers,
        )
        manager_role_ids = self._renderer.resolve_manager_role_ids(
            manager_ids=assignment.manager_ids,
            managers_by_id=managers_by_id,
            fallback_managers=assignment.managers,
        )
        logical_metadata = ChannelTalkUserChatLogicalMetadata(
            base=DocumentBaseMetadata(
                source="channel_talk",
                record_id=detail.user_chat_id,
                url=build_user_chat_desk_url(
                    channel_id=execution.channel_id,
                    user_chat_id=detail.user_chat_id,
                ),
                created_at=detail.timing.created_at,
                updated_at=(
                    detail.timing.desk_updated_at
                    or detail.timing.updated_at
                    or last_message_at
                ),
                synced_at=sync_window.window_end,
                contextual_content=contextual_content,
            ),
            user_chat_core=ChannelTalkUserChatCoreMetadata(
                chat=ChannelTalkUserChatChatMetadata(
                    channel_id=execution.channel_id,
                    channel_name=bundle.channel_name,
                    user_chat_id=detail.user_chat_id,
                    state=detail.state.value,
                    managed=detail.managed,
                    priority=detail.priority,
                    customer_name=detail.name,
                    description=detail.description,
                    goal_state=detail.goal_state,
                ),
                customer=ChannelTalkUserChatCustomerMetadata(
                    user_id=(
                        customer.external_user_id
                        if customer is not None
                        else bundle.list_item.user_id
                    ),
                    member_id=(
                        customer.member_id
                        if customer is not None
                        else bundle.list_item.member_id
                    ),
                    veil_id=customer.veil_id if customer is not None else None,
                    unified_id=customer.unified_id if customer is not None else None,
                    type=customer.user_type if customer is not None else None,
                    name=customer.name if customer is not None else None,
                    email=customer.email if customer is not None else None,
                    mobile_number=(
                        customer.mobile_number if customer is not None else None
                    ),
                    avatar_url=customer.avatar_url if customer is not None else None,
                    language=customer.language if customer is not None else None,
                    country=customer.country if customer is not None else None,
                    city=customer.city if customer is not None else None,
                    time_zone=None,
                ),
                assignment=ChannelTalkUserChatAssignmentMetadata(
                    manager_ids=list(assignment.manager_ids),
                    assignee_id=assignee_id,
                    assignee_name=assignee_name,
                    assignee_email=assignee_email,
                    first_assignee_id_after_open=assignment.first_assignee_id_after_open,
                    manager_names=manager_names,
                    manager_role_ids=manager_role_ids,
                ),
                messages=ChannelTalkUserChatMessageMetadata(
                    message_ids=[message.message_id for message in messages],
                    last_message_at=last_message_at,
                    included_message_count=len(included_messages),
                    excluded_message_count=excluded_count,
                    author_types=list(author_types),
                    contains_bot_messages=contains_bot_messages,
                    contains_private_events=contains_private_events,
                    contains_form_messages=contains_form_messages,
                ),
                timing=ChannelTalkUserChatTimingMetadata(
                    first_opened_at=detail.timing.first_opened_at,
                    opened_at=detail.timing.opened_at,
                    first_asked_at=detail.timing.first_asked_at,
                    first_replied_at=detail.timing.first_replied_at,
                    first_replied_at_after_open=detail.timing.first_replied_at_after_open,
                    front_updated_at=detail.timing.front_updated_at,
                    desk_updated_at=detail.timing.desk_updated_at,
                    follow_up_triggered_at=detail.timing.follow_up_triggered_at,
                    closed_at=detail.timing.closed_at,
                    snoozed_at=detail.timing.snoozed_at,
                ),
                metrics=ChannelTalkUserChatMetricsMetadata(
                    waiting_time=detail.metrics.waiting_time,
                    avg_reply_time=detail.metrics.avg_reply_time,
                    total_reply_time=detail.metrics.total_reply_time,
                    reply_count=detail.metrics.reply_count,
                    operation_waiting_time=detail.metrics.operation_waiting_time,
                    operation_avg_reply_time=detail.metrics.operation_avg_reply_time,
                    operation_total_reply_time=detail.metrics.operation_total_reply_time,
                    operation_reply_count=detail.metrics.operation_reply_count,
                ),
                anchors=ChannelTalkUserChatAnchorsMetadata(
                    front_message_id=detail.anchors.front_message_id,
                    desk_message_id=detail.anchors.desk_message_id,
                    user_last_message_id=detail.anchors.user_last_message_id,
                ),
                tags=ChannelTalkUserChatTagsMetadata(
                    keys=[tag.key for tag in detail.tags if tag.key is not None],
                    names=[tag.name for tag in detail.tags if tag.name is not None],
                ),
                chunk=ChannelTalkUserChatChunkMetadata(
                    chunk_index=0,
                    chunk_count=1,
                ),
            ),
        )
        return ChannelTalkUserChatPreparedDocument(
            document_id=build_user_chat_document_id(
                channel_id=execution.channel_id,
                user_chat_id=detail.user_chat_id,
            ),
            page_content=contextual_content,
            logical_metadata=logical_metadata,
            storage_metadata=logical_metadata.to_storage_metadata(),
        )
