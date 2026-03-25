from __future__ import annotations

from datetime import datetime
from datetime import timedelta
from datetime import timezone
from uuid import uuid4

import structlog

from catchup.configs.config import settings
from catchup.configs.constants import FULL_SYNC_EVENT_SCHEMA_VERSION
from catchup.db.models import SyncConnector, SyncType
from catchup.sync.common.exceptions import SyncRequestError
from catchup.sync.common.protocols import FullSyncTargetResolverProtocol
from catchup.sync.common.schemas import (
    FullSyncDispatchRequest,
    FullSyncTarget,
    SyncDispatchResult,
    SyncEventSeed,
)
from catchup.sync.services.sync_orchestrator import SyncDispatchOrchestrator

logger = structlog.get_logger()

def _format_epoch_ts(dt: datetime) -> str:
    normalized = dt.astimezone(timezone.utc)
    return f"{normalized.timestamp():.6f}"


def _resolve_sync_from_dt(sync_from_ts: str | None) -> tuple[str, datetime]:
    if sync_from_ts:
        try:
            resolved = datetime.fromtimestamp(float(sync_from_ts), tz=timezone.utc)
        except (TypeError, ValueError) as exc:
            raise SyncRequestError(
                "sync_from_ts is invalid",
                code="invalid_sync_from_ts",
                metadata={"sync_from_ts": sync_from_ts},
            ) from exc
        return sync_from_ts, resolved

    resolved = datetime.now(timezone.utc) - timedelta(days=settings.DEFAULT_SYNC_DAYS)
    return _format_epoch_ts(resolved), resolved


def _next_month_start(dt: datetime) -> datetime:
    normalized = dt.astimezone(timezone.utc)
    if normalized.month == 12:
        return normalized.replace(
            year=normalized.year + 1,
            month=1,
            day=1,
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )
    return normalized.replace(
        month=normalized.month + 1,
        day=1,
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )

def _build_month_ranges(
    *,
    range_start: datetime,
    range_end: datetime,
) -> list[tuple[datetime, datetime]]:
    """
    range_start + range_end을 월 단위의 구간 리스트로 나눔
    """
    normalized_start = range_start.astimezone(timezone.utc)
    normalized_end = range_end.astimezone(timezone.utc)

    if normalized_start >= normalized_end:
        return []

    ranges: list[tuple[datetime, datetime]] = []
    current_start = normalized_start

    while current_start < normalized_end:
        month_boundary = _next_month_start(current_start)
        current_end = min(month_boundary, normalized_end)
        ranges.append((current_start, current_end))
        current_start = current_end

    return ranges

def _resolve_stages(connector: SyncConnector) -> list[str]:
    if connector == SyncConnector.SLACK:
        return ["message"]
    if connector == SyncConnector.JIRA:
        return ["issue"]
    if connector == SyncConnector.GITHUB:
        return ["issue", "pr"]
    if connector == SyncConnector.CONFLUENCE:
        return ["page", "blogpost"]

    raise SyncRequestError(
        "unsupported full sync connector",
        code="unsupported_connector",
        metadata={"connector": connector.value},
    )


def _build_chunk_event_seeds(
    *,
    connector: SyncConnector,
    target: FullSyncTarget,
    sync_from_ts: str,
    sync_from_dt: datetime,
    range_watermark: datetime,
) -> list[SyncEventSeed]:
    seeds: list[SyncEventSeed] = []
    stages = _resolve_stages(connector)

    for stage in stages:
        ranges = _build_month_ranges(
            range_start=sync_from_dt,
            range_end=range_watermark,
        )
        chunk_total = len(ranges)

        for index, (range_start, range_end) in enumerate(ranges, start=1):
            metadata = dict(target.metadata)
            metadata["event_schema_version"] = FULL_SYNC_EVENT_SCHEMA_VERSION

            seeds.append(
                SyncEventSeed(
                    event_id=uuid4().hex,
                    target_type=target.target_type,
                    target_id=target.target_id,
                    target_name=target.target_name,
                    stage=stage,
                    range_start=range_start,
                    range_end=range_end,
                    chunk_index=index,
                    chunk_total=chunk_total,
                    range_watermark=range_watermark,
                    sync_from_ts=sync_from_ts,
                    metadata=metadata,
                    max_attempts=settings.SYNC_JOB_MAX_ATTEMPTS,
                )
            )

        logger.info(
            "full_sync_chunk_seeds_planned",
            connector=connector.value,
            target_id=target.target_id,
            stage=stage,
            chunk_total=chunk_total,
            sync_from_ts=sync_from_ts,
            range_watermark=range_watermark.isoformat(),
        )

    return seeds


class FullSyncDispatchOrchestrator:
    """Full Sync 전용 입력 해석 후 공통 dispatch orchestrator에 위임한다."""

    def __init__(self, orchestrator: SyncDispatchOrchestrator):
        self._orchestrator = orchestrator

    async def dispatch(
        self,
        *,
        connector: SyncConnector,
        request: FullSyncDispatchRequest,
        base_url: str | None,
        resolver: FullSyncTargetResolverProtocol,
    ) -> SyncDispatchResult:
        """
        Target Resolve & Event Seed 생성 -> SyncDispatchOrchestrator에게 위임
        """
        scope_id = request.scope_id.strip()
        if not scope_id:
            raise SyncRequestError("scope_id is required")

        sync_from_ts, sync_from_dt = _resolve_sync_from_dt(request.sync_from_ts)
        range_watermark = datetime.now(timezone.utc)

        if sync_from_dt >= range_watermark:
            raise SyncRequestError(
                "sync_from_ts must be earlier than dispatch time",
                code="invalid_sync_range",
                metadata={
                    "sync_from_ts": sync_from_ts,
                    "range_watermark": range_watermark.isoformat(),
                },
            )
        
        resolved = await resolver.resolve_full_sync_targets(request=request)

        event_seeds: list[SyncEventSeed] = []
        for target in resolved.targets:
            event_seeds.extend(
                _build_chunk_event_seeds(
                    connector=connector,
                    target=target,
                    sync_from_ts=sync_from_ts,
                    sync_from_dt=sync_from_dt,
                    range_watermark=range_watermark,
                )
            )

        logger.info(
            "full_sync_dispatch_planning_completed",
            connector=connector.value,
            scope_id=scope_id,
            target_count=len(resolved.targets),
            event_seed_count=len(event_seeds),
        )

        return await self._orchestrator.dispatch(
            connector=connector,
            sync_type=SyncType.FULL,
            scope_id=scope_id,
            trigger=request.trigger,
            event_seeds=event_seeds,
            base_url=base_url,
            sync_from_ts=sync_from_ts,
        )
