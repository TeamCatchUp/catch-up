from __future__ import annotations

from datetime import datetime

from catchup.connectors.channel_talk.schemas.channel_metadata import (
    ChannelTalkManagerMetadata,
)
from catchup.connectors.channel_talk.schemas.user_chat import ChannelTalkUserChatDetail
from catchup.connectors.channel_talk.schemas.user_chat import (
    ChannelTalkUserChatManagerRef,
)
from catchup.connectors.channel_talk.schemas.user_chat_message import (
    ChannelTalkUserChatMessage,
)
from catchup.connectors.channel_talk.schemas.user_chat_message import (
    ChannelTalkUserChatMessageAttachment,
)
from catchup.connectors.channel_talk.schemas.user_chat_message import (
    ChannelTalkUserChatMessageButton,
)
from catchup.connectors.channel_talk.schemas.user_chat_message import (
    ChannelTalkUserChatMessageForm,
)
from catchup.connectors.channel_talk.schemas.user_chat_message import (
    ChannelTalkUserChatMessageLog,
)
from catchup.connectors.channel_talk.schemas.user_chat_message import (
    ChannelTalkUserChatMessageWebPage,
)


def _join_present(parts: list[str | None], separator: str) -> str:
    return separator.join(part for part in parts if part)


class UserChatMessageRenderer:
    def partition_messages(
        self,
        messages: tuple[ChannelTalkUserChatMessage, ...],
    ) -> tuple[tuple[ChannelTalkUserChatMessage, ...], int]:
        included: list[ChannelTalkUserChatMessage] = []
        excluded_count = 0
        for message in messages:
            if self.should_include_message(message):
                included.append(message)
                continue
            excluded_count += 1
        return tuple(included), excluded_count

    @staticmethod
    def should_include_message(message: ChannelTalkUserChatMessage) -> bool:
        return bool(
            str(message.plain_text or "").strip()
            or message.form is not None
            or message.log is not None
            or message.attachments
            or message.buttons
            or message.web_page is not None
        )

    @staticmethod
    def message_timestamp(message: ChannelTalkUserChatMessage) -> datetime | None:
        return message.created_at or message.updated_at

    def build_contextual_content(
        self,
        *,
        detail: ChannelTalkUserChatDetail,
        included_messages: tuple[ChannelTalkUserChatMessage, ...],
        managers_by_id: dict[str, ChannelTalkManagerMetadata],
    ) -> str:
        customer = detail.customer
        title = detail.description or detail.name
        lines: list[str] = []
        if title:
            lines.append(str(title).strip())
        if customer is not None:
            customer_parts = [
                customer.name,
                customer.email,
                customer.mobile_number,
            ]
            customer_label = " / ".join(
                dict.fromkeys(
                    item.strip() for item in customer_parts if item and item.strip()
                )
            )
            if customer_label:
                lines.append(f"User: {customer_label}")
        assignee_name = self.resolve_assignee_name(
            detail=detail,
            managers_by_id=managers_by_id,
        )
        if assignee_name:
            lines.append(f"Assignee: {assignee_name}")
        manager_names = self.resolve_manager_names(
            manager_ids=detail.assignment.manager_ids,
            managers_by_id=managers_by_id,
            fallback_managers=detail.assignment.managers,
        )
        if manager_names:
            lines.append(f"Managers: {', '.join(manager_names)}")
        if detail.tags:
            tags = ", ".join(
                tag.name or tag.key or ""
                for tag in detail.tags
                if (tag.name or tag.key)
            )
            if tags:
                lines.append(f"Tags: {tags}")
        lines.append("")
        lines.append("Conversation:")
        if included_messages:
            lines.extend(
                self.format_message_line(
                    message,
                    managers_by_id=managers_by_id,
                )
                for message in included_messages
            )
        else:
            lines.append("(포함된 메시지 없음)")
        return "\n".join(lines)

    @classmethod
    def format_message_line(
        cls,
        message: ChannelTalkUserChatMessage,
        *,
        managers_by_id: dict[str, ChannelTalkManagerMetadata],
    ) -> str:
        if message.log is not None:
            return f"[시스템] System: {cls.render_log_message(message.log)}"
        author_label = cls.resolve_message_author_label(
            message=message,
            managers_by_id=managers_by_id,
        )
        content = cls.render_message_content(message)
        prefix = cls.message_prefix(message)
        if prefix:
            return f"{prefix} {author_label}: {content}"
        return f"{author_label}: {content}"

    @classmethod
    def resolve_message_author_label(
        cls,
        *,
        message: ChannelTalkUserChatMessage,
        managers_by_id: dict[str, ChannelTalkManagerMetadata],
    ) -> str:
        author = message.author
        if author is None:
            return message.person_type or "Unknown"
        if author.user_id is not None:
            return "Customer"
        if author.manager_id is not None:
            return (
                cls.manager_display_name(
                    manager_id=author.manager_id,
                    managers_by_id=managers_by_id,
                )
                or author.name
                or "Manager"
            )
        return author.name or author.bot_name or author.author_type or "Unknown"

    @classmethod
    def message_prefix(cls, message: ChannelTalkUserChatMessage) -> str | None:
        if message.log is not None:
            return "[시스템]"
        if message.form is not None:
            return "[입력폼]"
        if message.attachments:
            return "[파일]"
        if message.buttons:
            return "[버튼]"
        if message.is_private is True:
            return "[내부대화]"
        return None

    @classmethod
    def render_message_content(cls, message: ChannelTalkUserChatMessage) -> str:
        if message.log is not None:
            return cls.render_log_message(message.log)
        content_parts: list[str] = []
        plain_text = str(message.plain_text or "").strip()
        form_text = (
            cls.render_form_message(message.form) if message.form is not None else ""
        )
        if message.form is not None:
            if plain_text and form_text:
                content_parts.append(plain_text)
                if not cls.content_contains_form_text(
                    content=plain_text,
                    form_text=form_text,
                ):
                    content_parts.append(form_text)
            else:
                content_parts.append(plain_text or form_text)
        elif plain_text:
            content_parts.append(plain_text)
        if message.attachments:
            content_parts.append(cls.render_attachments(message.attachments))
        if message.buttons:
            content_parts.append(cls.render_buttons(message.buttons))
        if message.web_page is not None:
            web_page_text = cls.render_web_page(message.web_page)
            if web_page_text and not cls.content_contains_web_page(
                content_parts=content_parts,
                web_page=message.web_page,
            ):
                content_parts.append(web_page_text)
        return " | ".join(item for item in content_parts if item) or "(내용 없음)"

    @staticmethod
    def content_contains_form_text(
        *,
        content: str,
        form_text: str,
    ) -> bool:
        form_parts = [
            part.strip()
            for part in form_text.replace(" / ", "\n").splitlines()
            if part.strip()
        ]
        return bool(form_parts) and all(part in content for part in form_parts)

    @staticmethod
    def render_form_message(message_form: ChannelTalkUserChatMessageForm) -> str:
        parts = [
            f"{item.label}: {item.value}"
            if item.label and item.value
            else item.value or item.label
            for item in message_form.inputs
        ]
        return _join_present(parts, " / ") or (message_form.form_type or "")

    @staticmethod
    def render_attachments(
        attachments: list[ChannelTalkUserChatMessageAttachment],
    ) -> str:
        return " / ".join(
            _join_present(
                [
                    attachment.name or attachment.file_key,
                    f"({attachment.content_type})" if attachment.content_type else None,
                ],
                " ",
            )
            for attachment in attachments
        )

    @staticmethod
    def render_buttons(
        buttons: list[ChannelTalkUserChatMessageButton],
    ) -> str:
        return "버튼: " + " / ".join(
            _join_present(
                [
                    button.text or button.value or button.action,
                    f"({button.url})" if button.url else None,
                ],
                " ",
            )
            for button in buttons
        )

    @staticmethod
    def render_web_page(web_page: ChannelTalkUserChatMessageWebPage) -> str:
        return _join_present(
            [
                web_page.title,
                web_page.url,
                web_page.description,
            ],
            " | ",
        )

    @staticmethod
    def content_contains_web_page(
        *,
        content_parts: list[str],
        web_page: ChannelTalkUserChatMessageWebPage,
    ) -> bool:
        content = "\n".join(content_parts)
        expected_parts = [
            web_page.title,
            web_page.url,
            web_page.description,
        ]
        return all(part in content for part in expected_parts if part)

    @staticmethod
    def render_log_message(message_log: ChannelTalkUserChatMessageLog) -> str:
        return message_log.action or message_log.log_type or "system event"

    @classmethod
    def resolve_assignee_name(
        cls,
        *,
        detail: ChannelTalkUserChatDetail,
        managers_by_id: dict[str, ChannelTalkManagerMetadata],
    ) -> str | None:
        if detail.assignment.assignee_name:
            return detail.assignment.assignee_name
        assignee_id = detail.assignment.assignee_id
        if assignee_id is None:
            return None
        return cls.manager_display_name(
            manager_id=assignee_id,
            managers_by_id=managers_by_id,
        )

    @classmethod
    def resolve_manager_names(
        cls,
        *,
        manager_ids: tuple[str, ...],
        managers_by_id: dict[str, ChannelTalkManagerMetadata],
        fallback_managers: list[ChannelTalkUserChatManagerRef],
    ) -> list[str]:
        fallback_names = {
            manager.manager_id: manager.name
            for manager in fallback_managers
            if manager.name is not None
        }
        names: list[str] = []
        for manager_id in manager_ids:
            name = cls.manager_display_name(
                manager_id=manager_id,
                managers_by_id=managers_by_id,
            ) or fallback_names.get(manager_id)
            if name:
                names.append(name)
        return list(dict.fromkeys(names))

    @staticmethod
    def resolve_manager_role_ids(
        *,
        manager_ids: tuple[str, ...],
        managers_by_id: dict[str, ChannelTalkManagerMetadata],
        fallback_managers: list[ChannelTalkUserChatManagerRef],
    ) -> list[str]:
        fallback_role_ids = {
            manager.manager_id: manager.role_id
            for manager in fallback_managers
            if manager.role_id is not None
        }
        role_ids: list[str] = []
        for manager_id in manager_ids:
            manager = managers_by_id.get(manager_id)
            role_id = (manager.role_id if manager is not None else None) or (
                fallback_role_ids.get(manager_id)
            )
            if role_id:
                role_ids.append(role_id)
        return list(dict.fromkeys(role_ids))

    @staticmethod
    def manager_display_name(
        *,
        manager_id: str,
        managers_by_id: dict[str, ChannelTalkManagerMetadata],
    ) -> str | None:
        manager = managers_by_id.get(manager_id)
        if manager is None:
            return None
        return manager.name or manager.email
