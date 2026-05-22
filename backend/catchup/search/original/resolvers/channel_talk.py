from __future__ import annotations

from collections.abc import Callable
from collections.abc import Mapping
from datetime import datetime
from datetime import timezone
from typing import Any

from sqlalchemy.orm import Session

from catchup.connectors.channel_talk.core.user_chat_full_sync_models import (
    ChannelTalkUserChatFullSyncConnection,
)
from catchup.connectors.channel_talk.core.user_chat_ids import build_user_chat_desk_url
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
from catchup.search.original.schemas.channel_talk import ChannelTalkOriginalAuthor
from catchup.search.original.schemas.channel_talk import ChannelTalkOriginalAuthorType
from catchup.search.original.schemas.channel_talk import (
    ChannelTalkUserChatOriginalContent,
)
from catchup.search.original.schemas.channel_talk import (
    ChannelTalkUserChatOriginalContentResponse,
)
from catchup.search.original.schemas.channel_talk import (
    ChannelTalkUserChatOriginalContentType,
)
from catchup.search.original.schemas.channel_talk import ChannelTalkUserChatOriginalItem
from catchup.search.original.schemas.channel_talk import (
    ChannelTalkUserChatOriginalItemType,
)
from catchup.search.original.schemas.channel_talk import (
    ChannelTalkUserChatOriginalVisibility,
)
from catchup.server.search.schemas import OriginalContentRequest


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
    ) -> None:
        self._fetcher = fetcher or ChannelTalkUserChatOriginalFetcher()
        self._repository_factory = repository_factory or ChannelTalkCredentialsRepository
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    async def resolve(
        self,
        *,
        request: OriginalContentRequest,
        ref: OriginalDocumentRef,
        db: Session,
    ) -> ChannelTalkUserChatOriginalContentResponse:
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
        return ChannelTalkUserChatOriginalContentResponse(
            connector=SourceType.CHANNEL_TALK,
            entity_type=ref.entity_type,
            document_id=ref.document_id,
            title=title,
            url=build_user_chat_desk_url(
                channel_id=channel_id,
                user_chat_id=user_chat_id,
            ),
            items=[
                _map_message_to_item(message)
                for message in page.messages
                if message.log is None
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
) -> ChannelTalkUserChatOriginalItem:
    return ChannelTalkUserChatOriginalItem(
        id=message.message_id,
        type=ChannelTalkUserChatOriginalItemType.MESSAGE,
        visibility=(
            ChannelTalkUserChatOriginalVisibility.INTERNAL
            if message.is_private is True
            else ChannelTalkUserChatOriginalVisibility.PUBLIC
        ),
        author=_map_author(message),
        contents=_map_message_contents(message),
        created_at=message.created_at,
        updated_at=message.updated_at,
    )


def _map_message_contents(
    message: ChannelTalkUserChatMessage,
) -> list[ChannelTalkUserChatOriginalContent]:
    contents: list[ChannelTalkUserChatOriginalContent] = []
    explicit_text = _read_explicit_plain_text(message)
    block_payloads = [
        block.model_dump(mode="json", exclude_none=True)
        for block in message.blocks
    ]

    if explicit_text and not _matches_block_text(
        text=explicit_text,
        blocks=block_payloads,
    ):
        contents.append(
            ChannelTalkUserChatOriginalContent(
                content_type=ChannelTalkUserChatOriginalContentType.TEXT,
                payload={"text": explicit_text},
            )
        )
    if block_payloads:
        contents.append(
            ChannelTalkUserChatOriginalContent(
                content_type=ChannelTalkUserChatOriginalContentType.BLOCK,
                payload={"blocks": block_payloads},
            )
        )
    if message.buttons:
        contents.append(
            ChannelTalkUserChatOriginalContent(
                content_type=ChannelTalkUserChatOriginalContentType.BUTTON,
                payload={
                    "buttons": [
                        button.model_dump(mode="json", exclude_none=True)
                        for button in message.buttons
                    ]
                },
            )
        )
    if message.form is not None:
        contents.append(
            ChannelTalkUserChatOriginalContent(
                content_type=ChannelTalkUserChatOriginalContentType.FORM,
                payload={
                    "form": message.form.model_dump(mode="json", exclude_none=True)
                },
            )
        )
    if message.attachments:
        contents.append(
            ChannelTalkUserChatOriginalContent(
                content_type=ChannelTalkUserChatOriginalContentType.FILE,
                payload={
                    "files": [
                        attachment.model_dump(mode="json", exclude_none=True)
                        for attachment in message.attachments
                    ]
                },
            )
        )
    return contents


def _read_explicit_plain_text(message: ChannelTalkUserChatMessage) -> str | None:
    payload = message.raw_payload
    if not isinstance(payload, Mapping):
        return None
    for key in ("plainText", "plain_text", "text", "body"):
        value = payload.get(key)
        if isinstance(value, str):
            text = value.strip()
            if text:
                return text
    return None


def _matches_block_text(
    *,
    text: str,
    blocks: list[dict[str, Any]],
) -> bool:
    block_text = "\n".join(
        str(value).strip()
        for block in blocks
        for value in (block.get("text"), block.get("value"))
        if isinstance(value, str) and value.strip()
    )
    return bool(block_text) and text.strip() == block_text


def _map_author(
    message: ChannelTalkUserChatMessage,
) -> ChannelTalkOriginalAuthor | None:
    author = message.author
    if author is None:
        if message.person_type is None:
            return None
        return ChannelTalkOriginalAuthor(
            type=_normalize_author_type(message.person_type)
        )

    author_id = (
        author.user_id
        or author.member_id
        or author.manager_id
        or author.bot_id
    )

    return ChannelTalkOriginalAuthor(
        id=author_id,
        name=author.name or author.bot_name,
        type=_normalize_author_type(
            author.author_type or message.person_type,
            has_customer_identity=(
                author.user_id is not None or author.member_id is not None
            ),
            has_manager_identity=author.manager_id is not None,
            is_bot=author.is_bot,
        ),
        email=author.email,
    )


def _normalize_author_type(
    value: str | None,
    *,
    has_customer_identity: bool = False,
    has_manager_identity: bool = False,
    is_bot: bool = False,
) -> ChannelTalkOriginalAuthorType | None:
    if has_customer_identity or value in {"customer", "user", "member"}:
        return ChannelTalkOriginalAuthorType.CUSTOMER
    if has_manager_identity or is_bot or value in {"manager", "bot"}:
        return ChannelTalkOriginalAuthorType.MANAGER
    return None


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
