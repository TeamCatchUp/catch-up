from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from catchup.auth.dependencies import require_admin_user
from catchup.configs.config import settings
from catchup.db.dependencies import get_db
from catchup.db.models import SyncConnector, User
from catchup.server.sync.schemas import (
    SyncAcceptedResponse,
    SyncErrorResponse,
    SyncFullRequest,
    SyncIncrementalRequest,
    SyncJobSnapshotResponse,
    SyncTargetItem,
    SyncTargetsResponse,
)
from catchup.sync.contracts import (
    FullSyncDispatchRequest,
    IncrementalSyncDispatchRequest,
    SyncDispatchResult,
)
from catchup.sync.dispatch_service import get_sync_dispatch_service
from catchup.sync.query_service import (
    SyncJobSnapshotResult,
    SyncTargetsResult,
    get_sync_query_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/sync", tags=["sync-runtime"])

@router.post(
    "/full",
    response_model=SyncAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        status.HTTP_400_BAD_REQUEST: {"model": SyncErrorResponse},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": SyncErrorResponse},
    },
)
async def dispatch_full_sync(
    sync_request: SyncFullRequest,
    request: Request,
    db: Session = Depends(get_db),
    _admin_user: User = Depends(require_admin_user),
):
    dispatch_service = get_sync_dispatch_service()

    try:
        result = await dispatch_service.dispatch_full_sync(
            db=db,
            connector=sync_request.connector,
            command=FullSyncDispatchRequest(
                scope_id=sync_request.scope_id,
                target_ids=sync_request.target_ids,
                sync_days=sync_request.sync_days,
                trigger="api",
            ),
            base_url=str(request.base_url),
        )
        return _to_sync_accepted_response(result)

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_build_error_detail(
                code="invalid_request",
                message=str(exc),
                connector=sync_request.connector,
                scope_id=sync_request.scope_id,
            ),
        )

    except Exception as exc:
        detail = getattr(exc, "detail", None)
        if isinstance(detail, dict):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=_build_error_detail(
                    code="invalid_request",
                    message="connector validation failed",
                    connector=sync_request.connector,
                    scope_id=sync_request.scope_id,
                    metadata=detail,
                ),
            )

        logger.error(
            "[SYNC][FULL SYNC][API] Dispatch failed: connector=%s, scope_id=%s, error=%s",
            sync_request.connector,
            sync_request.scope_id,
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_build_error_detail(
                code="internal_error",
                message="sync full request failed",
                connector=sync_request.connector,
                scope_id=sync_request.scope_id,
            ),
        )


@router.post(
    "/incremental",
    response_model=SyncAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        status.HTTP_400_BAD_REQUEST: {"model": SyncErrorResponse},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": SyncErrorResponse},
    },
)
async def dispatch_incremental_sync(
    sync_request: SyncIncrementalRequest,
    request: Request,
    db: Session = Depends(get_db),
    _admin_user: User = Depends(require_admin_user),
):
    dispatch_service = get_sync_dispatch_service()

    try:
        result = await dispatch_service.dispatch_incremental_sync(
            db=db,
            connector=sync_request.connector,
            command=IncrementalSyncDispatchRequest(
                scope_id=sync_request.scope_id,
                target_ids=sync_request.target_ids,
                trigger="api",
            ),
            base_url=str(request.base_url),
        )
        return _to_sync_accepted_response(result)

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_build_error_detail(
                code="invalid_request",
                message=str(exc),
                connector=sync_request.connector,
                scope_id=sync_request.scope_id,
            ),
        )

    except Exception as exc:
        detail = getattr(exc, "detail", None)
        if isinstance(detail, dict):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=_build_error_detail(
                    code="invalid_request",
                    message="connector validation failed",
                    connector=sync_request.connector,
                    scope_id=sync_request.scope_id,
                    metadata=detail,
                ),
            )

        logger.error(
            "[SYNC][INCREMENTAL SYNC][API] Dispatch failed: connector=%s, scope_id=%s, error=%s",
            sync_request.connector,
            sync_request.scope_id,
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_build_error_detail(
                code="internal_error",
                message="sync incremental request failed",
                connector=sync_request.connector,
                scope_id=sync_request.scope_id,
            ),
        )


