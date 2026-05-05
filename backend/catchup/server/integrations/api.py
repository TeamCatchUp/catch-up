from __future__ import annotations

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Query
from fastapi import status

from catchup.auth.dependencies import require_admin_user
from catchup.connector_core.adapters.connection_status import ConnectionStatusAdapter
from catchup.connector_core.application.connection_status import (
    ConnectionStatusApplication,
)
from catchup.connector_core.ports.connection_status import ConnectionStatus
from catchup.db.models import SourceType
from catchup.mapping.user_source_mapping_models import MappingStatusResponse
from catchup.mapping.user_source_mapping_models import UserSourceMappingRefreshResponse
from catchup.mapping.user_source_mapping_models import UserSourceMappingResponse
from catchup.mapping.user_source_mapping_service import UserSourceMappingApplication

connection_status_application = ConnectionStatusApplication(
    provider=ConnectionStatusAdapter(),
)
user_source_mapping_application = UserSourceMappingApplication()

router = APIRouter(
    prefix="/api/v1/integrations",
    tags=["integrations"],
    dependencies=[Depends(require_admin_user)],
)


@router.post(
    "/user-source-mapping/refresh",
    response_model=UserSourceMappingRefreshResponse,
)
def refresh_user_source_mapping_endpoint():
    return user_source_mapping_application.refresh_user_source_mappings()


@router.get(
    "/user-source-mapping",
    response_model=UserSourceMappingResponse,
)
def get_user_source_mapping(
    filter: SourceType | None = Query(None, description="jira, slack, github, confluence, channel_talk"),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=100),
):
    return user_source_mapping_application.list_user_source_mappings(
        source_type_filter=filter,
        page=page,
        size=size,
    )


@router.get(
    "/user-source-mapping/status",
    response_model=MappingStatusResponse,
)
def get_mapping_status():
    return user_source_mapping_application.get_mapping_status()


@router.get(
    "/{vendor}/connection-status",
    response_model=ConnectionStatus,
)
def get_connection_status(
    vendor: str,
):
    response = connection_status_application.get_status(vendor=vendor)
    if response is not None:
        return response

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=(
            "vendor must be one of: github, slack, atlassian, jira, confluence, channel_talk"
        ),
    )
