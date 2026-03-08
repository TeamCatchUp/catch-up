from __future__ import annotations

import asyncio
from typing import Protocol

from sqlalchemy.orm import Session

from catchup.sync.common.schemas import (
    FullSyncDispatchRequest,
    FullSyncResolvedTargets,
    IncrementalSyncDispatchRequest,
    PublishTasksResult,
    SyncDispatchResult,
    SyncEventContext,
    SyncStreamMessage,
    SyncStreamTask,
)


class EventPublisherProtocol(Protocol):
    async def publish(self, *, tasks: list[SyncStreamTask]) -> PublishTasksResult:
        """이벤트 목록을 Stream에 publish 하고 publish 결과를 반환."""
        ...


class WorkerProtocol(Protocol):
    async def run_forever(self, stop_event: asyncio.Event) -> None:
        ...

    async def process(self, message: SyncStreamMessage) -> None:
        ...


class IngestionHandlerProtocol(Protocol):
    connector: str
    sync_type: str

    async def handle(
        self,
        *,
        context: SyncEventContext,
        service_cache: dict[str, object],
    ) -> dict[str, int | bool]:
        ...

    async def on_job_started(
        self,
        *,
        context: SyncEventContext,
        total_targets: int,
    ) -> None:
        ...

    async def on_target_started(
        self,
        *,
        context: SyncEventContext,
    ) -> None:
        ...

    async def on_target_requeued(
        self,
        *,
        context: SyncEventContext,
        next_attempt: int,
        error_summary: str,
    ) -> None:
        ...

    async def on_target_failed(
        self,
        *,
        context: SyncEventContext,
        next_attempt: int,
        error_summary: str,
        retryable: bool,
    ) -> None:
        ...

    async def on_target_completed(
        self,
        *,
        context: SyncEventContext,
        result: dict[str, int | bool],
    ) -> None:
        ...

    async def on_job_completed(
        self,
        *,
        context: SyncEventContext,
        total_targets: int,
        completed_targets: int,
        failed_targets: int,
        requeued_targets: int,
    ) -> None:
        ...

    async def on_job_failed(
        self,
        *,
        context: SyncEventContext,
        total_targets: int,
        failed_targets: int,
    ) -> None:
        ...


class ConnectorSyncServiceProtocol(Protocol):
    async def dispatch_full_sync(
        self,
        *,
        db,
        request: FullSyncDispatchRequest,
        base_url: str | None,
    ) -> SyncDispatchResult:
        ...

    async def dispatch_incremental_sync(
        self,
        *,
        db,
        request: IncrementalSyncDispatchRequest,
        base_url: str | None,
    ) -> SyncDispatchResult:
        ...


class FullSyncTargetResolverProtocol(Protocol):
    async def resolve_full_sync_targets(
        self,
        *,
        db: Session,
        request: FullSyncDispatchRequest,
        sync_from: str,
    ) -> FullSyncResolvedTargets:
        ...
