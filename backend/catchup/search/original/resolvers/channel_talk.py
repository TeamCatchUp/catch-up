from __future__ import annotations

from collections.abc import Callable
from collections.abc import Iterable
from collections.abc import Mapping
from datetime import datetime
from datetime import timezone
from typing import Any

from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from catchup.connectors.channel_talk.core.client import ChannelTalkCoreApiClient
from catchup.connectors.channel_talk.core.user_chat_full_sync_models import (
    ChannelTalkUserChatFullSyncConnection,
)
from catchup.connectors.channel_talk.core.user_chat_ids import build_user_chat_desk_url
from catchup.connectors.channel_talk.core.user_chat_original_fetcher import (
    ChannelTalkUserChatOriginalFetcher,
)
from catchup.connectors.channel_talk.exceptions import ChannelTalkError
from catchup.connectors.channel_talk.schemas.channel_connection import (
    ChannelTalkCredentialsRecord,
)
from catchup.connectors.channel_talk.schemas.channel_metadata import (
    ChannelTalkManagerMetadata,
)
from catchup.connectors.channel_talk.schemas.user import ChannelTalkUserFoundation
from catchup.connectors.channel_talk.schemas.user_chat import ChannelTalkUserChatDetail
from catchup.connectors.channel_talk.schemas.user_chat_message import (
    ChannelTalkUserChatMessage,
)
from catchup.db.channel_talk.repository import ChannelTalkCredentialsRepository
from catchup.db.channel_talk.repository import ChannelTalkMetadataRepository
from catchup.db.engine import SessionLocal
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
from catchup.server.search.schemas import OriginalFileUrlRequest
from catchup.server.search.schemas import OriginalFileUrlResponse


class ChannelTalkOriginalError(RuntimeError):
    """Raised when ChannelTalk original content cannot be fetched."""

    def __init__(self, message: str, *, status_code: int = 404) -> None:
        super().__init__(message)
        self.status_code = status_code


