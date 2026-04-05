from fastapi import FastAPI
from fastapi import Request
from fastapi import status
from fastapi.responses import JSONResponse

from catchup.sync.common.exceptions import BaseSyncException
from catchup.sync.common.exceptions import SyncConnectorException
from catchup.sync.common.exceptions import SyncInternalException
from catchup.sync.common.exceptions import SyncRequestException


def _get_sync_error_status_code(
    exc: BaseSyncException,
) -> int:
    if isinstance(exc, SyncRequestException):
        return status.HTTP_400_BAD_REQUEST

    if isinstance(exc, SyncConnectorException):
        return status.HTTP_400_BAD_REQUEST

    if isinstance(exc, SyncInternalException):
        return status.HTTP_500_INTERNAL_SERVER_ERROR

    return status.HTTP_500_INTERNAL_SERVER_ERROR


def register_sync_exception_handlers(
    app: FastAPI,
) -> None:
    @app.exception_handler(BaseSyncException)
    async def handle_sync_error(
        _request: Request,
        exc: BaseSyncException,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=_get_sync_error_status_code(exc),
            content=exc.to_detail(),
        )
