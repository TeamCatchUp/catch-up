from __future__ import annotations

from sqlalchemy.orm import Session

from catchup.connectors.channel_talk.client import ChannelTalkApiClient
from catchup.connectors.channel_talk.service import ChannelTalkCredentialsService
from catchup.connectors.channel_talk.service import ChannelTalkCredentialsStore
from catchup.connectors.channel_talk.service import ChannelTalkMetadataStore
from catchup.connectors.channel_talk.service import ChannelTalkMetadataSyncService
from catchup.db.channel_talk.repository import ChannelTalkCredentialsRepository
from catchup.db.channel_talk.repository import ChannelTalkMetadataRepository


def create_channel_talk_credentials_service(
    *,
    db: Session,
    client: ChannelTalkApiClient | None = None,
    store: ChannelTalkCredentialsStore | None = None,
) -> ChannelTalkCredentialsService:
    # 기본 DB repository를 한 번만 해석해 두고, 이후 service wiring이 adapter/application 분리 이후에도 동일한 저장소 인스턴스를 재사용하도록 고정한다.
    resolved_store = store or ChannelTalkCredentialsRepository(db)
    return ChannelTalkCredentialsService(
        store=resolved_store,
        client=client,
    )

def create_channel_talk_metadata_service(
    *,
    db: Session,
    client: ChannelTalkApiClient | None = None,
    store: ChannelTalkMetadataStore | None = None,
) -> ChannelTalkMetadataSyncService:
    
    resolved_store = store or ChannelTalkMetadataRepository(db)
    return ChannelTalkMetadataSyncService(
        store=resolved_store,
        client=client,
    )
