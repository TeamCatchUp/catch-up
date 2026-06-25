from __future__ import annotations

import asyncio
from collections.abc import Callable
from collections.abc import Iterable
from datetime import datetime
from datetime import timezone
from typing import Any
from typing import TypeVar

from fastapi.concurrency import run_in_threadpool
from langchain_core.documents import Document
from pydantic import BaseModel
from sqlalchemy.orm import Session

from catchup.components.vector_db.base import BaseVectorDbService
from catchup.connectors.atlassian.oauth_client import AtlassianOAuthClient
from catchup.connectors.atlassian.token_manager import AtlassianTokenManager
from catchup.connectors.atlassian.token_manager import AtlassianTokenProvider
from catchup.connectors.atlassian.utils import parse_atlassian_datetime
from catchup.connectors.confluence.client import ConfluenceApiClient
from catchup.connectors.confluence.client import ConfluenceApiError
from catchup.connectors.confluence.client import ConfluenceRateLimitError
from catchup.connectors.confluence.schemas import ConfluenceAttachmentResponse
from catchup.connectors.confluence.schemas import ConfluenceBlogPostResponse
from catchup.connectors.confluence.schemas import ConfluenceCommentResponse
from catchup.connectors.confluence.schemas import ConfluenceLabelResponse
from catchup.connectors.confluence.schemas import ConfluencePageResponse
from catchup.db.atlassian import oauth_repository
from catchup.db.confluence import domain_repository
from catchup.db.engine import SessionLocal
from catchup.db.models import ConfluenceUser
from catchup.db.models import SourceType
from catchup.search.original.ids import OriginalDocumentRef
from catchup.search.original.schemas.confluence import ConfluenceOriginalAttachment
from catchup.search.original.schemas.confluence import ConfluenceOriginalAuthor
from catchup.search.original.schemas.confluence import ConfluenceOriginalCommentType
from catchup.search.original.schemas.confluence import ConfluenceOriginalContent
from catchup.search.original.schemas.confluence import ConfluenceOriginalContentResponse
from catchup.search.original.schemas.confluence import ConfluenceOriginalContentType
from catchup.search.original.schemas.confluence import ConfluenceOriginalItem
from catchup.search.original.schemas.confluence import ConfluenceOriginalItemType
from catchup.server.search.schemas import OriginalContentRequest
from catchup.server.search.schemas import OriginalFileUrlRequest
from catchup.server.search.schemas import OriginalFileUrlResponse

_ModelT = TypeVar("_ModelT", bound=BaseModel)


class ConfluenceOriginalError(RuntimeError):
    """Raised when Confluence original content cannot be fetched."""

    def __init__(self, message: str, *, status_code: int = 404) -> None:
        super().__init__(message)
        self.status_code = status_code


