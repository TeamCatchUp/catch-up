from __future__ import annotations

from datetime import datetime
from datetime import timezone
from typing import Any

from langchain_core.documents import Document

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
from catchup.connectors.channel_talk.schemas.user import ChannelTalkUserFoundation
from catchup.connectors.channel_talk.schemas.user_chat import ChannelTalkUserChatDetail
from catchup.connectors.channel_talk.schemas.user_chat_message import (
    ChannelTalkUserChatMessage,
)
from catchup.sync.ingestion.adapters.channel_talk.user_chat_models import (
    ChannelTalkFetchedUserChat,
)
from catchup.sync.ingestion.vector_records.channel_talk_user_chat import (
    ChannelTalkUserChatAssignmentMetadata,
)
from catchup.sync.ingestion.vector_records.channel_talk_user_chat import (
    ChannelTalkUserChatCustomerMetadata,
)
from catchup.sync.ingestion.vector_records.channel_talk_user_chat import (
    ChannelTalkUserChatData,
)
from catchup.sync.ingestion.vector_records.channel_talk_user_chat import (
    ChannelTalkUserChatDataPart,
)
from catchup.sync.ingestion.vector_records.channel_talk_user_chat import (
    ChannelTalkUserChatMetadata,
)
from catchup.sync.ingestion.vector_records.channel_talk_user_chat import (
    ChannelTalkUserChatTagMetadata,
)
from catchup.sync.ingestion.vector_records.channel_talk_user_chat import (
    ChannelTalkUserChatVectorRecord,
)


