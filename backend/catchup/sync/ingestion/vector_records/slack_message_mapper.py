from __future__ import annotations

import html
import re
from datetime import datetime
from datetime import timezone
from typing import Any

from langchain_core.documents import Document

from catchup.connectors.slack.schemas import SlackAttachment
from catchup.connectors.slack.schemas import SlackFileRef
from catchup.connectors.slack.schemas import SlackMessage
from catchup.connectors.slack.schemas import SlackThreadReply
from catchup.sync.ingestion.vector_records.slack_message import (
    SlackMessageAuthorMetadata,
)
from catchup.sync.ingestion.vector_records.slack_message import SlackMessageData
from catchup.sync.ingestion.vector_records.slack_message import SlackMessageDataPart
from catchup.sync.ingestion.vector_records.slack_message import SlackMessageMetadata
from catchup.sync.ingestion.vector_records.slack_message import (
    SlackMessageReactionMetadata,
)
from catchup.sync.ingestion.vector_records.slack_message import SlackMessageVectorRecord


class SlackMessageV2RecordMapper:
    """Build v2 vector-store records from parsed Slack message data."""

    def to_document(
        self,
        message: SlackMessage,
        *,
        team_id: str,
        content: str,
        internal_author_id: str | None = None,
        synced_at: datetime | None = None,
    ) -> Document:
        return self.to_record(
            message,
            team_id=team_id,
            content=content,
            embedding=[],
            internal_author_id=internal_author_id,
            synced_at=synced_at,
        ).to_document()

    def to_record(
        self,
        message: SlackMessage,
        *,
        team_id: str,
        content: str,
        embedding: list[float],
        internal_author_id: str | None = None,
        synced_at: datetime | None = None,
    ) -> SlackMessageVectorRecord:
        synced_at = synced_at or datetime.now(timezone.utc)
        mention_names_by_id = self._mention_names_by_id(message)
        parts = self._parts(
            message,
            mention_names_by_id,
            internal_author_id=internal_author_id,
        )
        channel_name = (
            _normalize_display_text(message.channel_name) or message.channel_id
        )
        author_id = message.user_id or message.bot_id
        author_name = (
            message.user_real_name or message.user_name or message.bot_name or author_id
        )
        title = self._title(message, channel_name, mention_names_by_id)
        body = self._body_from_parts(parts)

        return SlackMessageVectorRecord(
            langchain_id=(f"slack:message:{team_id}:{message.channel_id}:{message.ts}"),
            content=content,
            embedding=embedding,
            source="slack",
            entity_type="message",
            record_id=message.ts,
            scope_type="workspace",
            scope_id=team_id,
            target_type="channel",
            target_id=message.channel_id,
            target_name=channel_name,
            internal_author_id=internal_author_id,
            title=title,
            body=body,
            data=SlackMessageData(parts=parts),
            url=message.url
            or f"slack://message/{team_id}/{message.channel_id}/{message.ts}",
            created_at=message.created_at,
            updated_at=self._updated_at(message),
            synced_at=synced_at,
            slack_message=SlackMessageMetadata(
                team_id=team_id,
                channel_id=message.channel_id,
                ts=message.ts,
                message_type=message.message_type,
                subtype=message.subtype,
                author=SlackMessageAuthorMetadata(
                    slack_user_id=message.user_id,
                    slack_bot_id=message.bot_id,
                    name=_normalize_display_text(author_name),
                    catchup_user_id=internal_author_id,
                )
                if author_id or author_name or internal_author_id
                else None,
                reactions=[
                    SlackMessageReactionMetadata(
                        name=reaction.name,
                        count=reaction.count,
                    )
                    for reaction in message.reactions
                    if reaction.name
                ],
                edited_at=message.edited_ts,
            ),
        )

    @classmethod
    def _parts(
        cls,
        message: SlackMessage,
        mention_names_by_id: dict[str, str],
        *,
        internal_author_id: str | None = None,
    ) -> list[SlackMessageDataPart]:
        message_text = cls._message_part_text(message, mention_names_by_id)
        part_inputs: list[tuple[str, str | None, dict[str, Any]]] = [
            (
                "message_body",
                message_text,
                cls._message_metadata(message, internal_author_id),
            ),
        ]
        part_inputs.extend(
            (
                "thread_reply",
                cls._reply_part_text(reply, mention_names_by_id),
                cls._reply_metadata(reply),
            )
            for reply in message.replies
        )
        for attachment in message.attachments:
            attachment_text = _resolve_slack_text(
                cls._attachment_text(attachment), mention_names_by_id
            )
            part_inputs.append(
                (
                    "attachment",
                    attachment_text,
                    cls._attachment_metadata(attachment, parent_type="message"),
                )
            )
            part_inputs.extend(
                cls._block_part_inputs(
                    attachment.blocks,
                    parent_type="attachment",
                    mention_names_by_id=mention_names_by_id,
                    attachment_id=str(attachment.id)
                    if attachment.id is not None
                    else None,
                    skip_texts=(attachment_text,),
                )
            )
        part_inputs.extend(
            cls._file_part_inputs(
                message.files,
                parent_type="message",
                mention_names_by_id=mention_names_by_id,
            )
        )
        for reply in message.replies:
            for attachment in reply.attachments:
                attachment_text = _resolve_slack_text(
                    cls._attachment_text(attachment), mention_names_by_id
                )
                part_inputs.append(
                    (
                        "attachment",
                        attachment_text,
                        cls._attachment_metadata(
                            attachment,
                            parent_type="thread_reply",
                            reply_ts=reply.ts,
                        ),
                    )
                )
                part_inputs.extend(
                    cls._block_part_inputs(
                        attachment.blocks,
                        parent_type="thread_reply_attachment",
                        mention_names_by_id=mention_names_by_id,
                        reply_ts=reply.ts,
                        attachment_id=(
                            str(attachment.id) if attachment.id is not None else None
                        ),
                        skip_texts=(attachment_text,),
                    )
                )
            part_inputs.extend(
                cls._file_part_inputs(
                    reply.files,
                    parent_type="thread_reply",
                    reply_ts=reply.ts,
                    mention_names_by_id=mention_names_by_id,
                )
            )
        return [
            part
            for part_type, text, metadata in part_inputs
            if (part := cls._build_part(part_type, text, metadata)) is not None
        ]

    @classmethod
    def _message_part_text(
        cls,
        message: SlackMessage,
        mention_names_by_id: dict[str, str],
    ) -> str:
        return cls._text_with_block_fallback(
            cls._message_text(message),
            message.blocks,
            mention_names_by_id,
        )

    @classmethod
    def _reply_part_text(
        cls,
        reply: SlackThreadReply,
        mention_names_by_id: dict[str, str],
    ) -> str:
        return cls._text_with_block_fallback(
            cls._reply_text(reply),
            reply.blocks,
            mention_names_by_id,
        )

    @classmethod
    def _text_with_block_fallback(
        cls,
        text: str | None,
        blocks: list[dict[str, Any]],
        mention_names_by_id: dict[str, str],
    ) -> str:
        parts = [_resolve_slack_text(text, mention_names_by_id)]
        parts.extend(
            _resolve_slack_text(cls._block_text(block), mention_names_by_id)
            for block in blocks
            if isinstance(block, dict)
        )
        return _join_unique_text(*parts)

    @classmethod
    def _file_part_inputs(
        cls,
        files: list[SlackFileRef],
        *,
        parent_type: str,
        mention_names_by_id: dict[str, str],
        reply_ts: str | None = None,
    ) -> list[tuple[str, str | None, dict[str, Any]]]:
        return [
            (
                "file",
                _resolve_slack_text(cls._file_text(file), mention_names_by_id),
                cls._file_metadata(
                    file,
                    parent_type=parent_type,
                    reply_ts=reply_ts,
                ),
            )
            for file in files
        ]

    @staticmethod
    def _build_part(
        part_type: str,
        text: str | None,
        metadata: dict[str, Any],
    ) -> SlackMessageDataPart | None:
        normalized = (text or "").strip()
        if not normalized:
            return None
        return SlackMessageDataPart(
            type=part_type,
            text=normalized,
            metadata=_drop_none(metadata),
        )

    @staticmethod
    def _message_metadata(
        message: SlackMessage,
        internal_author_id: str | None,
    ) -> dict[str, Any]:
        return _drop_none(
            {
                "ts": message.ts,
                "message_type": message.message_type,
                "subtype": message.subtype,
                "author": _author_metadata(
                    slack_user_id=message.user_id,
                    slack_bot_id=message.bot_id,
                    name=(
                        message.user_real_name
                        or message.user_name
                        or message.bot_name
                        or message.user_id
                        or message.bot_id
                    ),
                    catchup_user_id=internal_author_id,
                ),
                "created_at": message.created_at.isoformat(),
                "updated_at": SlackMessageV2RecordMapper._updated_at(
                    message
                ).isoformat(),
                "edited_at": message.edited_ts,
                "reaction_count": sum(
                    reaction.count for reaction in message.reactions
                ),
                "file_count": len(message.files),
                "attachment_count": len(message.attachments),
            }
        )

    @staticmethod
    def _reply_metadata(reply: SlackThreadReply) -> dict[str, Any]:
        return _drop_none(
            {
                "ts": reply.ts,
                "author": _author_metadata(
                    slack_user_id=reply.user_id,
                    name=reply.user_real_name or reply.user_name or reply.user_id,
                ),
                "created_at": _ts_to_isoformat(reply.ts),
                "reaction_count": sum(reaction.count for reaction in reply.reactions),
                "file_count": len(reply.files),
                "attachment_count": len(reply.attachments),
            }
        )

    @staticmethod
    def _attachment_text(attachment: SlackAttachment) -> str:
        parts: list[str | None] = [
            attachment.pretext,
            attachment.title,
            attachment.text,
            attachment.fallback,
        ]
        for field in attachment.fields:
            title = field.get("title")
            value = field.get("value")
            if title and value:
                parts.append(f"{title}: {value}")
            else:
                parts.append(title or value)
        return _join_unique_text(*parts)

    @staticmethod
    def _attachment_metadata(
        attachment: SlackAttachment,
        *,
        parent_type: str,
        reply_ts: str | None = None,
    ) -> dict[str, Any]:
        return _drop_none(
            {
                "id": attachment.id,
                "title_link": attachment.title_link,
                "author_name": attachment.author_name,
                "author_link": attachment.author_link,
                "service_name": attachment.service_name,
                "from_url": attachment.from_url,
                "footer": attachment.footer,
                "color": attachment.color,
                "image_url": attachment.image_url,
                "thumb_url": attachment.thumb_url,
                "app_id": attachment.app_id,
                "app_unfurl_url": attachment.app_unfurl_url,
                "actions": attachment.actions or None,
                "parent_type": parent_type,
                "reply_ts": reply_ts,
            }
        )

    @staticmethod
    def _file_text(file: SlackFileRef) -> str:
        return _join_unique_text(
            file.title,
            file.name,
            file.preview_plain_text,
            file.plain_text,
            file.preview,
            file.initial_comment,
        )

    @staticmethod
    def _file_metadata(
        file: SlackFileRef,
        *,
        parent_type: str,
        reply_ts: str | None = None,
    ) -> dict[str, Any]:
        return _drop_none(
            {
                "id": file.id,
                "filetype": file.filetype,
                "mimetype": file.mimetype,
                "pretty_type": file.pretty_type,
                "size": file.size,
                "mode": file.mode,
                "is_external": file.is_external,
                "external_type": file.external_type,
                "file_access": file.file_access,
                "permalink": file.permalink,
                "permalink_public": file.permalink_public,
                "url_private": file.url_private,
                "url_private_download": file.url_private_download,
                "parent_type": parent_type,
                "reply_ts": reply_ts,
            }
        )

    @classmethod
    def _block_part_inputs(
        cls,
        blocks: list[dict[str, Any]],
        *,
        parent_type: str,
        mention_names_by_id: dict[str, str],
        reply_ts: str | None = None,
        attachment_id: str | None = None,
        skip_texts: tuple[str | None, ...] = (),
    ) -> list[tuple[str, str | None, dict[str, Any]]]:
        skip_keys = {_dedupe_key(value) for value in skip_texts if value}
        return [
            (
                "block_text",
                text,
                _drop_none(
                    {
                        "block_type": block.get("type"),
                        "block_id": block.get("block_id"),
                        "parent_type": parent_type,
                        "reply_ts": reply_ts,
                        "attachment_id": attachment_id,
                    }
                ),
            )
            for block in blocks
            if isinstance(block, dict)
            if (
                text := _resolve_slack_text(
                    cls._block_text(block), mention_names_by_id
                )
            )
            and _dedupe_key(text) not in skip_keys
        ]

    @classmethod
    def _block_text(cls, block: dict[str, Any]) -> str:
        block_type = block.get("type")
        if block_type == "divider":
            return ""
        if block_type == "rich_text":
            return cls._rich_text_elements(block.get("elements", []))

        parts: list[str | None] = []
        for key in ("text", "label", "hint"):
            parts.append(cls._text_object(block.get(key)))
        for field in block.get("fields", []) or []:
            parts.append(cls._text_object(field))
        for element in block.get("elements", []) or []:
            if isinstance(element, dict):
                parts.append(cls._block_element_text(element))
        if block_type == "input":
            parts.append(cls._input_element_text(block.get("element")))
        return _join_unique_text(*parts)

    @classmethod
    def _block_element_text(cls, element: dict[str, Any]) -> str:
        direct_text = cls._text_object(element)
        if direct_text:
            return direct_text
        element_type = element.get("type")
        if element_type in {"button", "overflow"}:
            return _join_unique_text(
                cls._text_object(element.get("text")),
                *(
                    cls._text_object(option.get("text"))
                    for option in element.get("options", []) or []
                    if isinstance(option, dict)
                ),
            )
        if isinstance(element.get("elements"), list):
            return cls._rich_text_elements(element["elements"])
        return ""

    @staticmethod
    def _text_object(value: Any) -> str:
        if isinstance(value, str):
            return value
        if isinstance(value, dict):
            text = value.get("text")
            return text if isinstance(text, str) else ""
        return ""

    @classmethod
    def _input_element_text(cls, element: Any) -> str:
        if not isinstance(element, dict):
            return ""
        parts: list[str | None] = []
        for key in ("initial_value", "initial_date", "initial_time"):
            value = element.get(key)
            if isinstance(value, str):
                parts.append(value)
        if isinstance(element.get("initial_option"), dict):
            parts.append(cls._text_object(element["initial_option"].get("text")))
        for option in element.get("initial_options", []) or []:
            if isinstance(option, dict):
                parts.append(cls._text_object(option.get("text")))
        return _join_unique_text(*parts)

    @classmethod
    def _rich_text_elements(cls, elements: Any) -> str:
        if not isinstance(elements, list):
            return ""
        return "".join(cls._rich_text_element(element) for element in elements).strip()

    @classmethod
    def _rich_text_element(cls, element: Any) -> str:
        if not isinstance(element, dict):
            return ""
        element_type = element.get("type")
        if element_type == "text":
            return element.get("text", "")
        if element_type == "link":
            url = element.get("url", "")
            text = element.get("text")
            return f"<{url}|{text}>" if text else url
        if element_type == "user":
            user_id = element.get("user_id") or element.get("user")
            return f"<@{user_id}>" if user_id else ""
        if element_type == "channel":
            channel_id = element.get("channel_id") or element.get("channel")
            return f"<#{channel_id}>" if channel_id else ""
        if element_type == "usergroup":
            group_id = element.get("usergroup_id") or element.get("usergroup")
            return f"<!subteam^{group_id}>" if group_id else ""
        if element_type == "emoji":
            name = element.get("name")
            return f":{name}:" if name else ""
        if element_type == "date":
            timestamp = element.get("timestamp")
            fallback = element.get("fallback", "")
            if timestamp:
                return f"<!date^{timestamp}^{{date_short_pretty}}|{fallback}>"
            return fallback
        if element_type == "broadcast":
            range_name = element.get("range")
            return f"<!{range_name}>" if range_name else ""
        if element_type == "rich_text_list":
            return cls._rich_text_list(element)
        if isinstance(element.get("elements"), list):
            return cls._rich_text_elements(element["elements"])
        return cls._text_object(element)

    @classmethod
    def _rich_text_list(cls, element: dict[str, Any]) -> str:
        items: list[str] = []
        style = element.get("style")
        for index, item in enumerate(element.get("elements", []) or [], start=1):
            text = cls._rich_text_element(item).strip()
            if not text:
                continue
            prefix = f"{index}. " if style == "ordered" else "• "
            items.append(f"{prefix}{text}")
        return "\n".join(items)

    @staticmethod
    def _body_from_parts(parts: list[SlackMessageDataPart]) -> str:
        body_part_types = {"thread_reply", "attachment", "file", "block_text"}
        return "\n\n".join(part.text for part in parts if part.type in body_part_types)

    @classmethod
    def _title(
        cls,
        message: SlackMessage,
        channel_name: str,
        mention_names_by_id: dict[str, str],
    ) -> str:
        title = _resolve_slack_text(
            cls._message_text(message), mention_names_by_id
        ).strip()
        return title or f"{channel_name} / {message.ts}"

    @staticmethod
    def _message_text(message: SlackMessage) -> str:
        return message.raw_text if message.raw_text is not None else message.text

    @staticmethod
    def _reply_text(reply: SlackThreadReply) -> str:
        return reply.raw_text if reply.raw_text is not None else reply.text

    @staticmethod
    def _mention_names_by_id(message: SlackMessage) -> dict[str, str]:
        names_by_id: dict[str, str] = {}

        def add_user(
            user_id: str | None,
            *name_candidates: str | None,
        ) -> None:
            if not user_id:
                return
            display_name = _first_text(*name_candidates) or user_id
            if user_id in names_by_id and names_by_id[user_id] != user_id:
                return
            names_by_id[user_id] = display_name

        add_user(message.user_id, message.user_real_name, message.user_name)
        for user in message.mentioned_users:
            add_user(user.id, user.real_name, user.display_name, user.name)
        for reply in message.replies:
            add_user(reply.user_id, reply.user_real_name, reply.user_name)

        return names_by_id

    @classmethod
    def _updated_at(cls, message: SlackMessage) -> datetime:
        candidates = [
            message.created_at,
            cls._ts_to_datetime(message.edited_ts),
            cls._ts_to_datetime(message.latest_reply_ts),
        ]
        return max(candidate for candidate in candidates if candidate is not None)

    @staticmethod
    def _ts_to_datetime(value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        except (TypeError, ValueError, OSError):
            return None


def _drop_none(value: dict[str, Any]) -> dict[str, Any]:
    return {key: item for key, item in value.items() if item is not None}


def _join_unique_text(*values: str | None) -> str:
    parts: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not isinstance(value, str):
            continue
        text = value.strip()
        if not text:
            continue
        key = " ".join(text.split())
        if key in seen:
            continue
        seen.add(key)
        parts.append(text)
    return "\n".join(parts)


def _dedupe_key(value: str | None) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.strip().split())


