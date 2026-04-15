from fastapi import FastAPI
from fastapi import Request
from fastapi import status
from fastapi.responses import JSONResponse

from catchup.user.exceptions import AdminCountViolationError
from catchup.user.exceptions import CannotDeactivateAdminUserError
from catchup.user.exceptions import CannotDeleteAdminUserError
from catchup.user.exceptions import CannotPromoteDeletedUserError
from catchup.user.exceptions import CannotPromoteInactiveUserError
from catchup.user.exceptions import CannotRevokeDeletedUserError
from catchup.user.exceptions import CannotRevokeInactiveUserError
from catchup.user.exceptions import CannotRevokeOwnAdminRoleError
from catchup.user.exceptions import UserAlreadyAdminError
from catchup.user.exceptions import UserAlreadyDeletedError
from catchup.user.exceptions import UserAlreadyInactiveError
from catchup.user.exceptions import UserAlreadyUserError
from catchup.user.exceptions import UserError
from catchup.user.exceptions import UserNotFoundError


def _get_user_error_status_code(
    exc: UserError,
) -> int:
    if isinstance(exc, UserNotFoundError):
        return status.HTTP_404_NOT_FOUND

    if isinstance(exc, CannotRevokeOwnAdminRoleError):
        return status.HTTP_403_FORBIDDEN

    if isinstance(exc, CannotDeactivateAdminUserError):
        return status.HTTP_403_FORBIDDEN

    if isinstance(exc, CannotDeleteAdminUserError):
        return status.HTTP_403_FORBIDDEN

    if isinstance(
        exc,
        (
            UserAlreadyAdminError,
            UserAlreadyUserError,
            UserAlreadyDeletedError,
            UserAlreadyInactiveError,
            AdminCountViolationError,
            CannotPromoteDeletedUserError,
            CannotPromoteInactiveUserError,
            CannotRevokeDeletedUserError,
            CannotRevokeInactiveUserError,
        ),
    ):
        return status.HTTP_409_CONFLICT

    return status.HTTP_400_BAD_REQUEST


def register_user_exception_handlers(
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
