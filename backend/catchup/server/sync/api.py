from __future__ import annotations

from collections.abc import Awaitable
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from catchup.auth.dependencies import require_admin_user
from catchup.configs.config import settings
from catchup.db.dependencies import get_db
from catchup.db.models import SyncConnector
from catchup.server.sync.schemas import (
    FullSyncRequest,
    SyncAcceptedResponse,
    SyncErrorResponse,
    SyncJobSnapshotResponse,
    SyncRecordGapResponse,
    SyncRecordRetryRequest,
    SyncRecordRetryResponse,
    SyncStatusResponse,
    SyncTargetsResponse,
)
from catchup.sync.common.schemas import FullSyncDispatchRequest, SyncDispatchResult
from catchup.sync.common.exceptions import SyncAPIError, SyncRequestError
from catchup.sync.repair.record_repair_service import get_record_repair_service
from catchup.sync.dispatch_service import SyncDispatchService
from catchup.sync.query_service import get_sync_query_service
from catchup.sync.status_stream.service import get_sync_status_stream_service
from catchup.server.sync.dependencies import get_sync_dispatch_service_dependency

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/sync",
    tags=["sync-runtime"],
    dependencies=[Depends(require_admin_user)],
)


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
    sync_request: FullSyncRequest,
    request: Request,
    db: Session = Depends(get_db),
    dispatch_service: SyncDispatchService = Depends(get_sync_dispatch_service_dependency),
):
    dispatch_request = sync_request.to_dispatch_request(
        default_sync_days=settings.DEFAULT_SYNC_DAYS,
    )

    return await _execute_full_sync_dispatch(
        connector=sync_request.connector,
        dispatch_request=dispatch_request,
        dispatch_call=dispatch_service.dispatch_full_sync(
            db=db,
            connector=sync_request.connector,
            request=dispatch_request,
            base_url=str(request.base_url),
        ),
    )


@router.get(
    "/targets",
    response_model=SyncTargetsResponse,
    responses={
        status.HTTP_400_BAD_REQUEST: {"model": SyncErrorResponse},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": SyncErrorResponse},
    },
)
async def list_sync_targets(
    connector: SyncConnector = Query(..., description="sync connector"),
    scope_id: str = Query(..., description="connector scope id"),
):
    query_service = get_sync_query_service()

    try:
        result = await query_service.list_targets(
            connector=connector,
            scope_id=scope_id,
        )
        return SyncTargetsResponse.from_targets_result(result)
    except SyncAPIError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=exc.to_detail(
                connector=connector,
                scope_id=scope_id,
            ),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_build_error_detail(
                code="invalid_request",
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
    "/status",
    response_model=SyncStatusResponse,
    responses={status.HTTP_404_NOT_FOUND: {"model": SyncErrorResponse}},
)
async def get_scope_sync_status(
    connector: SyncConnector = Query(..., description="sync connector"),
    scope_id: str = Query(..., description="connector scope id"),
):
    query_service = get_sync_query_service()
    status_result = query_service.get_scope_latest_full_status(
        connector=connector,
        scope_id=scope_id,
    )

    if status_result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_build_error_detail(
                code="not_found",
                message=f"sync status not found: connector={connector}, scope_id={scope_id}",
                connector=connector,
                scope_id=scope_id,
            ),
        )

    return SyncStatusResponse.from_scope_status_result(status_result)


@router.get(
    "/records/gaps",
    response_model=SyncRecordGapResponse,
    responses={
        status.HTTP_400_BAD_REQUEST: {"model": SyncErrorResponse},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": SyncErrorResponse},
    },
)
async def get_record_gaps(
    connector: SyncConnector = Query(..., description="sync connector"),
    scope_id: str = Query(..., description="connector scope id"),
    target_id: str = Query(..., description="sync target id"),
    sync_days: int | None = Query(
        default=None,
        ge=1,
        description="collection period in days; if omitted connector default is used",
    ),
):
    repair_service = get_record_repair_service()

    try:
        return await repair_service.get_record_gaps(
            connector=connector,
            scope_id=scope_id,
            target_id=target_id,
            sync_days=sync_days,
        )
    except SyncRequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_build_error_detail(
                code=exc.code,
                message=exc.message,
                connector=connector,
                scope_id=scope_id,
                metadata={
                    "target_id": target_id,
                    "sync_days": sync_days,
                    **exc.metadata,
                },
            ),
        ) from exc
    except SyncAPIError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=exc.to_detail(
                connector=connector,
                scope_id=scope_id,
            ),
        ) from exc
    except Exception as exc:
        logger.error(
            "[SYNC][RECORDS][GAPS][API] Request failed: connector=%s, scope_id=%s, target_id=%s, sync_days=%s, error=%s",
            connector,
            scope_id,
            target_id,
            sync_days,
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_build_error_detail(
                code="internal_error",
                message="sync record gap request failed",
                connector=connector,
                scope_id=scope_id,
                metadata={
                    "target_id": target_id,
                    "sync_days": sync_days,
                },
            ),
        ) from exc


