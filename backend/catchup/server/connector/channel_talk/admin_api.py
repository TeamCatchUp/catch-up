from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter
from fastapi import Depends

from catchup.auth.dependencies import require_admin_user
from catchup.connectors.channel_talk.schemas import ChannelTalkConnectRequest
from catchup.connectors.channel_talk.schemas import ChannelTalkCredentialsStatus
from catchup.connectors.channel_talk.schemas import ChannelTalkUninstallResult
from catchup.connectors.channel_talk.service import ChannelTalkCredentialsService
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
    service: Annotated[ChannelTalkCredentialsService, Depends(get_channel_talk_service)],
):
    result = await service.connect(request=connect_request)
    return _build_connect_response(result)


@router.get(
    "/credentials",
    response_model=ChannelTalkStatusResponse,
)
async def get_channel_talk_credentials(
    service: Annotated[ChannelTalkCredentialsService, Depends(get_channel_talk_service)],
):
    result = await service.get_status()
    return _build_status_response(result)


@router.delete(
    "/credentials",
    response_model=ChannelTalkUninstallResponse,
)
async def delete_channel_talk_credentials(
    service: Annotated[ChannelTalkCredentialsService, Depends(get_channel_talk_service)],
):
    result = await service.uninstall()
    return _build_uninstall_response(result)


# Review item 4: service 반환 타입을 그대로 사용해 Any/_read_value 기반 동적 응답 구성을 제거한다.
def _build_connect_response(result: ChannelTalkCredentialsStatus) -> ChannelTalkConnectResponse:
    return ChannelTalkConnectResponse(
        installed=result.installed,
        channel_id=result.channel_id,
        channel_name=result.channel_name,
        credential_last_verified_at=_stringify_datetime(result.credential_last_verified_at),
        webhook_token_configured=result.webhook_token_configured,
        status_reason=None,
        status="connected",
        message="Channel Talk credentials saved.",
    )


def _build_status_response(result: ChannelTalkCredentialsStatus) -> ChannelTalkStatusResponse:
    return ChannelTalkStatusResponse(
        installed=result.installed,
        channel_id=result.channel_id,
        channel_name=result.channel_name,
        credential_last_verified_at=_stringify_datetime(result.credential_last_verified_at),
        webhook_token_configured=result.webhook_token_configured,
        status_reason=None,
    )


def _build_uninstall_response(result: ChannelTalkUninstallResult) -> ChannelTalkUninstallResponse:
    if result.removed:
        return ChannelTalkUninstallResponse(
            status="success",
            message="Channel Talk credentials removed.",
            installed=False,
        )

    return ChannelTalkUninstallResponse(
        status="not_found",
        message="Channel Talk credentials were not installed.",
        installed=False,
    )


def _stringify_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()