class ChannelTalkOriginalResolver:
    def __init__(
        self,
        *,
        fetcher: ChannelTalkUserChatOriginalFetcher | None = None,
        client: ChannelTalkCoreApiClient | None = None,
        repository_factory: Callable[[Session], ChannelTalkCredentialsRepository]
        | None = None,
        metadata_repository_factory: Callable[[Session], ChannelTalkMetadataRepository]
        | None = None,
        session_factory: Callable[[], Session] | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._fetcher = fetcher or ChannelTalkUserChatOriginalFetcher()
        self._client = client or ChannelTalkCoreApiClient()
        self._repository_factory = (
            repository_factory or ChannelTalkCredentialsRepository
        )
        self._metadata_repository_factory = (
            metadata_repository_factory or ChannelTalkMetadataRepository
        )
        self._session_factory = session_factory or SessionLocal
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    async def resolve(
        self,
        *,
        request: OriginalContentRequest,
        ref: OriginalDocumentRef,
        db: Session | None = None,
    ) -> ChannelTalkUserChatOriginalContentResponse:
        channel_id = ref.identifiers["channel_id"]
        user_chat_id = ref.identifiers["user_chat_id"]
        credentials = await self._get_credentials(channel_id=channel_id, db=db)
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
        visible_messages = [message for message in page.messages if message.log is None]
        manager_ids = _collect_manager_author_ids(visible_messages)
        manager_map = _build_manager_metadata_map(
            await self._list_managers_by_channel_and_ids(
                channel_id=channel_id,
                manager_ids=manager_ids,
                db=db,
            )
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
                _map_message_to_item(
                    message,
                    customer=page.detail.customer if page.detail else None,
                    manager_map=manager_map,
                )
                for message in visible_messages
            ],
            metadata=_build_metadata(
                detail=page.detail,
                messages=page.messages,
                channel_id=channel_id,
                channel_name=connection.channel_name,
                user_chat_id=user_chat_id,
            ),
            next_cursor=page.next_cursor,
            fetched_at=self._clock(),
        )

    async def resolve_file_url(
        self,
        *,
        request: OriginalFileUrlRequest,
        ref: OriginalDocumentRef,
        db: Session | None = None,
    ) -> OriginalFileUrlResponse:
        channel_id = ref.identifiers["channel_id"]
        user_chat_id = ref.identifiers["user_chat_id"]
        credentials = await self._get_credentials(channel_id=channel_id, db=db)
        if credentials is None:
            raise ChannelTalkOriginalError("channel_talk credentials not found")

        try:
            url = await self._client.get_user_chat_file_url(
                access_key=credentials.access_key,
                access_secret=credentials.access_secret,
                channel_id=channel_id,
                user_chat_id=user_chat_id,
                file_key=request.file_key,
            )
        except ChannelTalkError as exc:
            raise ChannelTalkOriginalError(
                str(exc),
                status_code=_resolve_channel_talk_error_status(exc),
            ) from exc

        return OriginalFileUrlResponse(
            connector=SourceType.CHANNEL_TALK,
            entity_type=ref.entity_type,
            document_id=ref.document_id,
            file_key=request.file_key,
            url=url,
            expires_in_seconds=900,
            fetched_at=self._clock(),
        )

    async def _get_credentials(
        self,
        *,
        channel_id: str,
        db: Session | None,
    ) -> ChannelTalkCredentialsRecord | None:
        return await run_in_threadpool(
            self._get_credentials_sync,
            channel_id=channel_id,
            db=db,
        )

    def _get_credentials_sync(
        self,
        *,
        channel_id: str,
        db: Session | None,
    ) -> ChannelTalkCredentialsRecord | None:
        if db is not None:
            return self._repository_factory(db).get_connection(channel_id=channel_id)

        with self._session_factory() as session:
            return self._repository_factory(session).get_connection(
                channel_id=channel_id
            )

    async def _list_managers_by_channel_and_ids(
        self,
        *,
        channel_id: str,
        manager_ids: set[str],
        db: Session | None,
    ) -> list[ChannelTalkManagerMetadata]:
        if not manager_ids:
            return []
        return await run_in_threadpool(
            self._list_managers_by_channel_and_ids_sync,
            channel_id=channel_id,
            manager_ids=manager_ids,
            db=db,
        )

    def _list_managers_by_channel_and_ids_sync(
        self,
        *,
        channel_id: str,
        manager_ids: set[str],
        db: Session | None,
    ) -> list[ChannelTalkManagerMetadata]:
        if db is not None:
            return self._metadata_repository_factory(db).list_managers_by_channel_and_ids(
                channel_id,
                manager_ids,
            )

        with self._session_factory() as session:
            return self._metadata_repository_factory(
                session
            ).list_managers_by_channel_and_ids(
                channel_id,
                manager_ids,
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
    customer: ChannelTalkUserFoundation | None = None,
    manager_map: Mapping[str, ChannelTalkManagerMetadata] | None = None,
) -> ChannelTalkUserChatOriginalItem:
    return ChannelTalkUserChatOriginalItem(
        id=message.message_id,
        type=ChannelTalkUserChatOriginalItemType.MESSAGE,
        visibility=(
            ChannelTalkUserChatOriginalVisibility.INTERNAL
            if message.is_private is True
            else ChannelTalkUserChatOriginalVisibility.PUBLIC
        ),
        author=_map_author(
            message,
            customer=customer,
            manager_map=manager_map,
        ),
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
        block.model_dump(mode="json", exclude_none=True) for block in message.blocks
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
    block_text_parts: list[str] = []
    for block in blocks:
        for value in (block.get("text"), block.get("value")):
            if not isinstance(value, str):
                continue
            normalized_value = value.strip()
            if normalized_value and normalized_value not in block_text_parts:
                block_text_parts.append(normalized_value)
    block_text = "\n".join(block_text_parts)
    return bool(block_text) and text.strip() == block_text


def _map_author(
    message: ChannelTalkUserChatMessage,
    *,
    customer: ChannelTalkUserFoundation | None = None,
    manager_map: Mapping[str, ChannelTalkManagerMetadata] | None = None,
) -> ChannelTalkOriginalAuthor | None:
    author = message.author
    if author is None:
        if message.person_type is None:
            return None
        author_type = _normalize_author_type(message.person_type)
        is_customer = author_type == ChannelTalkOriginalAuthorType.CUSTOMER
        person_id = (
            message.raw_payload.get("personId")
            if isinstance(message.raw_payload, Mapping)
            else None
        )
        manager_metadata = (
            manager_map.get(person_id)
            if manager_map is not None and message.person_type == "manager"
            else None
        )
        return ChannelTalkOriginalAuthor(
            id=(
                customer.external_user_id
                if is_customer and customer
                else person_id
            ),
            name=customer.name
            if is_customer and customer
            else (manager_metadata.name if manager_metadata else None),
            type=author_type,
            email=customer.email
            if is_customer and customer
            else (manager_metadata.email if manager_metadata else None),
            avatar_url=customer.avatar_url
            if is_customer and customer
            else (manager_metadata.avatar_url if manager_metadata else None),
        )

    author_id = author.user_id or author.member_id or author.manager_id or author.bot_id
    author_type = _normalize_author_type(
        author.author_type or message.person_type,
        has_customer_identity=(
            author.user_id is not None or author.member_id is not None
        ),
        has_manager_identity=author.manager_id is not None,
        is_bot=author.is_bot,
    )
    is_manager = author_type == ChannelTalkOriginalAuthorType.MANAGER
    manager_metadata = (
        manager_map.get(author_id)
        if is_manager and manager_map is not None and author_id is not None
        else None
    )

    return ChannelTalkOriginalAuthor(
        id=author_id,
        name=author.name
        or author.bot_name
        or (manager_metadata.name if manager_metadata else None)
        or (customer.name if author_type == ChannelTalkOriginalAuthorType.CUSTOMER and customer else None),
        type=author_type,
        email=author.email
        or (manager_metadata.email if manager_metadata else None)
        or (customer.email if author_type == ChannelTalkOriginalAuthorType.CUSTOMER and customer else None),
        avatar_url=author.avatar_url
        or (manager_metadata.avatar_url if manager_metadata else None)
        or (customer.avatar_url
            if author_type == ChannelTalkOriginalAuthorType.CUSTOMER and customer
            else None),
    )


def _collect_manager_author_ids(
    messages: Iterable[ChannelTalkUserChatMessage],
) -> set[str]:
    manager_ids: set[str] = set()
    for message in messages:
        author = message.author
        if author is None:
            if message.person_type != "manager":
                continue
            person_id = (
                message.raw_payload.get("personId")
                if isinstance(message.raw_payload, Mapping)
                else None
            )
            if isinstance(person_id, str) and person_id.strip():
                manager_ids.add(person_id.strip())
            continue

        author_id = author.user_id or author.member_id or author.manager_id or author.bot_id
        author_type = _normalize_author_type(
            author.author_type or message.person_type,
            has_customer_identity=(
                author.user_id is not None or author.member_id is not None
            ),
            has_manager_identity=author.manager_id is not None,
            is_bot=author.is_bot,
        )
        if (
            author_type == ChannelTalkOriginalAuthorType.MANAGER
            and author_id is not None
        ):
            manager_ids.add(author_id)
    return manager_ids


def _build_manager_metadata_map(
    managers: Iterable[ChannelTalkManagerMetadata] | None,
) -> dict[str, ChannelTalkManagerMetadata]:
    manager_map: dict[str, ChannelTalkManagerMetadata] = {}
    if not managers:
        return manager_map
    for manager in managers:
        manager_map.setdefault(manager.manager_id, manager)
    return manager_map


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


def _resolve_channel_talk_error_status(exc: ChannelTalkError) -> int:
    status_code = getattr(exc, "status_code", 502)
    if isinstance(status_code, int) and 400 <= status_code <= 599:
        return status_code
    return 502


def _build_metadata(
    *,
    detail: ChannelTalkUserChatDetail | None,
    messages: tuple[ChannelTalkUserChatMessage, ...] | list[ChannelTalkUserChatMessage],
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
        customer = _build_customer_metadata_from_messages(messages)
        if customer is not None:
            metadata["customer"] = customer
        return metadata

    customer = _merge_customer_with_form_data(
        detail.customer,
        messages=messages,
    )
    metadata.update(
        {
            "name": detail.name,
            "description": detail.description,
            "state": detail.state.value,
            "priority": detail.priority,
            "managed": detail.managed,
            "goal_state": detail.goal_state,
            "customer": customer,
            "assignment": _dump_model(detail.assignment),
            "tags": [
                tag.model_dump(mode="json", exclude_none=True) for tag in detail.tags
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


def _build_customer_metadata_from_messages(
    messages: tuple[ChannelTalkUserChatMessage, ...] | list[ChannelTalkUserChatMessage],
) -> dict[str, Any] | None:
    values: dict[str, str] = {}
    for message in messages:
        if message.form is None:
            continue
        for message_input in message.form.inputs:
            value = message_input.value
            if value is None or not str(value).strip():
                continue
            binding = message_input.binding_key
            if not binding:
                continue
            lowered = binding.strip().lower()
            if lowered.startswith("user.profile."):
                lowered = lowered[len("user.profile.") :]
            lowered = lowered.strip()
            if lowered in {
                "name",
                "email",
                "mobilenumber",
                "mobile",
                "phonenumber",
                "mobilephone",
            }:
                if lowered == "name":
                    values["name"] = str(value).strip()
                elif lowered == "email":
                    values["email"] = str(value).strip()
                elif lowered in {"mobile", "mobilenumber", "phonenumber", "mobilephone"}:
                    values["mobile_number"] = str(value).strip()
            elif lowered in {
                "landline",
                "landlinenumber",
                "telephonenumber",
                "landlinephone",
            }:
                values["landline_number"] = str(value).strip()

    if not values:
        return None
    return values


def _merge_customer_with_form_data(
    customer: ChannelTalkUserFoundation | None,
    *,
    messages: tuple[ChannelTalkUserChatMessage, ...] | list[ChannelTalkUserChatMessage],
) -> dict[str, Any] | None:
    base = _dump_model(customer) or {}
    form_values = _build_customer_metadata_from_messages(messages)
    if not form_values:
        return base or None

    customer_payload = dict(base)
    customer_payload.update(form_values)
    return customer_payload
