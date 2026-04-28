from __future__ import annotations

from sqlalchemy.orm import Session

from catchup.connector_core.adapters.channel_talk import ChannelTalkCredentialsStore
from catchup.connector_core.adapters.channel_talk import (
    ChannelTalkDocumentCredentialsStore,
)
from catchup.connector_core.adapters.channel_talk import (
    ChannelTalkDocumentMetadataStore,
)
from catchup.connector_core.adapters.channel_talk import ChannelTalkMetadataStore
from catchup.connectors.channel_talk.client import ChannelTalkApiClient
from catchup.connectors.channel_talk.documents_client import (
    ChannelTalkDocumentsApiClient,
)
from catchup.connectors.channel_talk.service import ChannelTalkCredentialsService
from catchup.connectors.channel_talk.service import (
    ChannelTalkDocumentCredentialsService,
)
from catchup.connectors.channel_talk.service import (
    ChannelTalkDocumentMetadataSyncService,
)
from catchup.connectors.channel_talk.service import ChannelTalkMetadataSyncService
from catchup.db.channel_talk import ChannelTalkCredentialsRepository
from catchup.db.channel_talk import ChannelTalkDocumentCredentialsRepository
from catchup.db.channel_talk import ChannelTalkDocumentMetadataRepository
from catchup.db.channel_talk import ChannelTalkMetadataRepository


def create_channel_talk_credentials_service(
    *,
    db: Session,
    client: ChannelTalkApiClient | None = None,
    store: ChannelTalkCredentialsStore | None = None,
) -> ChannelTalkCredentialsService:
    return ChannelTalkCredentialsService(
        store=store or ChannelTalkCredentialsRepository(db),
        client=client,
    )


def create_channel_talk_metadata_service(
    *,
    db: Session,
    client: ChannelTalkApiClient | None = None,
    store: ChannelTalkMetadataStore | None = None,
) -> ChannelTalkMetadataSyncService:
    return ChannelTalkMetadataSyncService(
        store=store or ChannelTalkMetadataRepository(db),
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


def create_channel_talk_document_metadata_service(
    *,
    db: Session,
    client: ChannelTalkDocumentsApiClient | None = None,
    store: ChannelTalkDocumentMetadataStore | None = None,
) -> ChannelTalkDocumentMetadataSyncService:
    return ChannelTalkDocumentMetadataSyncService(
        store=store or ChannelTalkDocumentMetadataRepository(db),
        client=client,
    )