class ChannelTalkUserChatV2RecordMapper:
    """Build v2 vector-store records from hydrated Channel Talk UserChat bundles."""

    def __init__(self, renderer: UserChatMessageRenderer | None = None) -> None:
        self._renderer = renderer or UserChatMessageRenderer()

    def to_document(
        self,
        bundle: ChannelTalkFetchedUserChat,
        *,
        channel_id: str,
        content: str,
        managers_by_id: dict[str, ChannelTalkManagerMetadata] | None = None,
        document_id: str | None = None,
        synced_at: datetime | None = None,
    ) -> Document:
        return self.to_record(
            bundle,
            channel_id=channel_id,
            content=content,
            embedding=[],
            managers_by_id=managers_by_id,
            document_id=document_id,
            synced_at=synced_at,
        ).to_document()

    def to_record(
        self,
        bundle: ChannelTalkFetchedUserChat,
        *,
        channel_id: str,
        content: str,
        embedding: list[float],
        managers_by_id: dict[str, ChannelTalkManagerMetadata] | None = None,
        document_id: str | None = None,
        synced_at: datetime | None = None,
    ) -> ChannelTalkUserChatVectorRecord:
        detail = bundle.detail
        managers_by_id = managers_by_id or {}
        synced_at = synced_at or datetime.now(timezone.utc)
        title = self._title(detail, bundle)
        parts = self._parts(bundle.messages, managers_by_id=managers_by_id)
        body = self._body_from_parts(parts)
        last_message_at = max(
            (
                timestamp
                for message in bundle.messages
                if (
                    timestamp := self._renderer.message_timestamp(message)
                )
                is not None
            ),
            default=None,
        )
        created_at = detail.timing.created_at or last_message_at or synced_at
        updated_at = (
            detail.timing.desk_updated_at
            or detail.timing.updated_at
            or last_message_at
            or created_at
        )
        target_name = _normalize_text(bundle.channel_name) or channel_id
        return ChannelTalkUserChatVectorRecord(
            langchain_id=document_id
            or build_user_chat_document_id(
                channel_id=channel_id,
                user_chat_id=detail.user_chat_id,
            ),
            content=content,
            embedding=embedding,
            source="channel_talk",
            entity_type="user_chat",
            record_id=detail.user_chat_id,
            scope_type="channel",
            scope_id=channel_id,
            target_type="channel",
            target_id=channel_id,
            target_name=target_name,
            internal_author_id=None,
            title=title,
            body=body,
            data=ChannelTalkUserChatData(parts=parts),
            url=build_user_chat_desk_url(
                channel_id=channel_id,
                user_chat_id=detail.user_chat_id,
            ),
            created_at=created_at,
            updated_at=updated_at,
            synced_at=synced_at,
            channel_talk_user_chat=ChannelTalkUserChatMetadata(
                state=detail.state.value,
                managed=detail.managed,
                priority=detail.priority,
                goal_state=detail.goal_state,
                customer=self._customer_metadata(detail.customer, bundle),
                assignment=ChannelTalkUserChatAssignmentMetadata(
                    manager_ids=list(detail.assignment.manager_ids),
                    assignee_id=detail.assignment.assignee_id,
                    first_assignee_id_after_open=(
                        detail.assignment.first_assignee_id_after_open
                    ),
                    manager_role_ids=self._renderer.resolve_manager_role_ids(
                        manager_ids=detail.assignment.manager_ids,
                        managers_by_id=managers_by_id,
                        fallback_managers=detail.assignment.managers,
                    ),
                ),
                tags=[
                    ChannelTalkUserChatTagMetadata(key=tag.key, name=tag.name)
                    for tag in detail.tags
                ],
            ),
        )

    def _parts(
        self,
        messages: tuple[ChannelTalkUserChatMessage, ...],
        *,
        managers_by_id: dict[str, ChannelTalkManagerMetadata],
    ) -> list[ChannelTalkUserChatDataPart]:
        parts: list[ChannelTalkUserChatDataPart] = []
        for message in messages:
            text = self._message_text(message)
            if not text:
                continue
            parts.append(
                ChannelTalkUserChatDataPart(
                    type=self._part_type(message),
                    text=text,
                    metadata=_drop_none(
                        {
                            "message_id": message.message_id,
                            "message_type": message.message_type,
                            "person_type": message.person_type,
                            "created_at": self._isoformat(message.created_at),
                            "updated_at": self._isoformat(message.updated_at),
                            "is_private": message.is_private,
                            "author": self._author_metadata(
                                message,
                                managers_by_id=managers_by_id,
                            ),
                            "attachments": self._attachments_metadata(message),
                            "buttons": self._buttons_metadata(message),
                            "form": self._form_metadata(message),
                            "web_page": self._web_page_metadata(message),
                            "log": self._log_metadata(message),
                        }
                    ),
                )
            )
        return parts

    @classmethod
    def _message_text(cls, message: ChannelTalkUserChatMessage) -> str | None:
        if message.log is not None:
            return _normalize_text(message.log.action or message.log.log_type)

        parts = [_normalize_text(message.plain_text)]
        if message.form is not None:
            form_text = UserChatMessageRenderer.render_form_message(message.form)
            if form_text and form_text not in parts:
                parts.append(_normalize_text(form_text))
        if message.attachments:
            attachment_text = UserChatMessageRenderer.render_attachments(
                message.attachments
            )
            parts.append(_normalize_text(attachment_text))
        if message.buttons:
            button_text = cls._render_buttons_without_urls(message)
            parts.append(_normalize_text(button_text))
        if message.web_page is not None:
            parts.append(
                _join_present(
                    [
                        message.web_page.title,
                        message.web_page.description,
                        message.web_page.site_name,
                    ],
                    " | ",
                )
            )
        if message.blocks:
            for block in message.blocks:
                block_text = _join_present(
                    [block.text, block.label, block.name, block.value, block.markdown],
                    " ",
                )
                if block_text and block_text not in parts:
                    parts.append(block_text)

        normalized = "\n".join(
            dict.fromkeys(part for part in parts if part and part.strip())
        ).strip()
        return normalized or None

    @staticmethod
    def _render_buttons_without_urls(message: ChannelTalkUserChatMessage) -> str:
        return " / ".join(
            _join_present([button.text, button.value, button.action], " ")
            for button in message.buttons
        )

    @staticmethod
    def _part_type(message: ChannelTalkUserChatMessage) -> str:
        if message.log is not None:
            return "system_event"
        if message.form is not None:
            return "form_message"
        if message.is_private is True:
            return "internal_note"
        if message.author is not None and message.author.is_bot:
            return "bot_message"
        return "message"

    @staticmethod
    def _body_from_parts(parts: list[ChannelTalkUserChatDataPart]) -> str:
        return "\n\n".join(
            part.text for part in parts if part.type != "system_event"
        )

    def _title(
        self,
        detail: ChannelTalkUserChatDetail,
        bundle: ChannelTalkFetchedUserChat,
    ) -> str:
        customer = detail.customer
        candidates = [
            detail.description,
            detail.name,
            customer.name if customer is not None else None,
            customer.email if customer is not None else None,
            customer.mobile_number if customer is not None else None,
            bundle.list_item.user_id,
            bundle.list_item.member_id,
            detail.user_chat_id,
        ]
        for candidate in candidates:
            if normalized := _normalize_text(candidate):
                return normalized
        return detail.user_chat_id

    @staticmethod
    def _customer_metadata(
        customer: ChannelTalkUserFoundation | None,
        bundle: ChannelTalkFetchedUserChat,
    ) -> ChannelTalkUserChatCustomerMetadata | None:
        if customer is None and not (bundle.list_item.user_id or bundle.list_item.member_id):
            return None
        return ChannelTalkUserChatCustomerMetadata(
            user_id=(
                customer.external_user_id
                if customer is not None
                else bundle.list_item.user_id
            ),
            member_id=(
                customer.member_id if customer is not None else bundle.list_item.member_id
            ),
            veil_id=customer.veil_id if customer is not None else None,
            unified_id=customer.unified_id if customer is not None else None,
            type=customer.user_type if customer is not None else None,
            name=customer.name if customer is not None else None,
            email=customer.email if customer is not None else None,
            mobile_number=customer.mobile_number if customer is not None else None,
            avatar_url=customer.avatar_url if customer is not None else None,
            language=customer.language if customer is not None else None,
            country=customer.country if customer is not None else None,
            city=customer.city if customer is not None else None,
        )

    @staticmethod
    def _author_metadata(
        message: ChannelTalkUserChatMessage,
        *,
        managers_by_id: dict[str, ChannelTalkManagerMetadata],
    ) -> dict[str, Any] | None:
        author = message.author
        if author is None:
            return None
        manager = managers_by_id.get(author.manager_id) if author.manager_id else None
        return _drop_none(
            {
                "author_type": author.author_type,
                "external_user_id": (
                    author.manager_id
                    or author.user_id
                    or author.member_id
                    or author.bot_id
                ),
                "role_id": author.role_id or (manager.role_id if manager else None),
                "is_bot": author.is_bot,
            }
        )

    @staticmethod
    def _attachments_metadata(
        message: ChannelTalkUserChatMessage,
    ) -> list[dict[str, Any]]:
        return [
            _drop_none(
                {
                    "file_key": attachment.file_key,
                    "name": attachment.name,
                    "content_type": attachment.content_type,
                    "size": attachment.size,
                }
            )
            for attachment in message.attachments
        ]

    @staticmethod
    def _buttons_metadata(message: ChannelTalkUserChatMessage) -> list[dict[str, Any]]:
        return [
            _drop_none(
                {
                    "text": button.text,
                    "action": button.action,
                    "value": button.value,
                    "url": button.url,
                }
            )
            for button in message.buttons
        ]

    @staticmethod
    def _form_metadata(message: ChannelTalkUserChatMessage) -> dict[str, Any] | None:
        if message.form is None:
            return None
        return _drop_none(
            {
                "form_type": message.form.form_type,
                "submitted_at": ChannelTalkUserChatV2RecordMapper._isoformat(
                    message.form.submitted_at
                ),
                "inputs": [
                    _drop_none(
                        {
                            "label": item.label,
                            "input_type": item.input_type,
                            "data_type": item.data_type,
                            "binding_key": item.binding_key,
                            "value": item.value,
                        }
                    )
                    for item in message.form.inputs
                ],
            }
        )

    @staticmethod
    def _web_page_metadata(
        message: ChannelTalkUserChatMessage,
    ) -> dict[str, Any] | None:
        if message.web_page is None:
            return None
        return _drop_none(
            {
                "url": message.web_page.url,
                "title": message.web_page.title,
                "description": message.web_page.description,
                "site_name": message.web_page.site_name,
                "publisher": message.web_page.publisher,
                "author": message.web_page.author,
            }
        )

    @staticmethod
    def _log_metadata(message: ChannelTalkUserChatMessage) -> dict[str, Any] | None:
        if message.log is None:
            return None
        return _drop_none(
            {
                "action": message.log.action,
                "log_type": message.log.log_type,
                "actor_name": message.log.actor_name,
            }
        )

    @staticmethod
    def _isoformat(value: datetime | None) -> str | None:
        return value.isoformat() if value else None


def _normalize_text(value: str | None) -> str | None:
    normalized = str(value or "").strip()
    return normalized or None


def _join_present(parts: list[str | None], separator: str) -> str | None:
    joined = separator.join(part.strip() for part in parts if part and part.strip())
    return joined or None


def _drop_none(value: dict[str, Any]) -> dict[str, Any]:
    return {key: item for key, item in value.items() if item is not None}
