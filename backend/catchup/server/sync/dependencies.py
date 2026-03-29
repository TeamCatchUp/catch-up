from __future__ import annotations

from fastapi import HTTPException, status
import structlog

from catchup.server.sync.schemas import FullSyncRequest
from catchup.sync.common.exceptions import SyncAPIError
from catchup.sync.full.service import (
    FullSyncService,
    get_full_sync_service,
)

logger = structlog.get_logger(__name__)


def get_full_sync_service_dependency(
    sync_request: FullSyncRequest,
) -> FullSyncService:
    try:
        return get_full_sync_service()
    except SyncAPIError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=exc.to_detail(
                connector=sync_request.connector,
                scope_id=sync_request.scope_id,
            ),
        ) from exc
    except Exception as exc:
        logger.error(
            "full_sync_service_dependency_failed",
            connector=sync_request.connector.value,
            scope_id=sync_request.scope_id,
            error=str(exc),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "internal_error",
                "message": "full sync service initialization failed",
                "connector": sync_request.connector,
                "scope_id": sync_request.scope_id,
            },
        ) from exc
