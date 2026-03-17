from fastapi import FastAPI
from fastapi import Request
from fastapi import status
from fastapi.responses import JSONResponse

from catchup.user.exceptions import CannotPromoteDeletedUserError
from catchup.user.exceptions import CannotPromoteInactiveUserError
from catchup.user.exceptions import UserAlreadyAdminError
from catchup.user.exceptions import UserError
from catchup.user.exceptions import UserNotFoundError

def _get_user_error_status_code(
    exc: UserError,
) -> int:
    if isinstance(exc, UserNotFoundError):
        return status.HTTP_404_NOT_FOUND

    if isinstance(
        exc,
        (
            UserAlreadyAdminError,
            CannotPromoteDeletedUserError,
            CannotPromoteInactiveUserError,
        ),
    ):
        return status.HTTP_409_CONFLICT

    return status.HTTP_400_BAD_REQUEST

def register_exception_handlers(
    app: FastAPI,
) -> None:
    @app.exception_handler(UserError)
    async def handle_user_error(
        _request: Request,
        exc: UserError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=_get_user_error_status_code(exc),
            content={
                "code": exc.code,
                "message": exc.message,
                "detail": exc.detail,
            },
        )
