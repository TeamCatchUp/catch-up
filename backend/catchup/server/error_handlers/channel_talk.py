from __future__ import annotations

from fastapi import FastAPI
from fastapi import Request
from fastapi.encoders import jsonable_encoder
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from catchup.connectors.channel_talk.exceptions import ChannelTalkError

CHANNEL_TALK_ROUTE_PREFIX = "/api/v1/admin/connector/channel_talk"


def register_channel_talk_exception_handlers(
    app: FastAPI,
) -> None:
    @app.exception_handler(ChannelTalkError)
    async def handle_channel_talk_error(
        _request: Request,
        exc: ChannelTalkError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=int(exc.status_code),
            content={
                "detail": {
                    "code": exc.code,
                    "message": exc.message,
                    "metadata": exc.metadata,
                }
            },
        )

    @app.exception_handler(RequestValidationError)
    async def handle_channel_talk_request_validation_error(
        request: Request,
        exc: RequestValidationError,
    ):
        if not request.url.path.startswith(CHANNEL_TALK_ROUTE_PREFIX):
            return await request_validation_exception_handler(request, exc)

        return JSONResponse(
            status_code=400,
            content={
                "detail": {
                    "code": "invalid_request",
                    "message": _build_validation_message(exc),
                    "metadata": {"errors": jsonable_encoder(exc.errors())},
                }
            },
        )


def _build_validation_message(exc: RequestValidationError) -> str:
    if any(error.get("type") == "json_invalid" for error in exc.errors()):
        return "Invalid JSON body for Channel Talk connect request."
    return "Invalid Channel Talk connect request."
