from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter
from fastapi import BackgroundTasks
from fastapi import Depends

from catchup.auth.dependencies import require_admin_user
from catchup.connectors.channel_talk.schemas.channel_connection import (
    ChannelTalkConnectRequest,
)
from catchup.connectors.channel_talk.schemas.channel_connection import (
    ChannelTalkCredentialsStatus,
)
from catchup.connectors.channel_talk.schemas.channel_connection import (
    ChannelTalkUninstallResult,
)
from catchup.connectors.channel_talk.schemas.channel_metadata import (
    ChannelTalkCurrentChannel,
)
from catchup.connectors.channel_talk.schemas.document_connection import (
    ChannelTalkDocumentConnectRequest,
)
from catchup.connectors.channel_talk.schemas.document_connection import (
    ChannelTalkDocumentCredentialsStatus,
)
from catchup.connectors.channel_talk.schemas.document_connection import (
    ChannelTalkDocumentUninstallResult,
)
from catchup.connectors.channel_talk.service import ChannelTalkCredentialsService
from catchup.connectors.channel_talk.service import (
    ChannelTalkDocumentCredentialsService,
)
from catchup.server.connector.channel_talk.dependencies import (
    ChannelTalkDocumentMetadataTaskRunner,
)
from catchup.server.connector.channel_talk.dependencies import (
    ChannelTalkMetadataTaskRunner,
)
from catchup.server.connector.channel_talk.dependencies import (
    get_channel_talk_document_metadata_task_runner,
)
from catchup.server.connector.channel_talk.dependencies import (
    get_channel_talk_document_service,
)
from catchup.server.connector.channel_talk.dependencies import (
    get_channel_talk_metadata_task_runner,
)
from catchup.server.connector.channel_talk.dependencies import get_channel_talk_service
from catchup.server.connector.channel_talk.schemas import ChannelTalkConnectResponse
from catchup.server.connector.channel_talk.schemas import (
    ChannelTalkDocumentConnectResponse,
)
from catchup.server.connector.channel_talk.schemas import (
    ChannelTalkDocumentStatusResponse,
)
from catchup.server.connector.channel_talk.schemas import (
    ChannelTalkDocumentUninstallResponse,
)
from catchup.server.connector.channel_talk.schemas import (
    ChannelTalkDocumentValidateResponse,
)
from catchup.server.connector.channel_talk.schemas import ChannelTalkStatusResponse
from catchup.server.connector.channel_talk.schemas import ChannelTalkUninstallResponse
from catchup.server.connector.channel_talk.schemas import ChannelTalkValidateResponse

router = APIRouter(
    prefix="/api/v1/admin/connector/channel-talk",
    tags=["channel-talk"],
    dependencies=[Depends(require_admin_user)],
)


@router.post(
    "/credentials/validate",
    response_model=ChannelTalkValidateResponse,
)
async def validate_channel_talk_credentials(
    connect_request: ChannelTalkConnectRequest,
    service: Annotated[ChannelTalkCredentialsService, Depends(get_channel_talk_service)],
):
    result = await service.validate_credentials(request=connect_request)
    return _build_validate_response(
        result,
        webhook_token_configured=bool(connect_request.webhook_token.strip()),
    )


@router.post(
    "/credentials",
    response_model=ChannelTalkConnectResponse,
)
async def upsert_channel_talk_credentials(
    connect_request: ChannelTalkConnectRequest,
    background_tasks: BackgroundTasks,
    service: Annotated[ChannelTalkCredentialsService, Depends(get_channel_talk_service)],
    metadata_task_runner: Annotated[
        ChannelTalkMetadataTaskRunner,
        Depends(get_channel_talk_metadata_task_runner),
    ],
):
    result = await service.connect(request=connect_request)
    if result.installed and result.channel_id:
        background_tasks.add_task(metadata_task_runner, result.channel_id)
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


@router.post(
    "/documents/credentials/validate",
    response_model=ChannelTalkDocumentValidateResponse,
)
async def validate_channel_talk_document_credentials(
    connect_request: ChannelTalkDocumentConnectRequest,
    service: Annotated[
        ChannelTalkDocumentCredentialsService,
        Depends(get_channel_talk_document_service),
    ],
):
    result = await service.validate_connection(request=connect_request)
    return _build_document_validate_response(result)


