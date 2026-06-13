from __future__ import annotations

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
        parts = self._parts(message)
        body = "\n\n".join(part.text for part in parts)
        channel_name = message.channel_name or message.channel_id
        author_id = message.user_id or message.bot_id
        author_name = (
            message.user_real_name or message.user_name or message.bot_name or author_id
        )

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
            title=self._title(message, channel_name, body),
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
                channel_name=channel_name,
                ts=message.ts,
                thread_ts=message.thread_ts,
                is_thread_root=message.thread_ts == message.ts
                and message.reply_count > 0,
                message_type=message.message_type,
                subtype=message.subtype,
                author=SlackMessageAuthorMetadata(
                    slack_user_id=message.user_id,
                    slack_bot_id=message.bot_id,
                    name=author_name,
                    catchup_user_id=internal_author_id,
                )
                if author_id or author_name or internal_author_id
                else None,
                reply_count=message.reply_count,
                reactions=[
                    SlackMessageReactionMetadata(
                        name=reaction.name,
                        count=reaction.count,
                    )
                    for reaction in message.reactions
                    if reaction.name
                ],
                edited_at=message.edited_ts,
                latest_reply_ts=message.latest_reply_ts,
            ),
        )

    @classmethod
    def _parts(cls, message: SlackMessage) -> list[SlackMessageDataPart]:
        part_inputs: list[tuple[str, str | None, dict[str, Any]]] = [
            (
                "message_body",
                message.text,
                _drop_none(
                    {
                        "message_type": message.message_type,
                        "subtype": message.subtype,
                    }
                ),
            ),
        ]
        part_inputs.extend(
            ("thread_reply", reply.text, cls._reply_metadata(reply))
            for reply in message.replies
        )
        part_inputs.extend(
            (
                "attachment",
                cls._attachment_text(attachment),
                cls._attachment_metadata(attachment),
            )
            for attachment in message.attachments
        )
        part_inputs.extend(cls._file_part_inputs(message.files, parent_type="message"))
        for reply in message.replies:
            part_inputs.extend(
                cls._file_part_inputs(
                    reply.files,
                    parent_type="thread_reply",
                    reply_ts=reply.ts,
                )
            )
        return [
            part
            for part_type, text, metadata in part_inputs
            if (part := cls._build_part(part_type, text, metadata)) is not None
        ]

    @classmethod
    def _file_part_inputs(
        cls,
        files: list[SlackFileRef],
        *,
        parent_type: str,
        reply_ts: str | None = None,
    ) -> list[tuple[str, str | None, dict[str, Any]]]:
        return [
            (
                "file",
                cls._file_text(file),
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
    def _reply_metadata(reply: SlackThreadReply) -> dict[str, Any]:
        return _drop_none(
            {
                "ts": reply.ts,
                "user_id": reply.user_id,
                "user_name": reply.user_real_name or reply.user_name,
                "reaction_count": sum(reaction.count for reaction in reply.reactions),
                "file_count": len(reply.files),
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
    def _attachment_metadata(attachment: SlackAttachment) -> dict[str, Any]:
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
            }
        )

    @staticmethod
    def _file_text(file: SlackFileRef) -> str:
        return _join_unique_text(
            file.title,
            file.name,
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

    @staticmethod
    def _title(message: SlackMessage, channel_name: str, body: str) -> str:
        preview = " ".join(body.split())[:80]
        return preview or f"{channel_name} / {message.ts}"

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
