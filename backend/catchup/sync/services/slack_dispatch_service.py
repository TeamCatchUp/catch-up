from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy.orm import Session

from catchup.configs.config import settings
from catchup.connectors.slack.factory import create_slack_ingestion_service
from catchup.connectors.slack.sync_audit import emit_job_accepted
from catchup.db.models import SyncConnector
from catchup.db.sync import (
    complete_job_success as complete_db_sync_job_success,
    start_job as start_db_sync_job,
)
from catchup.sync.common.protocols import EventPublisherProtocol
from catchup.sync.common.schemas import (
    FullSyncDispatchCommand,
    IncrementalSyncDispatchCommand,
    SyncDispatchResult,
    SyncStreamTask,
)
from catchup.sync.contracts import ConnectorSyncService
from catchup.sync.event_publisher.redis_stream_publisher import get_event_publisher
from catchup.sync.event_publisher.slack_event_builder import (
    build_full_sync_event_seeds,
    persist_full_sync_job_and_events,
)

logger = logging.getLogger(__name__)

_INCREMENTAL_DISABLED_MESSAGE = "incremental pipeline disabled"


def _build_job_urls(base_url: str | None, job_id: str) -> tuple[str | None, str | None]:
    if not base_url:
        return None, None
    base = base_url.rstrip("/")
    return (
        f"{base}/api/v1/sync/jobs/{job_id}",
        f"{base}/api/v1/sync/jobs/{job_id}/stream",
    )


class SlackSyncDispatchValidationError(Exception):
    """Slack sync dispatch request validation error."""

    def __init__(self, detail: dict[str, object]):
        super().__init__(str(detail))
        self.detail = detail


class SlackConnectorSyncService(ConnectorSyncService):
    connector = SyncConnector.SLACK

    def __init__(self, event_publisher: EventPublisherProtocol):
        self._event_publisher = event_publisher

    def _resolve_full_sync_targets(
        self,
        *,
        team_id: str,
        channels: list[dict[str, str]],
        requested_target_ids: list[str] | None,
    ) -> tuple[list[dict[str, str]], list[str]]:
        if requested_target_ids is None:
            return channels, []

        requested_ids = [item.strip() for item in requested_target_ids if item and item.strip()]
        requested_id_set = set(requested_ids)

        resolved_channels = [
            channel
            for channel in channels
            if (channel.get("id") or "").strip() in requested_id_set
        ]
        resolved_id_set = {(channel.get("id") or "").strip() for channel in resolved_channels}
        invalid_target_ids = [
            target_id for target_id in requested_ids if target_id not in resolved_id_set
        ]

        if not resolved_channels:
            raise SlackSyncDispatchValidationError(
                detail={
                    "team_id": team_id,
                    "message": "no syncable channels matched the requested target_ids",
                    "requested_target_ids": requested_ids,
                }
            )

        return resolved_channels, invalid_target_ids

    async def dispatch_full_sync(
        self,
        *,
        db: Session,
        command: FullSyncDispatchCommand,
        base_url: str | None,
    ) -> SyncDispatchResult:
        team_id = command.scope_id
        requested_channel_ids = command.target_ids
        sync_days = command.sync_days or settings.DEFAULT_SYNC_DAYS

        requested_at = datetime.now(timezone.utc)
        sync_from = str((requested_at - timedelta(days=sync_days)).timestamp())
        job_id = uuid4().hex

        # 대상 조회/분해 책임은 서비스 계층에서 수행한다.
        service = await create_slack_ingestion_service(db, team_id)
        channels = await service.list_syncable_channels()
        resolved_channels, invalid_channel_ids = self._resolve_full_sync_targets(
            team_id=team_id,
            channels=channels,
            requested_target_ids=requested_channel_ids,
        )

        event_seeds = build_full_sync_event_seeds(
            channels=resolved_channels,
            sync_from=sync_from,
        )
        total_targets = len(event_seeds)

        db_event_ids = persist_full_sync_job_and_events(
            db,
            job_id=job_id,
            team_id=team_id,
            requested_at=requested_at,
            event_seeds=event_seeds,
        )

        tasks = [
            SyncStreamTask(
                event_id=event_id,
                job_id=job_id,
                connector="slack",
                sync_type="full",
                scope_id=team_id,
                target_type="channel",
                target_id=seed.channel_id,
                attempt=0,
                max_attempts=seed.max_attempts,
            )
            for event_id, seed in zip(db_event_ids, event_seeds, strict=False)
        ]
        message_ids = await self._event_publisher.publish(tasks=tasks)

        if total_targets == 0:
            started = start_db_sync_job(db, job_id)
            if started:
                complete_db_sync_job_success(db, job_id)

        snapshot_url, stream_url = _build_job_urls(base_url, job_id)
        logger.info(
            "[SLACK][FULL SYNC][DISPATCH SERVICE] Dispatch accepted: team_id=%s, job_id=%s, total_targets=%s, queued_targets=%s, invalid_target_count=%s, sync_days=%s",
            team_id,
            job_id,
            total_targets,
            len(message_ids),
            len(invalid_channel_ids),
            sync_days,
        )
        emit_job_accepted(
            job_id=job_id,
            team_id=team_id,
            total_channels=total_targets,
            queued_channels=len(message_ids),
            sync_type="full",
            dropped_channels=len(invalid_channel_ids),
            dropped_events=max(0, total_targets - len(message_ids)),
            trigger=command.trigger,
        )

        return SyncDispatchResult(
            status="accepted",
            connector=self.connector,
            scope_id=team_id,
            job_id=job_id,
            event_ids=db_event_ids,
            total_targets=total_targets,
            queued_targets=len(message_ids),
            dropped_targets=len(invalid_channel_ids),
            dropped_events=max(0, total_targets - len(message_ids)),
            snapshot_url=snapshot_url,
            stream_url=stream_url,
        )

    async def dispatch_incremental_sync(
        self,
        *,
        db: Session,
        command: IncrementalSyncDispatchCommand,
        base_url: str | None,
    ) -> SyncDispatchResult:
        _ = db
        _ = base_url
        logger.warning(
            "[SLACK][INCREMENTAL SYNC][DISPATCH SERVICE] Incremental dispatch is disabled: scope_id=%s, trigger=%s",
            command.scope_id,
            command.trigger,
        )
        return SyncDispatchResult(
            status="no_events",
            connector=self.connector,
            scope_id=command.scope_id,
            dropped_targets=0,
            dropped_events=0,
            message=_INCREMENTAL_DISABLED_MESSAGE,
        )


_slack_sync_service = SlackConnectorSyncService(event_publisher=get_event_publisher())


def get_slack_connector_sync_service() -> ConnectorSyncService:
    return _slack_sync_service