@router.post(
    "/records/retry",
    response_model=SyncRecordRetryResponse,
    responses={
        status.HTTP_400_BAD_REQUEST: {"model": SyncErrorResponse},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": SyncErrorResponse},
    },
)
async def retry_records(
    retry_request: SyncRecordRetryRequest,
):
    repair_service = get_record_repair_service()

    try:
        return await repair_service.retry_records(
            request=retry_request,
        )
    except SyncRequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_build_error_detail(
                code=exc.code,
                message=exc.message,
                connector=retry_request.connector,
                scope_id=retry_request.scope_id,
                metadata={
                    "target_id": retry_request.target_id,
                    "sync_days": retry_request.sync_days,
                    **exc.metadata,
                },
            ),
        ) from exc
    except SyncAPIError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=exc.to_detail(
                connector=retry_request.connector,
                scope_id=retry_request.scope_id,
            ),
        ) from exc
    except Exception as exc:
        logger.error(
            "[SYNC][RECORDS][RETRY][API] Request failed: connector=%s, scope_id=%s, target_id=%s, sync_days=%s, error=%s",
            retry_request.connector,
            retry_request.scope_id,
            retry_request.target_id,
            retry_request.sync_days,
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_build_error_detail(
                code="internal_error",
                message="sync record retry request failed",
                connector=retry_request.connector,
                scope_id=retry_request.scope_id,
                metadata={
                    "target_id": retry_request.target_id,
                    "sync_days": retry_request.sync_days,
                },
            ),
        ) from exc


@router.get(
    "/jobs/{job_id}",
    response_model=SyncJobSnapshotResponse,
    responses={status.HTTP_404_NOT_FOUND: {"model": SyncErrorResponse}},
)
async def get_job_snapshot(
    job_id: str,
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

    return SyncJobSnapshotResponse.from_snapshot_result(snapshot)


@router.get(
    "/jobs/{job_id}/stream",
    responses={status.HTTP_404_NOT_FOUND: {"model": SyncErrorResponse}},
)
async def stream_job_events(
    job_id: str,
):
    query_service = get_sync_query_service()
    stream_service = get_sync_status_stream_service()
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
        stream_service.stream_job_events_sse(
            snapshot=SyncJobSnapshotResponse.from_snapshot_result(
                first_snapshot
            ).model_dump(mode="json"),
            heartbeat_seconds=settings.SYNC_SSE_HEARTBEAT_SECONDS,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
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


def _build_dispatch_metadata(
    dispatch_request: FullSyncDispatchRequest,
) -> dict[str, object]:
    return {
        "target_count": len(dispatch_request.target_ids or []),
        "trigger": dispatch_request.trigger.value,
        "sync_from_ts": dispatch_request.sync_from_ts,
    }


async def _execute_full_sync_dispatch(
    *,
    connector: SyncConnector,
    dispatch_request: FullSyncDispatchRequest,
    dispatch_call: Awaitable[SyncDispatchResult],
) -> SyncAcceptedResponse:
    scope_id = dispatch_request.scope_id
    dispatch_metadata = _build_dispatch_metadata(dispatch_request)

    try:
        result = await dispatch_call
        return SyncAcceptedResponse.from_dispatch_result(result)
    except SyncRequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_build_error_detail(
                code=exc.code,
                message=exc.message,
                connector=connector,
                scope_id=scope_id,
                metadata={
                    **dispatch_metadata,
                    **exc.metadata,
                },
            ),
        ) from exc
    except SyncAPIError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=exc.to_detail(
                connector=connector,
                scope_id=scope_id,
            ),
        ) from exc
    except Exception as exc:
        logger.error(
            "[SYNC][FULL][API] Dispatch failed: connector=%s, scope_id=%s, target_count=%s, trigger=%s, sync_from_ts=%s, error=%s",
            connector,
            scope_id,
            dispatch_metadata["target_count"],
            dispatch_metadata["trigger"],
            dispatch_metadata["sync_from_ts"],
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_build_error_detail(
                code="internal_error",
                message="sync full request failed",
                connector=connector,
                scope_id=scope_id,
                metadata=dispatch_metadata,
            ),
        ) from exc
