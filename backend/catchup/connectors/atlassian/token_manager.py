import asyncio
import logging
from datetime import datetime, timedelta, timezone
from threading import Lock
from types import ModuleType
from typing import Callable, ClassVar

from sqlalchemy.orm import Session

from catchup.connectors.atlassian.exceptions import (
    AtlassianTokenNotFoundError,
)
from catchup.connectors.atlassian.oauth_client import AtlassianOAuthClient
from catchup.db.engine import SessionLocal
from catchup.db.models import AtlassianOAuthToken

logger = logging.getLogger(__name__)

TOKEN_REFRESH_BUFFER = timedelta(minutes=5)


class AtlassianTokenManager:
    _refresh_locks: ClassVar[dict[str, asyncio.Lock]] = {}
    _refresh_locks_guard: ClassVar[Lock] = Lock()

    def __init__(
        self,
        oauth_client: AtlassianOAuthClient,
        oauth_repository: ModuleType,
    ):
        self.oauth_client = oauth_client
        self.oauth_repository = oauth_repository

    def _get_refresh_lock(self, cloud_id: str) -> asyncio.Lock:
        with self._refresh_locks_guard:
            lock = self._refresh_locks.get(cloud_id)
            if lock is None:
                lock = asyncio.Lock()
                self._refresh_locks[cloud_id] = lock
            return lock

    def _reload_token(self, db: Session, cloud_id: str) -> AtlassianOAuthToken:
        db.expire_all()
        token = self.oauth_repository.get_token_by_cloud_id(db, cloud_id)
        if token is None:
            raise AtlassianTokenNotFoundError(cloud_id)
        db.refresh(token)
        return token

    def _normalize_expires_at(self, expires_at: datetime) -> datetime:
        if expires_at.tzinfo is None:
            return expires_at.replace(tzinfo=timezone.utc)
        return expires_at.astimezone(timezone.utc)

    def _needs_refresh(self, token: AtlassianOAuthToken) -> bool:
        return self._normalize_expires_at(token.expires_at) <= (
            datetime.now(timezone.utc) + TOKEN_REFRESH_BUFFER
        )

    async def _refresh_token(
        self,
        db: Session,
        token: AtlassianOAuthToken,
    ) -> AtlassianOAuthToken:
        new_tokens = await self.oauth_client.refresh_access_token(token.refresh_token)
        refreshed = self.oauth_repository.update_refreshed_token(
            db=db,
            cloud_id=token.cloud_id,
            access_token=new_tokens.access_token,
            refresh_token=new_tokens.refresh_token,
            expires_at=(
                datetime.now(timezone.utc) + timedelta(seconds=new_tokens.expires_in)
            ),
        )
        if refreshed is None:
            raise AtlassianTokenNotFoundError(token.cloud_id)
        logger.info("[ATLASSIAN][TOKEN] Refreshed access token: cloud_id=%s", token.cloud_id)
        return refreshed

    async def resolve_access_token(
        self,
        db: Session,
        token: AtlassianOAuthToken,
        *,
        force_refresh: bool = False,
    ) -> str:
        cloud_id = token.cloud_id
        snapshot_access_token = token.access_token
        snapshot_expires_at = token.expires_at

        latest = self._reload_token(db, cloud_id)
        if not force_refresh and not self._needs_refresh(latest):
            return latest.access_token

        lock = self._get_refresh_lock(cloud_id)
        async with lock:
            latest = self._reload_token(db, cloud_id)
            if force_refresh:
                token_changed = latest.access_token != snapshot_access_token
                expires_changed = latest.expires_at != snapshot_expires_at
                if token_changed or expires_changed:
                    return latest.access_token
            elif not self._needs_refresh(latest):
                return latest.access_token

            refreshed = await self._refresh_token(db, latest)
            return refreshed.access_token

    async def resolve_access_token_by_cloud_id(
        self,
        db: Session,
        cloud_id: str,
        *,
        force_refresh: bool = False,
    ) -> str:
        token = self._reload_token(db, cloud_id)
        return await self.resolve_access_token(
            db,
            token,
            force_refresh=force_refresh,
        )


class AtlassianTokenProvider:
    def __init__(
        self,
        token_manager: AtlassianTokenManager,
        session_factory: Callable[[], Session] = SessionLocal,
    ):
        self.token_manager = token_manager
        self.session_factory = session_factory

    async def get_access_token(
        self,
        cloud_id: str,
        *,
        force_refresh: bool = False,
    ) -> str:
        with self.session_factory() as db:
            return await self.token_manager.resolve_access_token_by_cloud_id(
                db,
                cloud_id,
                force_refresh=force_refresh,
            )
