from __future__ import annotations

from collections.abc import Awaitable
from collections.abc import Callable
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from catchup.connectors.channel_talk.factory import (
    create_channel_talk_credentials_service,
)
from catchup.connectors.channel_talk.factory import (
    create_channel_talk_document_credentials_service,
)
from catchup.connectors.channel_talk.service import ChannelTalkCredentialsService
from catchup.connectors.channel_talk.service import (
    ChannelTalkDocumentCredentialsService,
)
from catchup.db.dependencies import get_db
from catchup.sync.metadata.registry import run_channel_talk_document_metadata_sync
from catchup.sync.metadata.registry import run_channel_talk_metadata_sync

ChannelTalkMetadataTaskRunner = Callable[[str], Awaitable[None]]
ChannelTalkDocumentMetadataTaskRunner = Callable[[str, str | None], Awaitable[None]]


def get_channel_talk_service(
    db: Annotated[Session, Depends(get_db)],
) -> ChannelTalkCredentialsService:
    return create_channel_talk_credentials_service(db=db)


def get_channel_talk_document_service(
    db: Annotated[Session, Depends(get_db)],
) -> ChannelTalkDocumentCredentialsService:
    return create_channel_talk_document_credentials_service(db=db)


def get_channel_talk_metadata_task_runner() -> ChannelTalkMetadataTaskRunner:
    return run_channel_talk_metadata_sync


def get_channel_talk_document_metadata_task_runner() -> ChannelTalkDocumentMetadataTaskRunner:
    return run_channel_talk_document_metadata_sync
