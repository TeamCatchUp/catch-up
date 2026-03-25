from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from collections.abc import Callable

from catchup.db.models import SyncConnector
from catchup.sync.query.providers import list_confluence_targets
from catchup.sync.query.providers import list_github_targets
from catchup.sync.query.providers import list_jira_targets
from catchup.sync.query.providers import list_slack_targets
from catchup.sync.query.types import SyncTargetsResult

TargetLoader = Callable[..., Awaitable[SyncTargetsResult]]


class SyncTargetListingService:
    def __init__(
        self,
        *,
        providers: dict[SyncConnector, TargetLoader] | None = None,
    ) -> None:
        self._providers = providers or {
            SyncConnector.GITHUB: list_github_targets,
            SyncConnector.JIRA: list_jira_targets,
            SyncConnector.CONFLUENCE: list_confluence_targets,
            SyncConnector.SLACK: list_slack_targets,
        }
        self._inflight_targets: dict[
            tuple[SyncConnector, str],
            asyncio.Task[SyncTargetsResult],
        ] = {}
        self._inflight_targets_lock = asyncio.Lock()

    async def list_targets(
        self,
        *,
        connector: SyncConnector,
        scope_id: str,
    ) -> SyncTargetsResult:
        key = (connector, scope_id)

        async with self._inflight_targets_lock:
            task = self._inflight_targets.get(key)
            if task is None:
                task = asyncio.create_task(
                    self._list_targets_realtime(
                        connector=connector,
                        scope_id=scope_id,
                    )
                )
                self._inflight_targets[key] = task

        try:
            return await task
        finally:
            if task.done():
                async with self._inflight_targets_lock:
                    if self._inflight_targets.get(key) is task:
                        self._inflight_targets.pop(key, None)

    async def _list_targets_realtime(
        self,
        *,
        connector: SyncConnector,
        scope_id: str,
    ) -> SyncTargetsResult:
        loader = self._providers.get(connector)
        if loader is None:
            raise ValueError(f"unsupported connector for target listing: {connector}")
        return await loader(scope_id=scope_id)
