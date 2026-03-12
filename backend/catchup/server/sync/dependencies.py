from __future__ import annotations

import logging

from fastapi import HTTPException, status

from catchup.sync.common.exceptions import SyncAPIError
from catchup.sync.dispatch_service import (
    SyncDispatchService,
    get_sync_dispatch_service,
)

logger = logging.getLogger(__name__)


def get_sync_dispatch_service_dependency() -> SyncDispatchService:
    try:
        return get_sync_dispatch_service()
    except SyncAPIError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=exc.to_detail(),
        ) from exc
    except Exception as exc:
        logger.error(
            "[SYNC][DISPATCH][API] Service initialization failed: error=%s",
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "internal_error",
                "message": "sync dispatch service initialization failed",
            },
        ) from exc