class ConfluenceOriginalResolver:
    def __init__(
        self,
        *,
        vector_db_service: BaseVectorDbService | None = None,
        vector_db_service_factory: Callable[[], BaseVectorDbService] | None = None,
        client_factory: Callable[[str, AtlassianTokenProvider], ConfluenceApiClient]
        | None = None,
        token_provider_factory: Callable[[], AtlassianTokenProvider] | None = None,
        session_factory: Callable[[], Session] | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._vector_db_service = vector_db_service
        self._vector_db_service_factory = vector_db_service_factory
        self._client_factory = client_factory or ConfluenceApiClient
        self._token_provider_factory = token_provider_factory or _default_token_provider
        self._session_factory = session_factory or SessionLocal
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    async def resolve(
        self,
        *,
        request: OriginalContentRequest,
        ref: OriginalDocumentRef,
        db: Session | None = None,
    ) -> ConfluenceOriginalContentResponse:
        content_id = ref.identifiers["content_id"]
        chunk_index = ref.identifiers["chunk_index"]
        indexed_doc = await self._load_indexed_document(ref.document_id)
        lookup = await self._resolve_lookup_context(indexed_doc=indexed_doc, db=db)
        client = self._client_factory(
            lookup["cloud_id"],
            self._token_provider_factory(),
        )
        content_type = _to_confluence_collection_name(ref.entity_type)

        try:
            raw_content = await _fetch_content(
                client=client,
                entity_type=ref.entity_type,
                content_id=content_id,
            )
            footer_comments, inline_comments, labels, attachments = (
                await _fetch_supplementary(
                    client=client,
                    content_type=content_type,
                    content_id=content_id,
                )
            )
        except ConfluenceApiError as exc:
            raise ConfluenceOriginalError(
                str(exc),
                status_code=_resolve_confluence_error_status(exc),
            ) from exc

        content = _validate_content(ref.entity_type, raw_content)
        user_map = await self._load_users(
            cloud_id=lookup["cloud_id"],
            account_ids=_collect_author_ids(content, footer_comments, inline_comments),
            db=db,
        )
        site_url = lookup.get("site_url")
        url = _absolutize_url(content.get_web_url(), site_url)
        attachment_payloads = [_map_attachment(att) for att in attachments]

        return ConfluenceOriginalContentResponse(
            connector=SourceType.CONFLUENCE,
            entity_type=ref.entity_type,
            document_id=ref.document_id,
            title=content.title,
            url=url,
            items=[
                _map_document_item(content, entity_type=ref.entity_type, user_map=user_map),
                *[
                    _map_comment_item(
                        comment,
                        comment_type=ConfluenceOriginalCommentType.FOOTER,
                        user_map=user_map,
                    )
                    for comment in footer_comments
                ],
                *[
                    _map_comment_item(
                        comment,
                        comment_type=ConfluenceOriginalCommentType.INLINE,
                        user_map=user_map,
                    )
                    for comment in inline_comments
                ],
            ],
            metadata={
                "cloud_id": lookup["cloud_id"],
                "content_id": content_id,
                "space_id": content.space_id,
                "space_key": lookup.get("space_key"),
                "space_name": lookup.get("space_name"),
                "status": content.status,
                "author_id": content.author_id,
                "version": content.version.number if content.version else None,
                "labels": [label.name for label in labels],
                "selected_chunk_index": int(chunk_index),
                "selected_section_hierarchy": lookup.get("section_hierarchy", []),
                "attachments": [
                    attachment.model_dump(mode="json", exclude_none=True)
                    for attachment in attachment_payloads
                ],
            },
            next_cursor=None,
            fetched_at=self._clock(),
        )

    async def resolve_file_url(
        self,
        *,
        request: OriginalFileUrlRequest,
        ref: OriginalDocumentRef,
        db: Session | None = None,
    ) -> OriginalFileUrlResponse:
        attachment_id = _parse_attachment_file_key(request.file_key)
        content_id = ref.identifiers["content_id"]
        indexed_doc = await self._load_indexed_document(ref.document_id)
        lookup = await self._resolve_lookup_context(indexed_doc=indexed_doc, db=db)
        client = self._client_factory(
            lookup["cloud_id"],
            self._token_provider_factory(),
        )
        try:
            attachments = [
                ConfluenceAttachmentResponse.model_validate(raw)
                for raw in await client.get_content_attachments(
                    _to_confluence_collection_name(ref.entity_type),
                    content_id,
                )
            ]
        except ConfluenceApiError as exc:
            raise ConfluenceOriginalError(
                str(exc),
                status_code=_resolve_confluence_error_status(exc),
            ) from exc

        attachment = next((att for att in attachments if att.id == attachment_id), None)
        if attachment is None:
            raise ConfluenceOriginalError("confluence attachment not found")
        download_url = attachment.get_download_url()
        if not download_url:
            raise ConfluenceOriginalError("confluence attachment download url not found")

        return OriginalFileUrlResponse(
            connector=SourceType.CONFLUENCE,
            entity_type=ref.entity_type,
            document_id=ref.document_id,
            file_key=request.file_key,
            url=_absolutize_url(download_url, lookup.get("site_url")) or download_url,
            expires_in_seconds=900,
            fetched_at=self._clock(),
        )

    async def _load_indexed_document(self, document_id: str) -> Document:
        vector_db_service = self._vector_db_service
        if vector_db_service is None and self._vector_db_service_factory is not None:
            vector_db_service = self._vector_db_service_factory()
            self._vector_db_service = vector_db_service
        if vector_db_service is None:
            raise ConfluenceOriginalError("confluence original index lookup is not configured", status_code=500)
        docs = await vector_db_service.fetch_by_ids([document_id])
        if not docs:
            raise ConfluenceOriginalError("confluence indexed document not found")
        return docs[0]

    async def _resolve_lookup_context(
        self,
        *,
        indexed_doc: Document,
        db: Session | None,
    ) -> dict[str, Any]:
        return await run_in_threadpool(
            self._resolve_lookup_context_sync,
            indexed_doc=indexed_doc,
            db=db,
        )

    def _resolve_lookup_context_sync(
        self,
        *,
        indexed_doc: Document,
        db: Session | None,
    ) -> dict[str, Any]:
        metadata = indexed_doc.metadata or {}
        space_id = metadata.get("space_id")
        if not isinstance(space_id, str) or not space_id:
            raise ConfluenceOriginalError("confluence indexed document missing space_id")

        def _lookup(session: Session) -> dict[str, Any]:
            spaces = domain_repository.get_spaces_by_space_id(session, space_id)
            if not spaces:
                raise ConfluenceOriginalError("confluence space metadata not found")
            if len(spaces) > 1:
                raise ConfluenceOriginalError(
                    "confluence space metadata is ambiguous",
                    status_code=409,
                )
            space = spaces[0]
            token = oauth_repository.get_token_by_cloud_id(session, space.cloud_id)
            if token is None:
                raise ConfluenceOriginalError("confluence oauth token not found")
            return {
                "cloud_id": space.cloud_id,
                "site_url": token.site_url,
                "space_id": space.space_id,
                "space_key": space.space_key,
                "space_name": space.space_name,
                "section_hierarchy": metadata.get("section_hierarchy") or [],
            }

        if db is not None:
            return _lookup(db)
        with self._session_factory() as session:
            return _lookup(session)

    async def _load_users(
        self,
        *,
        cloud_id: str,
        account_ids: list[str],
        db: Session | None,
    ) -> dict[str, ConfluenceUser]:
        return await run_in_threadpool(
            self._load_users_sync,
            cloud_id=cloud_id,
            account_ids=account_ids,
            db=db,
        )

    def _load_users_sync(
        self,
        *,
        cloud_id: str,
        account_ids: list[str],
        db: Session | None,
    ) -> dict[str, ConfluenceUser]:
        if db is not None:
            return domain_repository.get_users_by_ids(db, cloud_id, account_ids)
        with self._session_factory() as session:
            return domain_repository.get_users_by_ids(session, cloud_id, account_ids)


def _default_token_provider() -> AtlassianTokenProvider:
    return AtlassianTokenProvider(
        AtlassianTokenManager(
            oauth_client=AtlassianOAuthClient(),
            oauth_repository=oauth_repository,
        )
    )


async def _fetch_content(
    *,
    client: ConfluenceApiClient,
    entity_type: str,
    content_id: str,
) -> dict[str, Any]:
    if entity_type == "page":
        return await client.get_page_by_id(content_id, body_format="storage")
    return await client.get_blogpost_by_id(content_id, body_format="storage")


async def _fetch_supplementary(
    *,
    client: ConfluenceApiClient,
    content_type: str,
    content_id: str,
) -> tuple[
    list[ConfluenceCommentResponse],
    list[ConfluenceCommentResponse],
    list[ConfluenceLabelResponse],
    list[ConfluenceAttachmentResponse],
]:
    footer_comments_coro = client.get_content_footer_comments(
        content_type,
        content_id,
        body_format="storage",
    )
    labels_coro = client.get_content_labels(content_type, content_id)
    attachments_coro = client.get_content_attachments(content_type, content_id)

    if content_type == "pages":
        (
            raw_footer_comments,
            raw_labels,
            raw_attachments,
            raw_inline_comments,
        ) = await asyncio.gather(
            footer_comments_coro,
            labels_coro,
            attachments_coro,
            client.get_content_inline_comments(
                content_type,
                content_id,
                body_format="storage",
            ),
        )
    else:
        raw_footer_comments, raw_labels, raw_attachments = await asyncio.gather(
            footer_comments_coro,
            labels_coro,
            attachments_coro,
        )
        raw_inline_comments = []

    footer_comments = _validate_many(ConfluenceCommentResponse, raw_footer_comments)
    inline_comments = _validate_many(ConfluenceCommentResponse, raw_inline_comments)
    labels = _validate_many(ConfluenceLabelResponse, raw_labels)
    attachments = _validate_many(ConfluenceAttachmentResponse, raw_attachments)
    return footer_comments, inline_comments, labels, attachments


def _validate_many(model: type[_ModelT], rows: Iterable[Any]) -> list[_ModelT]:
    return [model.model_validate(row) for row in rows]


def _validate_content(
    entity_type: str,
    raw_content: dict[str, Any],
) -> ConfluencePageResponse | ConfluenceBlogPostResponse:
    if entity_type == "page":
        return ConfluencePageResponse.model_validate(raw_content)
    return ConfluenceBlogPostResponse.model_validate(raw_content)


def _to_confluence_collection_name(entity_type: str) -> str:
    return "pages" if entity_type == "page" else "blogposts"


def _map_document_item(
    content: ConfluencePageResponse | ConfluenceBlogPostResponse,
    *,
    entity_type: str,
    user_map: dict[str, ConfluenceUser],
) -> ConfluenceOriginalItem:
    return ConfluenceOriginalItem(
        id=f"{entity_type}:{content.id}",
        type=ConfluenceOriginalItemType.DOCUMENT,
        author=_map_author(content.author_id, user_map),
        contents=[_map_storage_content(content.body)],
        created_at=parse_atlassian_datetime(content.created_at),
        updated_at=parse_atlassian_datetime(
            content.version.created_at if content.version else None
        ),
    )


def _map_comment_item(
    comment: ConfluenceCommentResponse,
    *,
    comment_type: ConfluenceOriginalCommentType,
    user_map: dict[str, ConfluenceUser],
) -> ConfluenceOriginalItem:
    inline_selection, inline_marker_ref = _extract_inline_comment_properties(comment)
    return ConfluenceOriginalItem(
        id=f"comment:{comment.id}",
        type=ConfluenceOriginalItemType.COMMENT,
        comment_type=comment_type,
        parent_id=comment.parent_comment_id,
        author=_map_author(comment.author_id, user_map),
        contents=[_map_storage_content(comment.body)],
        resolution_status=comment.resolution_status,
        inline_original_selection=inline_selection,
        inline_marker_ref=inline_marker_ref,
        created_at=parse_atlassian_datetime(comment.created_at),
        updated_at=parse_atlassian_datetime(
            comment.version.created_at if comment.version else None
        ),
    )


def _map_storage_content(body: Any) -> ConfluenceOriginalContent:
    return ConfluenceOriginalContent(
        content_type=ConfluenceOriginalContentType.STORAGE,
        payload={
            "representation": body.representation if body else None,
            "value": body.value if body else "",
        },
    )


def _map_attachment(
    attachment: ConfluenceAttachmentResponse,
) -> ConfluenceOriginalAttachment:
    return ConfluenceOriginalAttachment(
        file_key=f"attachment:{attachment.id}",
        id=attachment.id,
        name=attachment.title,
        media_type=attachment.media_type,
        size=attachment.file_size,
        created_at=parse_atlassian_datetime(attachment.created_at),
        updated_at=parse_atlassian_datetime(
            attachment.version.created_at if attachment.version else None
        ),
    )


def _map_author(
    account_id: str | None,
    user_map: dict[str, ConfluenceUser],
) -> ConfluenceOriginalAuthor | None:
    if not account_id:
        return None
    user = user_map.get(account_id)
    if user is None:
        return ConfluenceOriginalAuthor(id=account_id)
    return ConfluenceOriginalAuthor(
        id=account_id,
        name=user.display_name or user.public_name,
        email=user.email,
        avatar_url=user.avatar_url,
    )


def _collect_author_ids(
    content: ConfluencePageResponse | ConfluenceBlogPostResponse,
    footer_comments: list[ConfluenceCommentResponse],
    inline_comments: list[ConfluenceCommentResponse],
) -> list[str]:
    ids = {content.author_id}
    ids.update(comment.author_id for comment in footer_comments)
    ids.update(comment.author_id for comment in inline_comments)
    return sorted(author_id for author_id in ids if author_id)


def _extract_inline_comment_properties(
    comment: ConfluenceCommentResponse,
) -> tuple[str | None, str | None]:
    properties = comment.properties
    if not isinstance(properties, dict):
        return None, None

    selection = properties.get("inline-original-selection")
    marker_ref = properties.get("inline-marker-ref")
    return _extract_property_value(selection), _extract_property_value(marker_ref)


def _extract_property_value(value: Any) -> str | None:
    if isinstance(value, dict):
        candidate = value.get("value")
        return candidate if isinstance(candidate, str) and candidate else None
    return value if isinstance(value, str) and value else None


def _parse_attachment_file_key(file_key: str) -> str:
    prefix = "attachment:"
    if not file_key.startswith(prefix) or len(file_key) == len(prefix):
        raise ConfluenceOriginalError(
            "confluence file_key must be attachment:{attachment_id}",
            status_code=400,
        )
    return file_key[len(prefix) :]


def _absolutize_url(url: str | None, site_url: Any) -> str | None:
    if not url:
        return None
    if url.startswith(("http://", "https://")):
        return url
    if not isinstance(site_url, str) or not site_url:
        return url
    return f"{site_url.rstrip('/')}/{url.lstrip('/')}"


def _resolve_confluence_error_status(exc: ConfluenceApiError) -> int:
    if isinstance(exc, ConfluenceRateLimitError):
        return 429
    if exc.status_code is not None and 400 <= exc.status_code < 500:
        return exc.status_code
    if exc.status_code is not None and exc.status_code >= 500:
        return 502
    return 502
