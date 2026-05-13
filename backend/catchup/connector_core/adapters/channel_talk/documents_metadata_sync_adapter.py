from __future__ import annotations

from collections.abc import AsyncIterator
from collections.abc import Awaitable
from collections.abc import Callable
from collections.abc import Mapping
from functools import partial
from typing import Any
from typing import Protocol

from fastapi.concurrency import run_in_threadpool

from catchup.connector_core.ports.metadata_sync import MetadataSyncPlan
from catchup.connector_core.ports.metadata_sync import MetadataSyncRequest
from catchup.connector_core.ports.metadata_sync import MetadataSyncStep
from catchup.connector_core.ports.metadata_sync import MetadataSyncStepResult
from catchup.connectors.channel_talk.document_space.client import (
    ChannelTalkDocumentsApiClient,
)
from catchup.connectors.channel_talk.document_space.http_client import (
    ChannelTalkDocumentsHttpClient,
)
from catchup.connectors.channel_talk.exceptions import ChannelTalkConflictError
from catchup.connectors.channel_talk.exceptions import ChannelTalkError
from catchup.connectors.channel_talk.exceptions import ChannelTalkPersistenceError
from catchup.connectors.channel_talk.exceptions import ChannelTalkValidationError
from catchup.connectors.channel_talk.schemas.document_connection import (
    ChannelTalkDocumentCredentialsRecord,
)
from catchup.connectors.channel_talk.schemas.document_metadata import (
    ChannelTalkDocumentAuthorMetadata,
)
from catchup.connectors.channel_talk.schemas.document_metadata import (
    ChannelTalkDocumentAuthorPage,
)
from catchup.connectors.channel_talk.schemas.document_metadata import (
    ChannelTalkDocumentNavNodeMetadata,
)


class ChannelTalkDocumentMetadataStore(Protocol):
    def get_document_connection(
        self,
        channel_id: str | None = None,
        space_id: str | None = None,
    ) -> ChannelTalkDocumentCredentialsRecord | None: ...

    def bulk_upsert_document_authors(
        self,
        payloads: list[ChannelTalkDocumentAuthorMetadata],
    ) -> list[ChannelTalkDocumentAuthorMetadata]: ...

    def bulk_upsert_document_nav_nodes(
        self,
        payloads: list[ChannelTalkDocumentNavNodeMetadata],
    ) -> list[ChannelTalkDocumentNavNodeMetadata]: ...

    def commit(self) -> None: ...


