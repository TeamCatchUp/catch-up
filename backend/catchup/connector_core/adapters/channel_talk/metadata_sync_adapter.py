from __future__ import annotations

from collections.abc import AsyncIterator
from collections.abc import Awaitable
from collections.abc import Callable
from collections.abc import Mapping
from functools import partial
from typing import Any
from typing import Protocol
from typing import TypeVar

from fastapi.concurrency import run_in_threadpool

from catchup.connector_core.ports.metadata_sync import MetadataSyncPlan
from catchup.connector_core.ports.metadata_sync import MetadataSyncRequest
from catchup.connector_core.ports.metadata_sync import MetadataSyncStep
from catchup.connector_core.ports.metadata_sync import MetadataSyncStepResult
from catchup.connectors.channel_talk.core_api_client import ChannelTalkCoreApiClient
from catchup.connectors.channel_talk.exceptions import ChannelTalkConflictError
from catchup.connectors.channel_talk.exceptions import ChannelTalkError
from catchup.connectors.channel_talk.exceptions import ChannelTalkPersistenceError
from catchup.connectors.channel_talk.exceptions import ChannelTalkValidationError
from catchup.connectors.channel_talk.schemas.channel_connection import (
    ChannelTalkCredentialsRecord,
)
from catchup.connectors.channel_talk.schemas.channel_metadata import ChannelTalkChannel
from catchup.connectors.channel_talk.schemas.channel_metadata import (
    ChannelTalkGroupManagerMembership,
)
from catchup.connectors.channel_talk.schemas.channel_metadata import (
    ChannelTalkGroupMetadata,
)
from catchup.connectors.channel_talk.schemas.channel_metadata import (
    ChannelTalkGroupMetadataPage,
)
from catchup.connectors.channel_talk.schemas.channel_metadata import (
    ChannelTalkManagerMetadata,
)
from catchup.connectors.channel_talk.schemas.channel_metadata import (
    ChannelTalkManagerMetadataPage,
)

ChannelTalkMetadataT = TypeVar(
    "ChannelTalkMetadataT",
    ChannelTalkManagerMetadata,
    ChannelTalkGroupMetadata,
)
ChannelTalkMetadataPageT = TypeVar(
    "ChannelTalkMetadataPageT",
    ChannelTalkManagerMetadataPage,
    ChannelTalkGroupMetadataPage,
)


class ChannelTalkMetadataStore(Protocol):
    """
    Channel Talk metadata adapter가 기대하는 최소 저장소 계약

    adapter는 "무엇을 저장해야 하는지"는 알지만
    SQLAlchemy row CRUD 같은 concrete persistence 세부는 모르게 유지
    """

    def get_connection(self) -> ChannelTalkCredentialsRecord | None: ...

    def upsert_channel_metadata(
        self,
        payload: ChannelTalkChannel,
    ) -> ChannelTalkChannel | None: ...

    def bulk_upsert_managers(
        self,
        payloads: list[ChannelTalkManagerMetadata],
    ) -> list[ChannelTalkManagerMetadata]: ...

    def bulk_upsert_groups(
        self,
        payloads: list[ChannelTalkGroupMetadata],
    ) -> list[ChannelTalkGroupMetadata]: ...

    def replace_group_managers(
        self,
        *,
        channel_id: str,
        memberships: tuple[ChannelTalkGroupManagerMembership, ...],
    ) -> tuple[ChannelTalkGroupManagerMembership, ...]: ...

    def commit(self) -> None: ...