@router.post(
    "/documents/credentials",
    response_model=ChannelTalkDocumentConnectResponse,
)
async def upsert_channel_talk_document_credentials(
    connect_request: ChannelTalkDocumentConnectRequest,
    background_tasks: BackgroundTasks,
    service: Annotated[
        ChannelTalkDocumentCredentialsService,
        Depends(get_channel_talk_document_service),
    ],
    metadata_task_runner: Annotated[
        ChannelTalkDocumentMetadataTaskRunner,
        Depends(get_channel_talk_document_metadata_task_runner),
    ],
):
    result = await service.connect(request=connect_request)
    if result.installed and result.channel_id:
        background_tasks.add_task(metadata_task_runner, result.channel_id)
    return _build_document_connect_response(result)


@router.get(
    "/documents/credentials",
    response_model=ChannelTalkDocumentStatusResponse,
)
async def get_channel_talk_document_credentials(
    service: Annotated[
        ChannelTalkDocumentCredentialsService,
        Depends(get_channel_talk_document_service),
    ],
):
    result = await service.get_status()
    return _build_document_status_response(result)


@router.delete(
    "/documents/credentials",
    response_model=ChannelTalkDocumentUninstallResponse,
)
async def delete_channel_talk_document_credentials(
    service: Annotated[
        ChannelTalkDocumentCredentialsService,
        Depends(get_channel_talk_document_service),
    ],
):
    result = await service.uninstall()
    return _build_document_uninstall_response(result)


def _build_validate_response(
    result: ChannelTalkCurrentChannel,
    *,
    webhook_token_configured: bool,
) -> ChannelTalkValidateResponse:
    return ChannelTalkValidateResponse(
        channel_id=result.channel_id,
        channel_name=result.channel_name,
        manager_id=result.manager.id if result.manager else None,
        manager_name=result.manager.name if result.manager else None,
        webhook_token_configured=webhook_token_configured,
    )


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


def _build_document_validate_response(
    result: ChannelTalkDocumentCredentialsStatus,
) -> ChannelTalkDocumentValidateResponse:
    return ChannelTalkDocumentValidateResponse(
        channel_id=result.channel_id or "",
        space_id=result.space_id or "",
        space_name=result.space_name or "",
        association_status=_stringify_association_status(result) or "",
    )


def _build_document_connect_response(
    result: ChannelTalkDocumentCredentialsStatus,
) -> ChannelTalkDocumentConnectResponse:
    return ChannelTalkDocumentConnectResponse(
        installed=result.installed,
        channel_id=result.channel_id,
        space_id=result.space_id,
        space_name=result.space_name,
        credential_last_verified_at=_stringify_datetime(result.credential_last_verified_at),
        association_status=_stringify_association_status(result),
        status_reason=None,
        status="connected",
        message="Channel Talk Documents credentials saved.",
    )


def _build_document_status_response(
    result: ChannelTalkDocumentCredentialsStatus,
) -> ChannelTalkDocumentStatusResponse:
    return ChannelTalkDocumentStatusResponse(
        installed=result.installed,
        channel_id=result.channel_id,
        space_id=result.space_id,
        space_name=result.space_name,
        credential_last_verified_at=_stringify_datetime(result.credential_last_verified_at),
        association_status=_stringify_association_status(result),
        status_reason=None,
    )


def _build_document_uninstall_response(
    result: ChannelTalkDocumentUninstallResult,
) -> ChannelTalkDocumentUninstallResponse:
    if result.removed:
        return ChannelTalkDocumentUninstallResponse(
            status="success",
            message="Channel Talk Documents credentials removed.",
            installed=False,
        )

    return ChannelTalkDocumentUninstallResponse(
        status="not_found",
        message="Channel Talk Documents credentials were not installed.",
        installed=False,
    )


def _stringify_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def _stringify_association_status(
    result: ChannelTalkDocumentCredentialsStatus,
) -> str | None:
    if result.association_status is None:
        return None
    return str(result.association_status)
