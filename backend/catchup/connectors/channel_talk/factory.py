from __future__ import annotations

from sqlalchemy.orm import Session

from catchup.connector_core.adapters.channel_talk import ChannelTalkCredentialsStore
from catchup.connector_core.adapters.channel_talk import (
    ChannelTalkDocumentCredentialsStore,
)
from catchup.connectors.channel_talk.core.client import ChannelTalkCoreApiClient
from catchup.connectors.channel_talk.document_space.client import (
    ChannelTalkDocumentsApiClient,
)
from catchup.connectors.channel_talk.service import ChannelTalkCredentialsService
from catchup.connectors.channel_talk.service import (
    ChannelTalkDocumentCredentialsService,
)
from catchup.db.channel_talk import ChannelTalkCredentialsRepository
from catchup.db.channel_talk import ChannelTalkDocumentCredentialsRepository


def create_channel_talk_credentials_service(
    *,
    db: Session,
    client: ChannelTalkCoreApiClient | None = None,
    store: ChannelTalkCredentialsStore | None = None,
) -> ChannelTalkCredentialsService:
    return ChannelTalkCredentialsService(
        store=store or ChannelTalkCredentialsRepository(db),
        client=client,
    )


def create_channel_talk_document_credentials_service(
    *,
    db: Session,
    client: ChannelTalkDocumentsApiClient | None = None,
    store: ChannelTalkDocumentCredentialsStore | None = None,
) -> ChannelTalkDocumentCredentialsService:
    return ChannelTalkDocumentCredentialsService(
        store=store or ChannelTalkDocumentCredentialsRepository(db),
        client=client,
    )