@router.get(
    "/targets",
    response_model=SyncTargetsResponse,
    responses={
        status.HTTP_501_NOT_IMPLEMENTED: {"model": SyncErrorResponse},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": SyncErrorResponse},
    },
)
async def list_sync_targets(
    connector: SyncConnector = Query(..., description="sync connector"),
    scope_id: str = Query(..., description="connector scope id"),
    _admin_user: User = Depends(require_admin_user),
):
    query_service = get_sync_query_service()

    try:
        result = await query_service.list_targets(
            connector=connector,
            scope_id=scope_id,
        )
        return _to_target_response(result)

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=_build_error_detail(
                code="not_implemented",
                message=str(exc),
                connector=connector,
                scope_id=scope_id,
            ),
        )

    except Exception as exc:
        logger.error(
            "[SYNC][TARGETS][API] Query failed: connector=%s, scope_id=%s, error=%s",
            connector,
            scope_id,
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_build_error_detail(
                code="internal_error",
                message="sync targets request failed",
                connector=connector,
                scope_id=scope_id,
            ),
        )


@router.get(
    "/jobs/{job_id}",
    response_model=SyncJobSnapshotResponse,
    responses={status.HTTP_404_NOT_FOUND: {"model": SyncErrorResponse}},
)
async def get_job_snapshot(
    job_id: str,
    _admin_user: User = Depends(require_admin_user),
):
    query_service = get_sync_query_service()
    snapshot = query_service.get_job_snapshot(job_id)

    if snapshot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_build_error_detail(
                code="not_found",
                message=f"sync job not found: {job_id}",
            ),
        )

    return _to_job_snapshot_response(snapshot)


@router.get(
    "/jobs/{job_id}/stream",
    responses={status.HTTP_404_NOT_FOUND: {"model": SyncErrorResponse}},
)
async def stream_job_events(
    job_id: str,
    from_sequence: int = Query(1, ge=1),
    _admin_user: User = Depends(require_admin_user),
):
    query_service = get_sync_query_service()
    first_snapshot = query_service.get_job_snapshot(job_id)

    if first_snapshot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_build_error_detail(
                code="not_found",
                message=f"sync job not found: {job_id}",
            ),
        )

    return StreamingResponse(
        query_service.stream_job_events_sse(
            job_id=job_id,
            from_sequence=from_sequence,
            heartbeat_seconds=settings.SYNC_SSE_HEARTBEAT_SECONDS,
        ),
        media_type="text/event-stream",
    )


def _to_sync_accepted_response(result: SyncDispatchResult) -> SyncAcceptedResponse:
    return SyncAcceptedResponse(
        status=result.status,
        connector=result.connector,
        scope_id=result.scope_id,
        job_id=result.job_id,
        event_ids=result.event_ids,
        total_targets=result.total_targets,
        queued_targets=result.queued_targets,
        dropped_targets=result.dropped_targets,
        dropped_events=result.dropped_events,
        message=result.message,
        snapshot_url=result.snapshot_url,
        stream_url=result.stream_url,
    )


def _to_job_snapshot_response(result: SyncJobSnapshotResult) -> SyncJobSnapshotResponse:
    return SyncJobSnapshotResponse(
        job_id=result.job_id,
        connector=result.connector,
        sync_type=result.sync_type,
        scope_id=result.scope_id,
        status=result.status,
        created_at=result.created_at,
        started_at=result.started_at,
        completed_at=result.completed_at,
        total_targets=result.total_targets,
        queued_targets=result.queued_targets,
        processing_targets=result.processing_targets,
        completed_targets=result.completed_targets,
        failed_targets=result.failed_targets,
        requeued_targets=result.requeued_targets,
        metrics=result.metrics,
        last_error=result.last_error,
    )


def _to_target_response(result: SyncTargetsResult) -> SyncTargetsResponse:
    return SyncTargetsResponse(
        connector=result.connector,
        scope_id=result.scope_id,
        total_targets=result.total_targets,
        targets=[
            SyncTargetItem(
                target_id=item.target_id,
                display_name=item.display_name,
                target_type=item.target_type,
                is_accessible=item.is_accessible,
                metadata=item.metadata,
            )
            for item in result.targets
        ],
    )


def _build_error_detail(
    *,
    code: str,
    message: str,
    connector: SyncConnector | None = None,
    scope_id: str | None = None,
    metadata: dict[str, object] | None = None,
) -> dict[str, object]:
    detail: dict[str, object] = {
        "code": code,
        "message": message,
    }

    if connector is not None:
        detail["connector"] = connector
    if scope_id is not None:
        detail["scope_id"] = scope_id
    if metadata:
        detail["metadata"] = metadata

    return detail