def _author_metadata(
    *,
    slack_user_id: str | None = None,
    slack_bot_id: str | None = None,
    name: str | None = None,
    catchup_user_id: str | None = None,
) -> dict[str, Any] | None:
    metadata = _drop_none(
        {
            "slack_user_id": slack_user_id,
            "slack_bot_id": slack_bot_id,
            "name": _normalize_display_text(name),
            "catchup_user_id": catchup_user_id,
        }
    )
    return metadata or None


def _ts_to_isoformat(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return datetime.fromtimestamp(float(value), tz=timezone.utc).isoformat()
    except (TypeError, ValueError, OSError):
        return None


def _resolve_slack_text(value: str | None, mention_names_by_id: dict[str, str]) -> str:
    text = _normalize_display_text(value)
    if not text:
        return ""

    def replace_user_mention(match: re.Match) -> str:
        user_id = match.group(1)
        return f"@{mention_names_by_id.get(user_id, user_id)}"

    text = re.sub(r"<@([A-Z0-9]+)>", replace_user_mention, text)
    text = re.sub(r"<#[A-Z0-9]+\|([^>]+)>", r"#\1", text)
    text = re.sub(r"<#([A-Z0-9]+)>", r"#\1", text)
    text = re.sub(r"<!date\^\d+\^[^|>]*\|([^>]*)>", r"\1", text)
    text = re.sub(r"<!([^>|]+)(?:\|([^>]+))?>", _replace_special_mention, text)
    text = re.sub(r"<([^>|]+)\|([^>]+)>", r"\2", text)
    text = re.sub(r"<([^>]+)>", r"\1", text)
    return html.unescape(text)


def _replace_special_mention(match: re.Match) -> str:
    fallback = match.group(2)
    if fallback:
        return f"@{fallback}"
    return f"@{match.group(1)}"


def _normalize_display_text(value: str | None) -> str:
    if not isinstance(value, str):
        return ""
    text = html.unescape(value.strip())
    if "\\u" in text:
        try:
            text = text.encode("utf-8").decode("unicode_escape")
        except UnicodeDecodeError:
            pass
    return text


def _first_text(*values: str | None) -> str | None:
    for value in values:
        text = _normalize_display_text(value)
        if text:
            return text
    return None
