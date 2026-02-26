import logging

from sqlalchemy.orm import Session

from catchup.connectors.atlassian.token_manager import AtlassianTokenManager
from catchup.connectors.confluence.client import ConfluenceApiClient
from catchup.connectors.jira.client import JiraApiClient

logger = logging.getLogger(__name__)

class AtlassianClientFactory:
    """
    Atlassian product별 API 클라이언트 팩토리

    TokenManager로 유효한 access_token을 확보한 뒤,
    product에 맞는 클라이언트를 생성하여 반환한다.
    """

    def __init__(self, token_manager: AtlassianTokenManager):
        self.token_manager = token_manager

    async def create_jira_client(
        self, db: Session, cloud_id: str
    ) -> JiraApiClient:
        """Jira API 클라이언트 생성."""
        access_token = await self.token_manager.resolve_access_token_by_cloud_id(
            db, cloud_id
        )
        logger.info("[ATLASSIAN][FACTORY] Created JiraApiClient: cloud_id=%s", cloud_id)
        return JiraApiClient(cloud_id=cloud_id, access_token=access_token)

    async def create_confluence_client(
        self, db: Session, cloud_id: str
    ) -> ConfluenceApiClient:
        """Confluence API 클라이언트 생성."""
        access_token = await self.token_manager.resolve_access_token_by_cloud_id(
            db, cloud_id
        )
        logger.info("[ATLASSIAN][FACTORY] Created ConfluenceApiClient: cloud_id=%s", cloud_id)
        return ConfluenceApiClient(cloud_id=cloud_id, access_token=access_token)