from fastapi import FastAPI

from catchup.server.error_handlers.sync import register_sync_exception_handlers
from catchup.server.error_handlers.user import register_user_exception_handlers


def register_exception_handlers(
    app: FastAPI,
) -> None:
    register_user_exception_handlers(app)
    register_sync_exception_handlers(app)
