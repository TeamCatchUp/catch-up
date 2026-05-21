from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from datetime import timezone
from typing import Any

from sqlalchemy.orm import Session

from catchup.connectors.channel_talk.core.user_chat_full_sync_models import (
    ChannelTalkUserChatFullSyncConnection,
)
from catchup.connectors.channel_talk.core.user_chat_ids import build_user_chat_desk_url
from catchup.connectors.channel_talk.core.user_chat_message_renderer import (
    UserChatMessageRenderer,
)
from catchup.connectors.channel_talk.core.user_chat_original_fetcher import (
    ChannelTalkUserChatOriginalFetcher,
)
from catchup.connectors.channel_talk.schemas.user_chat import ChannelTalkUserChatDetail
from catchup.connectors.channel_talk.schemas.user_chat_message import (
    ChannelTalkUserChatMessage,
)
from catchup.db.channel_talk.repository import ChannelTalkCredentialsRepository
from catchup.db.models import SourceType
from catchup.search.original.ids import OriginalDocumentRef
from catchup.search.original.schemas import OriginalAuthor
from catchup.search.original.schemas import OriginalBody
from catchup.search.original.schemas import OriginalItem
from catchup.search.original.schemas import OriginalSearchRequest
from catchup.search.original.schemas import OriginalSearchResponse


class ChannelTalkOriginalError(RuntimeError):
    """Raised when ChannelTalk original content cannot be fetched."""


class ChannelTalkOriginalResolver:
    def __init__(
        self,
        *,
        fetcher: ChannelTalkUserChatOriginalFetcher | None = None,
        repository_factory: Callable[[Session], ChannelTalkCredentialsRepository]
        | None = None,
        clock: Callable[[], datetime] | None = None,
        renderer: UserChatMessageRenderer | None = None,
    ) -> None:
        self._fetcher = fetcher or ChannelTalkUserChatOriginalFetcher()
        self._repository_factory = repository_factory or ChannelTalkCredentialsRepository
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._renderer = renderer or UserChatMessageRenderer()

    async def resolve(
        self,
        *,
        request: OriginalSearchRequest,
        ref: OriginalDocumentRef,
        db: Session,
    ) -> OriginalSearchResponse:
        channel_id = ref.identifiers["channel_id"]
        user_chat_id = ref.identifiers["user_chat_id"]
        repository = self._repository_factory(db)
        credentials = repository.get_connection(channel_id=channel_id)
        if credentials is None:
            raise ChannelTalkOriginalError("channel_talk credentials not found")

        connection = ChannelTalkUserChatFullSyncConnection.from_credentials_record(
            credentials
        )
        page = await self._fetcher.fetch_user_chat_original_page(
            connection=connection,
            user_chat_id=user_chat_id,
            cursor=request.next_cursor,
        )
        title = _build_title(page.detail, fallback=user_chat_id)
        return OriginalSearchResponse(
            connector=SourceType.CHANNEL_TALK,
            entity_type=ref.entity_type,
            document_id=ref.document_id,
            title=title,
            url=build_user_chat_desk_url(
                channel_id=channel_id,
                user_chat_id=user_chat_id,
            ),
            items=[
                _map_message_to_item(message, renderer=self._renderer)
                for message in page.messages
            ],
            metadata=_build_metadata(
                detail=page.detail,
                channel_id=channel_id,
                channel_name=connection.channel_name,
                user_chat_id=user_chat_id,
            ),
            next_cursor=page.next_cursor,
            fetched_at=self._clock(),
        )


def _build_title(
    detail: ChannelTalkUserChatDetail | None,
    *,
    fallback: str,
) -> str:
    if detail is None:
        return fallback
    return detail.description or detail.name or fallback


def _map_message_to_item(
    message: ChannelTalkUserChatMessage,
    *,
    renderer: UserChatMessageRenderer,
) -> OriginalItem:
    return OriginalItem(
        id=message.message_id,
        type="event" if message.log is not None else "message",
        author=_map_author(message),
        body=OriginalBody(
            format="plain_text",
            text=renderer.render_message_content(message),
        ),
        created_at=message.created_at,
        updated_at=message.updated_at,
        metadata={
            "visibility": "internal" if message.is_private is True else "public",
            "person_type": message.person_type,
            "message_type": message.message_type,
            "attachments": [
                attachment.model_dump(mode="json", exclude_none=True)
                for attachment in message.attachments
            ],
            "buttons": [
                button.model_dump(mode="json", exclude_none=True)
                for button in message.buttons
            ],
            "blocks": [
                block.model_dump(mode="json", exclude_none=True)
                for block in message.blocks
            ],
        },
    )


def _map_author(message: ChannelTalkUserChatMessage) -> OriginalAuthor | None:
    author = message.author
    if author is None:
        if message.person_type is None:
            return None
        return OriginalAuthor(type=message.person_type)

    author_type = author.author_type or message.person_type
    author_id = (
        author.user_id
        or author.member_id
        or author.manager_id
        or author.bot_id
    )
    if author.user_id is not None or author.member_id is not None:
        author_type = "customer"
    elif author.manager_id is not None:
        author_type = "manager"
    elif author.is_bot:
        author_type = "bot"

    return OriginalAuthor(
        id=author_id,
        name=author.name or author.bot_name,
        type=author_type,
        email=author.email,
    )


def _build_metadata(
    *,
    detail: ChannelTalkUserChatDetail | None,
    channel_id: str,
    channel_name: str,
    user_chat_id: str,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "channel_id": channel_id,
        "channel_name": channel_name,
        "user_chat_id": user_chat_id,
    }
    if detail is None:
        return metadata

    metadata.update(
        {
            "state": detail.state.value,
            "priority": detail.priority,
            "managed": detail.managed,
            "goal_state": detail.goal_state,
            "customer": _dump_model(detail.customer),
            "assignment": _dump_model(detail.assignment),
            "tags": [
                tag.model_dump(mode="json", exclude_none=True)
                for tag in detail.tags
            ],
            "timing": _dump_model(detail.timing),
            "metrics": _dump_model(detail.metrics),
            "anchors": _dump_model(detail.anchors),
        }
    )
    return metadata


def _dump_model(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    return value.model_dump(mode="json", exclude_none=True)
