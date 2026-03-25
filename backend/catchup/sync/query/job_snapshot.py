from __future__ import annotations

from datetime import datetime
from datetime import timezone

from sqlalchemy import select

from catchup.db.engine import SessionLocal
from catchup.db.models import SyncConnector
from catchup.db.models import SyncEventStatus
from catchup.db.models import SyncJob
from catchup.db.models import SyncType
from catchup.db.sync import SyncEventSummary
from catchup.db.sync import get_job
from catchup.db.sync import list_events_by_job
from catchup.db.sync import summarize_events_by_job
from catchup.sync.query.types import SyncJobSnapshotResult
from catchup.sync.query.types import SyncJobSummaryResult
from catchup.sync.query.types import SyncJobTargetSnapshotResult
from catchup.sync.query.types import SyncScopeStatusResult


class SyncJobSnapshotQuery:
    def _to_iso(self, value: datetime | None) -> str | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc).isoformat()
        return value.astimezone(timezone.utc).isoformat()

    def _summarize_events(self, events) -> dict[str, int]:
        queued_targets = sum(
            1
            for event in events
            if event.status in {SyncEventStatus.PENDING, SyncEventStatus.RETRYING}
        )
        processing_targets = sum(
            1 for event in events if event.status == SyncEventStatus.IN_PROGRESS
        )
        completed_targets = sum(
            1 for event in events if event.status == SyncEventStatus.SUCCESS
        )
        failed_targets = sum(
            1 for event in events if event.status == SyncEventStatus.FAILED
        )
        return {
            "total_targets": len(events),
            "queued_targets": queued_targets,
            "processing_targets": processing_targets,
            "completed_targets": completed_targets,
            "failed_targets": failed_targets,
            "requeued_targets": sum(int(event.attempt) for event in events),
        }

    def _build_metrics(self, events) -> dict[str, int]:
        return {
            "embedding_tokens_used": sum(
                int(event.embedding_tokens_used or 0) for event in events
            ),
            "summary_tokens_used": sum(
                int(event.summary_tokens_used or 0) for event in events
            ),
        }

    def _build_last_error(self, events) -> str | None:
        candidates = [
            event
            for event in events
            if event.status == SyncEventStatus.FAILED
            and (event.last_error or event.publish_error)
        ]
        if not candidates:
            return None

        candidates.sort(
            key=lambda event: event.failed_at or event.updated_at or event.requested_at,
            reverse=True,
        )
        return str(candidates[0].last_error or candidates[0].publish_error)

    def _build_job_summary(self, events) -> SyncJobSummaryResult:
        counts = self._summarize_events(events)
        return SyncJobSummaryResult(
            total_targets=counts["total_targets"],
            queued_targets=counts["queued_targets"],
            processing_targets=counts["processing_targets"],
            completed_targets=counts["completed_targets"],
            failed_targets=counts["failed_targets"],
            requeued_targets=counts["requeued_targets"],
            metrics=self._build_metrics(events),
            last_error=self._build_last_error(events),
        )

    def _to_job_summary_result(self, summary: SyncEventSummary) -> SyncJobSummaryResult:
        return SyncJobSummaryResult(
            total_targets=summary.total_targets,
            queued_targets=summary.queued_targets,
            processing_targets=summary.processing_targets,
            completed_targets=summary.completed_targets,
            failed_targets=summary.failed_targets,
            requeued_targets=summary.requeued_targets,
            metrics={
                "embedding_tokens_used": summary.embedding_tokens_used,
                "summary_tokens_used": summary.summary_tokens_used,
            },
            last_error=summary.last_error,
        )

    def _build_job_targets(self, events) -> list[SyncJobTargetSnapshotResult]:
        targets: list[SyncJobTargetSnapshotResult] = []
        for event in events:
            metadata = (
                event.resource_metadata
                if isinstance(event.resource_metadata, dict)
                else {}
            )
            target_id = str(event.resource_id)
            target_name = str(metadata.get("target_name") or target_id).strip() or target_id
            target_metadata = {
                key: metadata[key]
                for key in (
                    "stage",
                    "chunk_index",
                    "chunk_total",
                    "range_start",
                    "range_end",
                    "execution_phase",
                    "expected_count",
                    "synced_count",
                    "error_count",
                    "stored_count",
                    "missing_count",
                    "repair_status",
                    "last_validation_at",
                    "last_repair_at",
                    "skipped_count",
                )
                if key in metadata
            }
            targets.append(
                SyncJobTargetSnapshotResult(
                    target_id=target_id,
                    target_name=target_name,
                    status=event.status,
                    metadata=target_metadata,
                )
            )
        return targets

    def get_job_snapshot(self, job_id: str) -> SyncJobSnapshotResult | None:
        with SessionLocal() as db:
            job = get_job(db, job_id)
            if job is None:
                return None

            events = list_events_by_job(db, job_id=job_id, limit=None)
            summary = self._build_job_summary(events)
            targets = self._build_job_targets(events)
            return SyncJobSnapshotResult(
                job_id=job.job_id,
                connector=job.connector,
                sync_type=job.sync_type,
                scope_id=str(job.scope_id),
                status=job.status,
                created_at=self._to_iso(job.created_at) or "",
                started_at=self._to_iso(job.started_at),
                completed_at=self._to_iso(job.succeeded_at or job.failed_at),
                total_targets=summary.total_targets,
                queued_targets=summary.queued_targets,
                processing_targets=summary.processing_targets,
                completed_targets=summary.completed_targets,
                failed_targets=summary.failed_targets,
                requeued_targets=summary.requeued_targets,
                targets=targets,
                metrics=summary.metrics,
                last_error=summary.last_error,
            )

    def get_scope_latest_full_status(
        self,
        *,
        connector: SyncConnector,
        scope_id: str,
    ) -> SyncScopeStatusResult | None:
        with SessionLocal() as db:
            stmt = (
                select(SyncJob)
                .where(
                    SyncJob.connector == connector,
                    SyncJob.scope_id == scope_id,
                    SyncJob.sync_type == SyncType.FULL,
                )
                .order_by(SyncJob.requested_at.desc())
                .limit(1)
            )
            job = db.execute(stmt).scalar_one_or_none()
            if job is None:
                return None

            summary = self._to_job_summary_result(
                summarize_events_by_job(db, job_id=job.job_id)
            )
            return SyncScopeStatusResult(
                job_id=job.job_id,
                connector=job.connector,
                sync_type=job.sync_type,
                scope_id=str(job.scope_id),
                status=job.status,
                requested_at=self._to_iso(job.requested_at) or "",
                started_at=self._to_iso(job.started_at),
                completed_at=self._to_iso(job.succeeded_at or job.failed_at),
                total_targets=summary.total_targets,
                queued_targets=summary.queued_targets,
                processing_targets=summary.processing_targets,
                completed_targets=summary.completed_targets,
                failed_targets=summary.failed_targets,
                requeued_targets=summary.requeued_targets,
                metrics=summary.metrics,
                last_error=summary.last_error,
            )
