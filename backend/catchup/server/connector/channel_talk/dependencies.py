from __future__ import annotations

from typing import Any

import structlog
from fastapi import Depends
from sqlalchemy.orm import Session

from catchup.connectors.channel_talk.exceptions import ChannelTalkPersistenceError
from catchup.db.dependencies import get_db

logger = structlog.get_logger(__name__)


def get_channel_talk_service(
    db: Session = Depends(get_db),
) -> Any:
    try:
        from catchup.connectors.channel_talk.factory import (
            create_channel_talk_credentials_service,
        )
    except ModuleNotFoundError as exc:
        logger.error("channel_talk_integration_module_missing", exc_info=True)
        raise ChannelTalkPersistenceError(
            "Channel Talk integration modules are not available.",
            code="channel_talk_service_unavailable",
        ) from exc

    return create_channel_talk_credentials_service(db=db)
