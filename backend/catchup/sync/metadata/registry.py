from __future__ import annotations

from collections.abc import Awaitable
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import structlog
from sqlalchemy.orm import Session

from catchup.connectors.atlassian.oauth_client import AtlassianOAuthClient
from catchup.connectors.atlassian.token_manager import AtlassianTokenManager
from catchup.db.atlassian import oauth_repository as atlassian_crud
from catchup.db.channel_talk import ChannelTalkDocumentMetadataRepository
from catchup.db.channel_talk import ChannelTalkMetadataRepository
from catchup.db.engine import SessionLocal
from catchup.db.models import SyncConnector
from catchup.sync.metadata.channel_talk import ChannelTalkMetadataStore
from catchup.sync.metadata.channel_talk import ChannelTalkMetadataSyncService
from catchup.sync.metadata.channel_talk_documents import (
    ChannelTalkDocumentMetadataStore,
)
from catchup.sync.metadata.channel_talk_documents import (
    ChannelTalkDocumentMetadataSyncService,
)
from catchup.sync.metadata.confluence_service import ConfluenceMetadataService
from catchup.sync.metadata.jira_service import create_jira_metadata_service
from catchup.sync.metadata.schemas import MetadataSyncRequest
from catchup.sync.metadata.slack_service import create_slack_metadata_service

logger = structlog.get_logger(__name__)

MetadataSyncRunner = Callable[[MetadataSyncRequest], Awaitable[Any]]


@dataclass(frozen=True)
class MetadataSyncRegistration:
    connector: SyncConnector
    runner: MetadataSyncRunner


class MetadataSyncRegistry:
    """Connector metadata capability registry."""

    def __init__(self) -> None:
        self._registrations: dict[SyncConnector, MetadataSyncRunner] = {}

    def register(
        self,
        connector: SyncConnector,
        runner: MetadataSyncRunner,
    ) -> None:
        self._registrations[connector] = runner

    async def run(self, request: MetadataSyncRequest) -> Any:
        try:
            runner = self._registrations[request.connector]
        except KeyError as exc:
            raise KeyError(
                f"Metadata sync is not registered for connector={request.connector}"
            ) from exc
        return await runner(request)


def create_channel_talk_metadata_service(
    *,
    db: Session,
    store: ChannelTalkMetadataStore | None = None,
) -> ChannelTalkMetadataSyncService:
    return ChannelTalkMetadataSyncService(
        store=store or ChannelTalkMetadataRepository(db),
    )


def create_channel_talk_document_metadata_service(
    *,
    db: Session,
    store: ChannelTalkDocumentMetadataStore | None = None,
) -> ChannelTalkDocumentMetadataSyncService:
    return ChannelTalkDocumentMetadataSyncService(
        store=store or ChannelTalkDocumentMetadataRepository(db),
    )


async def run_slack_metadata_sync(team_id: str) -> None:
    logger.info("slack_metadata_sync_started", team_id=team_id)

    try:
        service = await create_slack_metadata_service(team_id)
        await service.sync_metadata()
        logger.info("slack_metadata_sync_completed", team_id=team_id)
    except Exception:
        logger.error(
            "slack_metadata_sync_failed",
            team_id=team_id,
            exc_info=True,
        )


async def run_jira_metadata_sync(cloud_id: str) -> None:
    logger.info("jira_metadata_sync_started", cloud_id=cloud_id)

    try:
        service = await create_jira_metadata_service(cloud_id=cloud_id)
        await service.sync_metadata()
        logger.info("jira_metadata_sync_completed", cloud_id=cloud_id)
    except Exception:
        logger.error(
            "jira_metadata_sync_failed",
            cloud_id=cloud_id,
            exc_info=True,
        )


async def run_confluence_metadata_sync(cloud_id: str) -> None:
    logger.info("confluence_metadata_sync_started", cloud_id=cloud_id)

    try:
        token_manager = AtlassianTokenManager(
            oauth_client=AtlassianOAuthClient(),
            oauth_repository=atlassian_crud,
        )
        service = ConfluenceMetadataService(token_manager)
        await service.sync_all(cloud_id)
        logger.info("confluence_metadata_sync_completed", cloud_id=cloud_id)
    except Exception:
        logger.error(
            "confluence_metadata_sync_failed",
            cloud_id=cloud_id,
            exc_info=True,
        )


async def run_channel_talk_metadata_sync(channel_id: str) -> None:
    with SessionLocal() as db:
        service = create_channel_talk_metadata_service(db=db)
        try:
            await service.sync_target(channel_id)
        except Exception:
            logger.exception(
                "channel_talk_metadata_sync_failed",
                channel_id=channel_id,
            )


async def run_channel_talk_document_metadata_sync(
    channel_id: str,
    space_id: str | None = None,
) -> None:
    with SessionLocal() as db:
        service = create_channel_talk_document_metadata_service(db=db)
        try:
            if space_id:
                await service.sync_space(channel_id, space_id)
            else:
                await service.sync_target(channel_id)
        except Exception:
            logger.exception(
                "channel_talk_document_metadata_sync_failed",
                channel_id=channel_id,
                space_id=space_id,
            )
