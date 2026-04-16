from __future__ import annotations

import structlog

from fastapi import APIRouter, Depends, HTTPException, Query, status

from catchup.audit.actions import SyncTriggerAction
from catchup.audit.metadata import FullSyncTriggerMetadata
from catchup.audit.utils import audit_log
from catchup.auth.dependencies import require_admin_user
from catchup.configs.config import settings
from catchup.db.models import SyncConnector
from catchup.server.sync.schemas import (
    FullSyncRequest,
    SlackIncrementalRecoveryResponse,
    SyncAcceptedResponse,
    SyncErrorResponse,
    SyncJobSnapshotResponse,
    SyncRecordGapResponse,
    SyncRecordRetryRequest,
    SyncRecordRetryResponse,
    SyncStatusResponse,
    SyncTargetsResponse,
)
from catchup.sync.common.exceptions import BaseSyncException, SyncRequestException
from catchup.sync.full.service import get_full_sync_service
from catchup.sync.repair.slack_incremental_recovery_service import get_slack_incremental_recovery_service
from catchup.sync.repair.record_repair_service import get_record_repair_service
from catchup.sync.query_service import get_sync_query_service

logger = structlog.get_logger(__name__)

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
@audit_log(
    SyncTriggerAction.FULL_SYNC_REQUEST,
    metadata_factory=FullSyncTriggerMetadata.from_audit,
)
async def dispatch_full_sync(
    sync_request: FullSyncRequest,
):
    full_sync_service = get_full_sync_service()

    dispatch_request = sync_request.to_dispatch_request(
        default_sync_days=settings.DEFAULT_SYNC_DAYS,
    )

    dispatch_result = await full_sync_service.dispatch(
        connector=sync_request.connector,
        request=dispatch_request,
    )
    return SyncAcceptedResponse.from_dispatch_result(dispatch_result)


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
    except BaseSyncException:
        raise
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
    status_result = await query_service.get_scope_latest_full_status_async(
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
    event_id: str = Query(..., description="sync event id"),
):
    repair_service = get_record_repair_service()

    try:
        return await repair_service.get_record_gaps(
            event_id=event_id,
        )
    except SyncRequestException as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_build_error_detail(
                code=exc.code,
                message=exc.message,
                metadata={
                    "event_id": event_id,
                    **exc.metadata,
                },
            ),
        ) from exc
    except BaseSyncException:
        raise
    except Exception as exc:
        logger.error(
            "[SYNC][RECORDS][GAPS][API] Request failed: event_id=%s, error=%s",
            event_id,
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_build_error_detail(
                code="internal_error",
                message="sync record gap request failed",
                metadata={
                    "event_id": event_id,
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
    except SyncRequestException as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_build_error_detail(
                code=exc.code,
                message=exc.message,
                metadata={
                    "event_id": retry_request.event_id,
                    **exc.metadata,
                },
            ),
        ) from exc
    except BaseSyncException:
        raise
    except Exception as exc:
        logger.error(
            "[SYNC][RECORDS][RETRY][API] Request failed: event_id=%s, error=%s",
            retry_request.event_id,
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_build_error_detail(
                code="internal_error",
                message="sync record retry request failed",
                metadata={
                    "event_id": retry_request.event_id,
                },
            ),
        ) from exc


@router.post(
    "/slack/incremental-recovery",
    response_model=SlackIncrementalRecoveryResponse,
    responses={
        status.HTTP_400_BAD_REQUEST: {"model": SyncErrorResponse},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": SyncErrorResponse},
    },
)
async def recover_slack_incremental_records(
):
    recovery_service = get_slack_incremental_recovery_service()

    try:
        return await recovery_service.recover()
    except SyncRequestException as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_build_error_detail(
                code=exc.code,
                message=exc.message,
                connector=SyncConnector.SLACK,
                metadata=exc.metadata,
            ),
        ) from exc
    except BaseSyncException:
        raise
    except Exception as exc:
        logger.error(
            "[SYNC][SLACK][INCREMENTAL_RECOVERY][API] Request failed: error=%s",
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_build_error_detail(
                code="internal_error",
                message="slack incremental recovery request failed",
                connector=SyncConnector.SLACK,
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
    snapshot = await query_service.get_job_snapshot_async(job_id)

    if snapshot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_build_error_detail(
                code="not_found",
                message=f"sync job not found: {job_id}",
            ),
        )

    return SyncJobSnapshotResponse.from_snapshot_result(snapshot)


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
