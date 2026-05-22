from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import ValidationInfo
from pydantic import field_validator

from catchup.connectors.channel_talk.schemas._parsing import _parse_metadata_page
from catchup.connectors.channel_talk.schemas._parsing import _PayloadReader
from catchup.connectors.channel_talk.schemas._parsing import _validation_field_name
from catchup.connectors.channel_talk.schemas.user_chat import FullSyncQuotaSnapshot
from catchup.connectors.channel_talk.schemas.user_chat import _parse_quota_snapshot
from catchup.utils.validation import require_text


class ChannelTalkUserChatMessageAuthor(BaseModel):
    model_config = ConfigDict(extra="ignore")

    author_type: str | None = None
    bot_id: str | None = None
    user_id: str | None = None
    member_id: str | None = None
    manager_id: str | None = None
    name: str | None = None
    email: str | None = None
    avatar_url: str | None = None
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
    description: str | None = None
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
    attachments: list[ChannelTalkUserChatMessageAttachment] = Field(
        default_factory=list
    )
    buttons: list[ChannelTalkUserChatMessageButton] = Field(default_factory=list)
    blocks: list[ChannelTalkUserChatMessageBlock] = Field(default_factory=list)
    log: ChannelTalkUserChatMessageLog | None = None
    form: ChannelTalkUserChatMessageForm | None = None
    web_page: ChannelTalkUserChatMessageWebPage | None = None
    raw_payload: dict[str, Any] | None = None

    @field_validator("message_id", "user_chat_id")
    @classmethod
    def validate_required_text(cls, value: str, info: ValidationInfo) -> str:
        return require_text(value, _validation_field_name(info))

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
        message_id = reader.text("id")
        if message_id is None:
            raise ValueError("user chat message payload missing message id")

        requested_user_chat_id = require_text(user_chat_id, "user_chat_id")
        if "userChatId" in payload:
            raise ValueError(
                "user chat message payload used unsupported userChatId key"
            )
        payload_user_chat_id = reader.text("chatId")
        if (
            payload_user_chat_id is not None
            and payload_user_chat_id != requested_user_chat_id
        ):
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
                value
                for value in root_reader.items("bots")
                if isinstance(value, Mapping)
            ]
        messages, next_cursor = _parse_metadata_page(
            payload,
            item_keys=("messages",),
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


def _parse_message_attachments(
    reader: "_PayloadReader",
) -> list[ChannelTalkUserChatMessageAttachment]:
    attachments: list[ChannelTalkUserChatMessageAttachment] = []
    for value in [*reader.items("attachments"), *reader.items("files")]:
        if not isinstance(value, Mapping):
            continue
        item_reader = _PayloadReader(value)
        attachments.append(
            ChannelTalkUserChatMessageAttachment(
                file_key=item_reader.text("key"),
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


def _parse_message_buttons(
    reader: "_PayloadReader",
) -> list[ChannelTalkUserChatMessageButton]:
    buttons: list[ChannelTalkUserChatMessageButton] = []
    for value in reader.items("buttons"):
        if not isinstance(value, Mapping):
            continue
        item_reader = _PayloadReader(value)
        buttons.append(
            ChannelTalkUserChatMessageButton(
                text=item_reader.text("text", "title", "label", "name"),
                action=item_reader.text("action", "type"),
                value=item_reader.text("value", "payload"),
                url=item_reader.text("url", "href"),
            )
        )
    return buttons


def _parse_message_blocks(
    reader: "_PayloadReader",
) -> list[ChannelTalkUserChatMessageBlock]:
    blocks: list[ChannelTalkUserChatMessageBlock] = []
    for value in reader.items("blocks"):
        if not isinstance(value, Mapping):
            continue
        item_reader = _PayloadReader(value)
        blocks.append(
            ChannelTalkUserChatMessageBlock(
                block_type=item_reader.text("type", "blockType", "block_type"),
                text=item_reader.text(
                    "text", "plainText", "plain_text", "label", "value"
                ),
                label=item_reader.text("label", "title"),
                name=item_reader.text("name"),
                value=item_reader.text("value"),
                raw_payload=dict(value),
            )
        )
    return blocks


def _parse_message_log(
    reader: "_PayloadReader",
) -> ChannelTalkUserChatMessageLog | None:
    log_reader = reader.nested("log")
    if log_reader is None:
        return None
    return ChannelTalkUserChatMessageLog(
        action=log_reader.text("action", "name", "type"),
        log_type=log_reader.text("type"),
        actor_name=log_reader.text("name", "actorName", "actor_name"),
        raw_payload=dict(log_reader.payload),
    )


def _parse_message_form(
    reader: "_PayloadReader",
) -> ChannelTalkUserChatMessageForm | None:
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


def _parse_message_web_page(
    reader: "_PayloadReader",
) -> ChannelTalkUserChatMessageWebPage | None:
    web_page_reader = reader.nested("webPage", "web_page")
    if web_page_reader is None:
        return None

    return ChannelTalkUserChatMessageWebPage(
        url=web_page_reader.text("url", "href"),
        title=web_page_reader.text("title", "name"),
        description=web_page_reader.text("description", "desc"),
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
    manager_sources = _reader_with_profile(manager_reader)
    user_sources = _reader_with_profile(user_reader)
    bot_sources = _reader_with_profile(bot_reader)
    person_id = reader.text("personId")
    bot_name = reader.text("botName") or (
        bot_reader and bot_reader.text("name", "botName")
    )
    bot_id = (
        person_id
        if (
            bot_reader is not None
            or reader.text("personType") == "bot"
            or bot_name is not None
        )
        else None
    )

    author_type = reader.text("personType")
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

    user_id = user_reader and user_reader.text("id")
    if user_id is None and author_type in {"user", "customer"}:
        user_id = person_id

    manager_id = manager_reader and manager_reader.text("id")
    if manager_id is None and author_type == "manager":
        manager_id = person_id

    return ChannelTalkUserChatMessageAuthor(
        author_type=author_type,
        bot_id=bot_id,
        user_id=user_id,
        member_id=(user_reader and user_reader.text("memberId")),
        manager_id=manager_id,
        name=_first_reader_text(
            [*manager_sources, *user_sources, *bot_sources, reader],
            "name",
            "displayName",
        )
        or _first_reader_text(bot_sources, "botName")
        or bot_name
        or reader.text("botName"),
        email=_first_reader_text(
            [*manager_sources, *user_sources, *bot_sources, reader],
            "email",
        ),
        avatar_url=_first_reader_text(
            [*manager_sources, *user_sources, *bot_sources, reader],
            "avatarUrl",
            "avatarURL",
            "avatar_url",
        ),
        role_id=(manager_reader and manager_reader.text("roleId")),
        bot_name=bot_name,
        is_bot=bool(bot_name or bot_id) or (author_type == "bot"),
    )


def _reader_with_profile(reader: "_PayloadReader" | None) -> tuple["_PayloadReader", ...]:
    if reader is None:
        return ()
    profile_reader = reader.nested("profile")
    if profile_reader is None:
        return (reader,)
    return (reader, profile_reader)


def _first_reader_text(
    readers: list["_PayloadReader"] | tuple["_PayloadReader", ...],
    *keys: str,
) -> str | None:
    for reader in readers:
        value = reader.text(*keys)
        if value is not None:
            return value
    return None


def _read_message_bot(
    reader: "_PayloadReader",
    *,
    root_bots: list[Mapping[str, Any]] | None = None,
) -> _PayloadReader | None:
    person_type = reader.text("personType")
    person_id = reader.text("personId")

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
        if item_reader.text("id") == person_id:
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
            for value in [
                message_web_page.title,
                message_web_page.url,
                message_web_page.description,
            ]
            if value is not None
        )
        if web_page_text:
            return web_page_text

    blocks = blocks or _parse_message_blocks(reader)
    block_texts = [block.text for block in blocks if block.text is not None]
    if block_texts:
        return "\n".join(block_texts)

    return None


def _build_form_plain_text(message_form: ChannelTalkUserChatMessageForm) -> str | None:
    parts = [_format_form_input_text(item) for item in message_form.inputs]
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