class ChannelTalkDocumentMetadataSyncAdapter:
    def __init__(
        self,
        *,
        store: ChannelTalkDocumentMetadataStore,
        client: ChannelTalkDocumentsApiClient | None = None,
    ) -> None:
        self.store = store
        self.client = client

    async def build_plan(
        self,
        request: MetadataSyncRequest,
    ) -> MetadataSyncPlan:
        connection = await self._load_connection(request)
        return MetadataSyncPlan(
            request=request,
            steps=(
                self._step(
                    "document_space",
                    self._sync_space,
                    request=request,
                    connection=connection,
                ),
                self._step(
                    "document_authors",
                    self._sync_authors,
                    request=request,
                    connection=connection,
                ),
                self._step(
                    "document_nav_nodes",
                    self._sync_nav_nodes,
                    request=request,
                    connection=connection,
                ),
            ),
        )

    @staticmethod
    def _step(
        name: str,
        handler,
        *,
        request: MetadataSyncRequest,
        connection: ChannelTalkDocumentCredentialsRecord,
    ) -> MetadataSyncStep:
        return MetadataSyncStep(
            name=name,
            run=partial(handler, request=request, connection=connection),
        )

    async def _sync_space(
        self,
        _completed: Mapping[str, MetadataSyncStepResult],
        *,
        request: MetadataSyncRequest,
        connection: ChannelTalkDocumentCredentialsRecord,
    ) -> MetadataSyncStepResult:
        client = self._client_for(connection)
        space = await client.get_current_space()
        if space.space_id != connection.space_id:
            raise ChannelTalkConflictError(
                "Stored Channel Talk Documents credentials do not match the requested space",
            )
        return MetadataSyncStepResult(synced_count=1)

    async def _sync_authors(
        self,
        _completed: Mapping[str, MetadataSyncStepResult],
        *,
        request: MetadataSyncRequest,
        connection: ChannelTalkDocumentCredentialsRecord,
    ) -> MetadataSyncStepResult:
        synced = 0
        client = self._client_for(connection)
        async for page in self._iter_author_pages(lambda since: client.list_authors(since=since)):
            payloads = [
                item.model_copy(
                    update={
                        "channel_id": request.tenant_id,
                        "space_id": connection.space_id,
                    }
                )
                for item in page.authors
            ]
            if payloads:
                stored = await self._store_and_commit(
                    self.store.bulk_upsert_document_authors,
                    payloads,
                    error_message="Failed to persist Channel Talk Documents authors",
                )
                synced += len(stored)
        return MetadataSyncStepResult(synced_count=synced)

    async def _sync_nav_nodes(
        self,
        _completed: Mapping[str, MetadataSyncStepResult],
        *,
        request: MetadataSyncRequest,
        connection: ChannelTalkDocumentCredentialsRecord,
    ) -> MetadataSyncStepResult:
        client = self._client_for(connection)
        page = await client.list_nav_nodes()
        payloads = [
            item.model_copy(
                update={
                    "channel_id": request.tenant_id,
                    "space_id": connection.space_id,
                }
            )
            for item in page.nav_nodes
        ]
        if not payloads:
            return MetadataSyncStepResult(synced_count=0)
        stored = await self._store_and_commit(
            self.store.bulk_upsert_document_nav_nodes,
            payloads,
            error_message="Failed to persist Channel Talk Documents navigation metadata",
        )
        return MetadataSyncStepResult(synced_count=len(stored))

    async def _load_connection(
        self,
        request: MetadataSyncRequest,
    ) -> ChannelTalkDocumentCredentialsRecord:
        try:
            record = await run_in_threadpool(
                self.store.get_document_connection,
                request.tenant_id,
                request.target_id,
            )
        except ChannelTalkError:
            raise
        except Exception as exc:
            raise ChannelTalkPersistenceError(
                "Failed to load Channel Talk Documents credentials"
            ) from exc
        if record is None:
            raise ChannelTalkValidationError(
                "Channel Talk Documents credentials are not installed"
            )
        if record.channel_id != request.tenant_id:
            raise ChannelTalkConflictError(
                "Stored Channel Talk Documents credentials do not match the requested channel",
            )
        return record

    def _client_for(
        self,
        connection: ChannelTalkDocumentCredentialsRecord,
    ) -> ChannelTalkDocumentsApiClient:
        if self.client is not None:
            return self.client
        return ChannelTalkDocumentsApiClient(
            transport=ChannelTalkDocumentsHttpClient(
                access_key=connection.access_key or "",
                access_secret=connection.access_secret or "",
                space_id=connection.space_id,
            ),
        )

    @staticmethod
    async def _iter_author_pages(
        fetch_page: Callable[[str | None], Awaitable[ChannelTalkDocumentAuthorPage]],
    ) -> AsyncIterator[ChannelTalkDocumentAuthorPage]:
        since: str | None = None
        while True:
            page = await fetch_page(since)
            yield page
            next_page_token = page.next_page_token
            if not next_page_token or next_page_token == since:
                break
            since = next_page_token

    async def _store_and_commit(
        self,
        operation: Callable[..., Any],
        *args: Any,
        error_message: str,
        **kwargs: Any,
    ) -> Any:
        try:
            stored = await run_in_threadpool(operation, *args, **kwargs)
            await run_in_threadpool(self.store.commit)
            return stored
        except ChannelTalkError:
            raise
        except Exception as exc:
            raise ChannelTalkPersistenceError(error_message) from exc