class ChannelTalkMetadataSyncAdapter:
    """Channel Talk metadata 수집/저장을 core metadata port 뒤로 감싼다."""

    def __init__(
        self,
        *,
        store: ChannelTalkMetadataStore,
        client: ChannelTalkCoreApiClient | None = None,
    ) -> None:
        self.store = store
        self.client = client or ChannelTalkCoreApiClient()

    async def build_plan(
        self,
        request: MetadataSyncRequest,
    ) -> MetadataSyncPlan:
        connection = await self._load_connection(request)
        return MetadataSyncPlan(
            request=request,
            steps=self._build_steps(request, connection),
        )

    def _build_steps(
        self,
        request: MetadataSyncRequest,
        connection: ChannelTalkCredentialsRecord,
    ) -> tuple[MetadataSyncStep, ...]:
        return (
            self._step(
                "channel",
                self._sync_channel,
                request=request,
                connection=connection,
            ),
            self._step(
                "managers",
                self._sync_managers,
                request=request,
                connection=connection,
            ),
            self._step(
                "groups",
                self._sync_groups,
                request=request,
                connection=connection,
            ),
            self._step(
                "group_memberships",
                self._sync_group_memberships,
                request=request,
                depends_on=("groups",),
            ),
        )

    @staticmethod
    def _step(
        name: str,
        handler,
        *,
        request: MetadataSyncRequest,
        connection: ChannelTalkCredentialsRecord | None = None,
        depends_on: tuple[str, ...] = (),
    ) -> MetadataSyncStep:
        handler_kwargs: dict[str, Any] = {"request": request}

        if connection is not None:
            handler_kwargs["connection"] = connection
            
        return MetadataSyncStep(
            name=name,
            depends_on=depends_on,
            run=partial(handler, **handler_kwargs),
        )

    async def _sync_channel(
        self,
        _completed: Mapping[str, MetadataSyncStepResult],
        *,
        request: MetadataSyncRequest,
        connection: ChannelTalkCredentialsRecord,
    ) -> MetadataSyncStepResult:
        current_channel = await self.client.get_current_channel(
            access_key=connection.access_key or "",
            access_secret=connection.access_secret or "",
        )
        channel = current_channel.channel
        if channel.channel_id != request.tenant_id:
            raise ChannelTalkConflictError(
                "Stored Channel Talk credentials do not match the requested channel",
            )

        await self._store_and_commit(
            self.store.upsert_channel_metadata,
            channel,
            error_message="Failed to persist Channel Talk channel metadata",
        )
        return MetadataSyncStepResult(synced_count=1)

    async def _sync_managers(
        self,
        _completed: Mapping[str, MetadataSyncStepResult],
        *,
        request: MetadataSyncRequest,
        connection: ChannelTalkCredentialsRecord,
    ) -> MetadataSyncStepResult:
        synced = 0

        async for page in self._iter_pages(
            lambda since: self.client.list_managers(
                access_key=connection.access_key or "",
                access_secret=connection.access_secret or "",
                since=since,
            )
        ):
            payloads = self._with_channel_id(page.managers, request.tenant_id)
            if payloads:
                stored = await self._store_and_commit(
                    self.store.bulk_upsert_managers,
                    payloads,
                    error_message="Failed to persist Channel Talk manager metadata",
                )
                synced += len(stored)

        return MetadataSyncStepResult(synced_count=synced)

    async def _sync_groups(
        self,
        _completed: Mapping[str, MetadataSyncStepResult],
        *,
        request: MetadataSyncRequest,
        connection: ChannelTalkCredentialsRecord,
    ) -> MetadataSyncStepResult:
        synced = 0
        memberships: list[ChannelTalkGroupManagerMembership] = []

        async for page in self._iter_pages(
            lambda since: self.client.list_groups(
                access_key=connection.access_key or "",
                access_secret=connection.access_secret or "",
                since=since,
            )
        ):
            payloads = self._with_channel_id(page.groups, request.tenant_id)
            if payloads:
                stored = await self._store_and_commit(
                    self.store.bulk_upsert_groups,
                    payloads,
                    error_message="Failed to persist Channel Talk group metadata",
                )
                synced += len(stored)
                memberships.extend(self._collect_group_memberships(payloads, request.tenant_id))

        return MetadataSyncStepResult(
            synced_count=synced,
            artifacts={"memberships": tuple(memberships)},
        )

    async def _sync_group_memberships(
        self,
        completed: Mapping[str, MetadataSyncStepResult],
        request: MetadataSyncRequest,
    ) -> MetadataSyncStepResult:
        memberships = self._extract_memberships(dict(completed))
        stored = await self._store_and_commit(
            self.store.replace_group_managers,
            channel_id=request.tenant_id,
            memberships=memberships,
            error_message="Failed to replace Channel Talk group-manager memberships",
        )
        return MetadataSyncStepResult(synced_count=len(stored))

    async def _load_connection(
        self,
        request: MetadataSyncRequest,
    ) -> ChannelTalkCredentialsRecord:
        try:
            record = await run_in_threadpool(self.store.get_connection)
        except ChannelTalkError:
            raise
        except Exception as exc:
            raise ChannelTalkPersistenceError(
                "Failed to load Channel Talk credentials"
            ) from exc
        if record is None:
            raise ChannelTalkValidationError("Channel Talk credentials are not installed")
        if record.channel_id != request.tenant_id:
            raise ChannelTalkConflictError(
                "Stored Channel Talk credentials do not match the requested channel",
            )
        return record

    @staticmethod
    async def _iter_pages(
        fetch_page: Callable[[str | None], Awaitable[ChannelTalkMetadataPageT]],
    ) -> AsyncIterator[ChannelTalkMetadataPageT]:
        since: str | None = None

        while True:
            page = await fetch_page(since)
            yield page

            next_page_token = page.next_page_token
            if not next_page_token or next_page_token == since:
                break
            since = next_page_token

    @staticmethod
    def _with_channel_id(
        payloads: list[ChannelTalkMetadataT],
        channel_id: str,
    ) -> list[ChannelTalkMetadataT]:
        return [
            payload.model_copy(update={"channel_id": channel_id})
            for payload in payloads
        ]

    @staticmethod
    def _collect_group_memberships(
        groups: list[ChannelTalkGroupMetadata],
        tenant_id: str,
    ) -> tuple[ChannelTalkGroupManagerMembership, ...]:
        memberships: list[ChannelTalkGroupManagerMembership] = []
        for group in groups:
            memberships.extend(group.to_memberships(tenant_id))
        return tuple(memberships)

    @staticmethod
    def _extract_memberships(
        completed: dict[str, MetadataSyncStepResult],
    ) -> tuple[ChannelTalkGroupManagerMembership, ...]:
        group_step = completed.get("groups")
        if group_step is None:
            return ()

        raw_memberships = group_step.artifacts.get("memberships", ())
        return tuple(
            ChannelTalkGroupManagerMembership.model_validate(item)
            for item in raw_memberships
        )

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
