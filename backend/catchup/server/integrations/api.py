from __future__ import annotations

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import status

from catchup.auth.dependencies import require_admin_user
from catchup.connector_core.adapters.connection_status import ConnectionStatusAdapter
from catchup.connector_core.application.connection_status import (
    ConnectionStatusApplication,
)
from catchup.connector_core.ports.connection_status import ConnectionStatus

connection_status_application = ConnectionStatusApplication(
    provider=ConnectionStatusAdapter(),
)

router = APIRouter(
    prefix="/api/v1/integrations",
    tags=["integrations"],
    dependencies=[Depends(require_admin_user)],
)


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
