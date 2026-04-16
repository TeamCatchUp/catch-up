from __future__ import annotations

from sqlalchemy.orm import Session

from catchup.connectors.channel_talk.client import ChannelTalkApiClient
from catchup.connectors.channel_talk.service import ChannelTalkCredentialsService
from catchup.connectors.channel_talk.service import ChannelTalkCredentialsStore
from catchup.db.channel_talk.repository import ChannelTalkCredentialsRepository


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
