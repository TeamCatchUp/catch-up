import logging
from types import ModuleType

from sqlalchemy.orm import Session

from catchup.connectors.atlassian.exceptions import (
    AtlassianTokenNotFoundError
)
from catchup.connectors.atlassian.oauth_client import AtlassianOAuthClient
from catchup.db.models import AtlassianOAuthToken

logger = logging.getLogger(__name__)

class AtlassianTokenManager:
    def __init__(
        self,
        oauth_client: AtlassianOAuthClient,
        oauth_repository: ModuleType,
    ):
        self.oauth_client = oauth_client
        self.oauth_repository = oauth_repository
    
    async def resolve_access_token(
        self, db: Session, token: AtlassianOAuthToken
    ) -> str:
        return token.access_token
    
    async def resolve_access_token_by_cloud_id(
        self, db:Session, cloud_id: str
    ) -> str:
        token = self.oauth_repository.get_token_by_cloud_id(db, cloud_id)

        if not token:
            raise AtlassianTokenNotFoundError(cloud_id)
        
        return await self.resolve_access_token(db, token)