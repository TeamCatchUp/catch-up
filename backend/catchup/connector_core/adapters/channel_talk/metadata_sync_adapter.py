from __future__ import annotations

from collections.abc import Callable
from collections.abc import Mapping
from functools import partial
from typing import Any

from fastapi.concurrency import run_in_threadpool

from catchup.connector_core.ports.metadata_sync import MetadataSyncPlan
from catchup.connector_core.ports.metadata_sync import MetadataSyncRequest
from catchup.connector_core.ports.metadata_sync import MetadataSyncStep
from catchup.connector_core.ports.metadata_sync import MetadataSyncStepResult
from catchup.connectors.channel_talk.client import ChannelTalkApiClient
from catchup.connectors.channel_talk.exceptions import ChannelTalkConflictError
from catchup.connectors.channel_talk.exceptions import ChannelTalkError
from catchup.connectors.channel_talk.exceptions import ChannelTalkPersistenceError
from catchup.connectors.channel_talk.exceptions import ChannelTalkValidationError
from catchup.connectors.channel_talk.schemas import ChannelTalkChannel
from catchup.connectors.channel_talk.schemas import ChannelTalkCredentialsRecord
from catchup.connectors.channel_talk.schemas import ChannelTalkGroupManagerMembership
from catchup.connectors.channel_talk.schemas import ChannelTalkGroupMetadata
from catchup.connectors.channel_talk.schemas import ChannelTalkManagerMetadata


class ChannelTalkMetadataStore:
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
        client: ChannelTalkApiClient | None = None,
    ) -> None:
        self.store = store
        self.client = client or ChannelTalkApiClient()

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
        since: str | None = None

        while True:
            page = await self.client.list_managers(
                access_key=connection.access_key or "",
                access_secret=connection.access_secret or "",
                since=since,
            )
            payloads = [
                manager.model_copy(update={"channel_id": request.tenant_id})
                for manager in page.managers
            ]
            if payloads:
                stored = await self._store_and_commit(
                    self.store.bulk_upsert_managers,
                    payloads,
                    error_message="Failed to persist Channel Talk manager metadata",
                )
                synced += len(stored)

            if not page.next_page_token or page.next_page_token == since:
                break
            since = page.next_page_token

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
        since: str | None = None

        while True:
            page = await self.client.list_groups(
                access_key=connection.access_key or "",
                access_secret=connection.access_secret or "",
                since=since,
            )
            payloads = [
                group.model_copy(update={"channel_id": request.tenant_id})
                for group in page.groups
            ]
            if payloads:
                stored = await self._store_and_commit(
                    self.store.bulk_upsert_groups,
                    payloads,
                    error_message="Failed to persist Channel Talk group metadata",
                )
                synced += len(stored)
                memberships.extend(self._collect_group_memberships(payloads, request.tenant_id))

            if not page.next_page_token or page.next_page_token == since:
                break
            since = page.next_page_token

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
