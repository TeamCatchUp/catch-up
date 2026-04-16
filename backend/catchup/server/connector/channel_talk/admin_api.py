from __future__ import annotations

from datetime import datetime
from typing import Annotated
from typing import Any

from fastapi import APIRouter
from fastapi import Depends

from catchup.auth.dependencies import require_admin_user
from catchup.connectors.channel_talk.schemas import ChannelTalkConnectRequest
from catchup.server.connector.channel_talk.dependencies import get_channel_talk_service
from catchup.server.connector.channel_talk.schemas import ChannelTalkConnectResponse
from catchup.server.connector.channel_talk.schemas import ChannelTalkStatusResponse
from catchup.server.connector.channel_talk.schemas import ChannelTalkUninstallResponse

router = APIRouter(
    prefix="/api/v1/admin/connector/channel-talk",
    tags=["channel-talk"],
    dependencies=[Depends(require_admin_user)],
)


@router.post(
    "/credentials",
    response_model=ChannelTalkConnectResponse,
)
async def upsert_channel_talk_credentials(
    connect_request: ChannelTalkConnectRequest,
    service: Annotated[Any, Depends(get_channel_talk_service)],
):
    result = await service.connect(request=connect_request)
    return _build_connect_response(result)


@router.get(
    "/credentials",
    response_model=ChannelTalkStatusResponse,
)
async def get_channel_talk_credentials(
    service: Annotated[Any, Depends(get_channel_talk_service)],
):
    result = await service.get_status()
    return _build_status_response(result)


@router.delete(
    "/credentials",
    response_model=ChannelTalkUninstallResponse
)
async def delete_channel_talk_credentials(
    service: Annotated[Any, Depends(get_channel_talk_service)],
):
    result = await service.uninstall()
    return _build_uninstall_response(result)


def _build_connect_response(result: Any) -> ChannelTalkConnectResponse:
    return ChannelTalkConnectResponse(
        **_build_status_payload(result, installed_default=True),
        status=str(_read_value(result, "status", "connected") or "connected"),
        message=str(
            _read_value(
                result,
                "message",
                "Channel Talk credentials saved.",
            )
            or "Channel Talk credentials saved."
        ),
    )


def _build_status_response(result: Any) -> ChannelTalkStatusResponse:
    return ChannelTalkStatusResponse(**_build_status_payload(result))


def _build_status_payload(
    result: Any,
    *,
    installed_default: bool = False,
) -> dict[str, Any]:
    installed = _read_bool(
        result,
        "installed",
        "is_installed",
        "connected",
        default=installed_default,
    )
    webhook_configured = _read_bool(
        result,
        "webhook_token_configured",
        "has_webhook_token",
        default=bool(_read_value(result, "webhook_token")),
    )

    return {
        "installed": installed,
        "channel_id": _stringify(_read_value(result, "channel_id", "scope_id")),
        "channel_name": _stringify(_read_value(result, "channel_name", "name")),
        "credential_last_verified_at": _stringify_datetime(
            _read_value(
                result,
                "credential_last_verified_at",
                "last_verified_at",
                "verified_at",
            )
        ),
        "webhook_token_configured": webhook_configured,
        "status_reason": _stringify(_read_value(result, "status_reason", "reason")),
    }


def _build_uninstall_response(result: Any) -> ChannelTalkUninstallResponse:
    removed = _read_bool(result, "removed", default=False)
    response_status = str(
        _read_value(result, "status", "success" if removed else "not_found")
        or ("success" if removed else "not_found")
    )
    message = str(
        _read_value(
            result,
            "message",
            "Channel Talk credentials removed." if removed
            else "Channel Talk credentials were not installed.",
        )
        or ""
    )

    return ChannelTalkUninstallResponse(
        status=response_status,
        message=message,
        installed=False,
    )


def _read_value(result: Any, *names: str) -> Any:
    if isinstance(result, dict):
        for name in names:
            if name in result:
                return result[name]
        return None

    for name in names:
        if hasattr(result, name):
            return getattr(result, name)
    return None


def _read_bool(result: Any, *names: str, default: bool = False) -> bool:
    value = _read_value(result, *names)
    if value is None:
        return default
    return bool(value)


def _stringify(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _stringify_datetime(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)
