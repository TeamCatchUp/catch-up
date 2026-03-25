from __future__ import annotations

from fastapi.concurrency import run_in_threadpool

from catchup.db.models import SyncConnector
from catchup.sync.query.job_snapshot import SyncJobSnapshotQuery
from catchup.sync.query.providers import list_confluence_targets
from catchup.sync.query.providers import list_github_targets
from catchup.sync.query.providers import list_jira_targets
from catchup.sync.query.providers import list_slack_targets
from catchup.sync.query.providers.common import build_targets_result
from catchup.sync.query.target_listing import SyncTargetListingService
from catchup.sync.query.types import SyncJobSnapshotResult
from catchup.sync.query.types import SyncJobSummaryResult
from catchup.sync.query.types import SyncJobTargetSnapshotResult
from catchup.sync.query.types import SyncScopeStatusResult
from catchup.sync.query.types import SyncTargetResult
from catchup.sync.query.types import SyncTargetsResult


class SyncQueryService:
    def __init__(self) -> None:
        self._job_snapshot_query = SyncJobSnapshotQuery()
        self._target_listing_service = SyncTargetListingService()
        self._inflight_targets = self._target_listing_service._inflight_targets
        self._inflight_targets_lock = self._target_listing_service._inflight_targets_lock

    def _to_iso(self, value):
        return self._job_snapshot_query._to_iso(value)

    def _summarize_events(self, events):
        return self._job_snapshot_query._summarize_events(events)

    def _build_metrics(self, events):
        return self._job_snapshot_query._build_metrics(events)

    def _build_last_error(self, events):
        return self._job_snapshot_query._build_last_error(events)

    def _build_job_summary(self, events):
        return self._job_snapshot_query._build_job_summary(events)

    def _to_job_summary_result(self, summary):
        return self._job_snapshot_query._to_job_summary_result(summary)

    def _build_job_targets(self, events):
        return self._job_snapshot_query._build_job_targets(events)

    def _build_targets_result(
        self,
        *,
        connector: SyncConnector,
        scope_id: str,
        targets: list[SyncTargetResult],
    ) -> SyncTargetsResult:
        return build_targets_result(
            connector=connector,
            scope_id=scope_id,
            targets=targets,
        )

    async def _list_github_targets(self, *, scope_id: str) -> SyncTargetsResult:
        return await list_github_targets(scope_id=scope_id)

    async def _list_jira_targets(self, *, scope_id: str) -> SyncTargetsResult:
        return await list_jira_targets(scope_id=scope_id)

    async def _list_confluence_targets(self, *, scope_id: str) -> SyncTargetsResult:
        return await list_confluence_targets(scope_id=scope_id)

    async def _list_slack_targets(self, *, scope_id: str) -> SyncTargetsResult:
        return await list_slack_targets(scope_id=scope_id)

    async def _list_targets_realtime(
        self,
        *,
        connector: SyncConnector,
        scope_id: str,
    ) -> SyncTargetsResult:
        return await self._target_listing_service._list_targets_realtime(
            connector=connector,
            scope_id=scope_id,
        )

    def get_job_snapshot(self, job_id: str) -> SyncJobSnapshotResult | None:
        return self._job_snapshot_query.get_job_snapshot(job_id)

    async def get_job_snapshot_async(
        self,
        job_id: str,
    ) -> SyncJobSnapshotResult | None:
        return await run_in_threadpool(self.get_job_snapshot, job_id)

    def get_scope_latest_full_status(
        self,
        *,
        connector: SyncConnector,
        scope_id: str,
    ) -> SyncScopeStatusResult | None:
        return self._job_snapshot_query.get_scope_latest_full_status(
            connector=connector,
            scope_id=scope_id,
        )

    async def get_scope_latest_full_status_async(
        self,
        *,
        connector: SyncConnector,
        scope_id: str,
    ) -> SyncScopeStatusResult | None:
        return await run_in_threadpool(
            self.get_scope_latest_full_status,
            connector=connector,
            scope_id=scope_id,
        )

    async def list_targets(
        self,
        *,
        connector: SyncConnector,
        scope_id: str,
    ) -> SyncTargetsResult:
        return await self._target_listing_service.list_targets(
            connector=connector,
            scope_id=scope_id,
        )


_sync_query_service = SyncQueryService()


def get_sync_query_service() -> SyncQueryService:
    return _sync_query_service


__all__ = [
    "SyncJobSnapshotResult",
    "SyncJobSummaryResult",
    "SyncJobTargetSnapshotResult",
    "SyncQueryService",
    "SyncScopeStatusResult",
    "SyncTargetResult",
    "SyncTargetsResult",
    "get_sync_query_service",
]
