from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from catchup.connectors.channel_talk.factory import (
    create_channel_talk_credentials_service,
)
from catchup.connectors.channel_talk.service import ChannelTalkCredentialsService
from catchup.db.dependencies import get_db


def get_channel_talk_service(
    db: Annotated[Session, Depends(get_db)],
) -> ChannelTalkCredentialsService:
    return create_channel_talk_credentials_service(db=db)
