from __future__ import annotations

from fastapi.concurrency import run_in_threadpool

from catchup.db.engine import SessionLocal
from catchup.db.models import SyncEventStatus
from catchup.db.models import SyncJobStatus
from catchup.db.models import SyncType
from catchup.db.sync import complete_job_failed
from catchup.db.sync import complete_job_success
from catchup.db.sync import get_job
from catchup.db.sync import summarize_events_by_job
from catchup.sync.common.protocols import IngestionHandlerProtocol
from catchup.sync.common.schemas import FullSyncContext
from catchup.sync.status_stream.schemas import SyncStatusEventType
from catchup.worker.common import build_job_status_event
from catchup.worker.common import publish_status_event
from catchup.worker.schemas import JobFinalizeResult


def _finalize_job_if_done_sync(context: FullSyncContext) -> JobFinalizeResult:
    if context.sync_type != SyncType.FULL:
        return JobFinalizeResult()

    with SessionLocal() as db:
        try:
            job = get_job(db, context.job_id)
            if job is None:
                return JobFinalizeResult()

            if job.status in {SyncJobStatus.SUCCESS, SyncJobStatus.FAILED}:
                return JobFinalizeResult()

            summary = summarize_events_by_job(db, job_id=context.job_id)
            if summary.total_targets == 0:
                return JobFinalizeResult()

            if summary.queued_targets > 0 or summary.processing_targets > 0:
                return JobFinalizeResult()

            if summary.failed_targets == 0:
                if not complete_job_success(db, context.job_id):
                    db.rollback()
                    return JobFinalizeResult()

                db.commit()
                return JobFinalizeResult(
                    finalized=True,
                    status=SyncJobStatus.SUCCESS,
                    total_targets=summary.total_targets,
                    completed_targets=summary.completed_targets,
                    failed_targets=summary.failed_targets,
                    requeued_targets=summary.requeued_targets,
                )

            if not complete_job_failed(db, context.job_id):
                db.rollback()
                return JobFinalizeResult()

            db.commit()
            return JobFinalizeResult(
                finalized=True,
                status=SyncJobStatus.FAILED,
                total_targets=summary.total_targets,
                completed_targets=summary.completed_targets,
                failed_targets=summary.failed_targets,
                requeued_targets=summary.requeued_targets,
            )
        except Exception:
            db.rollback()
            raise


async def _finalize_job_if_done(
    context: FullSyncContext,
    handler: IngestionHandlerProtocol,
) -> None:
    result = await run_in_threadpool(_finalize_job_if_done_sync, context)
    if not result.finalized or result.status is None:
        return

    if result.status == SyncJobStatus.SUCCESS:
        await publish_status_event(
            build_job_status_event(
                context=context,
                event_type=SyncStatusEventType.JOB_COMPLETED,
                status=SyncJobStatus.SUCCESS.value,
                total_targets=result.total_targets,
                completed_targets=result.completed_targets,
                failed_targets=result.failed_targets,
                requeued_targets=result.requeued_targets,
            )
        )
        await handler.on_job_completed(
            context=context,
            total_targets=result.total_targets,
            completed_targets=result.completed_targets,
            failed_targets=result.failed_targets,
            requeued_targets=result.requeued_targets,
        )
        return

    await publish_status_event(
        build_job_status_event(
            context=context,
            event_type=SyncStatusEventType.JOB_FAILED,
            status=SyncJobStatus.FAILED.value,
            total_targets=result.total_targets,
            completed_targets=result.completed_targets,
            failed_targets=result.failed_targets,
            requeued_targets=result.requeued_targets,
        )
    )
    await handler.on_job_failed(
        context=context,
        total_targets=result.total_targets,
        failed_targets=result.failed_targets,
    )
