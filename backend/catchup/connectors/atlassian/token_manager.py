import logging
from datetime import datetime, timedelta, timezone
from types import ModuleType

from sqlalchemy.orm import Session

from catchup.connectors.atlassian.exceptions import (
    AtlassianTokenExpiredError,
    AtlassianTokenNotFoundError,
)
from catchup.connectors.atlassian.oauth_client import AtlassianOAuthClient
from catchup.db.models import AtlassianOAuthToken

logger = logging.getLogger(__name__)

TOKEN_REFRESH_BUFFER = timedelta(minutes=5)

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
        """
        DB에서 인증객체를 조회하여 Access Token을 반환
        - 만료 기한이 임박한 경우 Refresh 후 DB에 Flush
        """
        if not self._is_token_expired(token):
            return token.access_token

        logger.info(
            "[ATLASSIAN][TOKEN] Refreshing access token: cloud_id=%s",
            token.cloud_id,
        )

        try:
            new_tokens = await self.oauth_client.refresh_access_token(
                token.refresh_token
            )
        except AtlassianTokenExpiredError:
            logger.warning(
                "[ATLASSIAN][TOKEN] Refresh token expired: cloud_id=%s",
                token.cloud_id,
            )
            raise
        
        token.access_token = new_tokens.access_token
        token.refresh_token = new_tokens.refresh_token
        token.expires_at = datetime.now(timezone.utc) + timedelta(seconds = new_tokens.expires_in)
        db.flush()

        logger.info("[ATLASSIAN][TOKEN] Token refreshed: cloud_id=%s", token.cloud_id)
        return token.access_token

    async def resolve_access_token_by_cloud_id(
            self, db:Session, cloud_id: str
    ) -> str:
        token = self.oauth_repository.get_token_by_cloud_id(db, cloud_id)
        
        if not token:
            raise AtlassianTokenNotFoundError(cloud_id)
        
        return await self.resolve_access_token(db, token)
    
    def _is_token_expired(self, token: AtlassianOAuthToken) -> bool:
        return token.expires_at <= datetime.now(timezone.utc) + TOKEN_REFRESH_BUFFER