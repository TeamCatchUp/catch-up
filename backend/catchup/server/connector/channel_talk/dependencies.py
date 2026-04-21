from __future__ import annotations

from collections.abc import Awaitable
from collections.abc import Callable
from typing import Annotated

import structlog
from fastapi import Depends
from sqlalchemy.orm import Session

from catchup.connectors.channel_talk.factory import (
    create_channel_talk_credentials_service,
)
from catchup.connectors.channel_talk.factory import create_channel_talk_metadata_service
from catchup.connectors.channel_talk.service import ChannelTalkCredentialsService
from catchup.db.dependencies import get_db
from catchup.db.engine import SessionLocal

logger = structlog.get_logger(__name__)

ChannelTalkMetadataTaskRunner = Callable[[str], Awaitable[None]]

def get_channel_talk_service(
    db: Annotated[Session, Depends(get_db)],
) -> ChannelTalkCredentialsService:
    return create_channel_talk_credentials_service(db=db)


async def run_channel_talk_metadata_sync(
    channel_id: str,
) -> None:
    with SessionLocal() as db:
        service = create_channel_talk_metadata_service(db=db)
        try:
            await service.sync_channel(channel_id)
        except Exception:
            logger.exception(
                "channel_talk_metadata_sync_failed",
                channel_id=channel_id,
            )


def get_channel_talk_metadata_task_runner() -> ChannelTalkMetadataTaskRunner:
    return run_channel_talk_metadata_sync
