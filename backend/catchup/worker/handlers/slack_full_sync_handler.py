from __future__ import annotations

from catchup.connectors.slack.factory import create_slack_ingestion_service
from catchup.connectors.slack.sync_audit import (
    emit_channel_completed,
    emit_channel_failed,
    emit_channel_requeued,
    emit_channel_started,
    emit_job_completed,
    emit_job_failed,
    emit_job_started,
)
from catchup.sync.common.protocols import IngestionHandlerProtocol
from catchup.sync.common.schemas import SyncEventContext


class SlackSyncHandler(IngestionHandlerProtocol):
    connector = "slack"
    sync_type = "full"

    async def _get_service(self, scope_id: str, cache: dict[str, object]):
        cached = cache.get(scope_id)
        if cached is not None:
            return cached

        # 순환 import 방지를 위해 런타임 시점에 SessionLocal을 로드한다.
        from catchup.db.engine import SessionLocal

        with SessionLocal() as db:
            service = await create_slack_ingestion_service(db, scope_id)
        cache[scope_id] = service
        return service

    async def handle(
        self,
        *,
        context: SyncEventContext,
        service_cache: dict[str, object],
    ) -> dict[str, int | bool]:
        service = await self._get_service(context.scope_id, service_cache)

        from catchup.db.engine import SessionLocal

        with SessionLocal() as db:
            result = await service.sync_channel_messages(
                channel_id=context.target_id,
                channel_name=context.target_name,
                sync_from=(
                    str(context.metadata.get("sync_from"))
                    if context.metadata.get("sync_from") is not None
                    else None
                ),
                db=db,
                skip_delete=True,
            )
        return {
            "synced": int(result.get("synced", 0)),
            "errors": int(result.get("errors", 0)),
            "skipped": bool(result.get("skipped", False)),
        }

    async def on_job_started(
        self,
        *,
        context: SyncEventContext,
        total_targets: int,
    ) -> None:
        emit_job_started(
            job_id=context.job_id,
            team_id=context.scope_id,
            total_channels=total_targets,
            sync_type=context.sync_type,
        )

    async def on_target_started(
        self,
        *,
        context: SyncEventContext,
    ) -> None:
        emit_channel_started(
            job_id=context.job_id,
            team_id=context.scope_id,
            channel_id=context.target_id,
            channel_name=context.target_name,
            attempt=context.attempt,
            sync_type=context.sync_type,
        )

    async def on_target_requeued(
        self,
        *,
        context: SyncEventContext,
        next_attempt: int,
        error_summary: str,
    ) -> None:
        _ = error_summary
        emit_channel_requeued(
            job_id=context.job_id,
            team_id=context.scope_id,
            channel_id=context.target_id,
            channel_name=context.target_name,
            attempt=next_attempt,
            delay_seconds=0.0,
            sync_type=context.sync_type,
        )

    async def on_target_failed(
        self,
        *,
        context: SyncEventContext,
        next_attempt: int,
        error_summary: str,
        retryable: bool,
    ) -> None:
        emit_channel_failed(
            job_id=context.job_id,
            team_id=context.scope_id,
            channel_id=context.target_id,
            channel_name=context.target_name,
            failure_reason="max_retries_exceeded",
            error_summary=error_summary,
            attempt=next_attempt,
            retryable=retryable,
            sync_type=context.sync_type,
        )

    async def on_target_completed(
        self,
        *,
        context: SyncEventContext,
        result: dict[str, int | bool],
    ) -> None:
        emit_channel_completed(
            job_id=context.job_id,
            team_id=context.scope_id,
            channel_id=context.target_id,
            channel_name=context.target_name,
            synced_count=int(result.get("synced", 0)),
            error_count=int(result.get("errors", 0)),
            skipped=bool(result.get("skipped", False)),
            sync_type=context.sync_type,
        )

    async def on_job_completed(
        self,
        *,
        context: SyncEventContext,
        total_targets: int,
        completed_targets: int,
        failed_targets: int,
        requeued_targets: int,
    ) -> None:
        emit_job_completed(
            job_id=context.job_id,
            team_id=context.scope_id,
            total_channels=total_targets,
            completed_channels=completed_targets,
            failed_channels=failed_targets,
            requeued_channels=requeued_targets,
            total_synced_messages=0,
            sync_type=context.sync_type,
        )

    async def on_job_failed(
        self,
        *,
        context: SyncEventContext,
        total_targets: int,
        failed_targets: int,
    ) -> None:
        emit_job_failed(
            job_id=context.job_id,
            team_id=context.scope_id,
            failure_reason="event_failures_remaining",
            error_summary=f"failed_events={failed_targets}, total_events={total_targets}",
            sync_type=context.sync_type,
        )
