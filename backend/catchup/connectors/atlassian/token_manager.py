import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import Lock
from types import ModuleType
from typing import Callable, ClassVar

from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from catchup.connectors.atlassian.exceptions import (
    AtlassianTokenNotFoundError,
)
from catchup.connectors.atlassian.oauth_client import AtlassianOAuthClient
from catchup.db.engine import SessionLocal
from catchup.db.models import AtlassianOAuthToken

logger = logging.getLogger(__name__)

TOKEN_REFRESH_BUFFER = timedelta(minutes=5)

@dataclass(frozen=True, slots=True)
class AtlassianTokenSnapshot:
    cloud_id: str
    access_token: str
    refresh_token: str
    expires_at: datetime


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

    def _normalize_expires_at(self, expires_at: datetime) -> datetime:
        if expires_at.tzinfo is None:
            return expires_at.replace(tzinfo=timezone.utc)
        return expires_at.astimezone(timezone.utc)

    def _needs_refresh(self, expires_at: datetime) -> bool:
        return self._normalize_expires_at(expires_at) <= (
            datetime.now(timezone.utc) + TOKEN_REFRESH_BUFFER
        )


class AtlassianTokenProvider:
    def __init__(
        self,
        token_manager: AtlassianTokenManager,
        session_factory: Callable[[], Session] = SessionLocal,
    ):
        self.token_manager = token_manager
        self.session_factory = session_factory

    def _load_token_snapshot_sync(self, cloud_id: str) -> AtlassianTokenSnapshot:
        with self.session_factory() as db:
            token = self.token_manager.oauth_repository.get_token_by_cloud_id(
                db,
                cloud_id,
            )
            if token is None:
                raise AtlassianTokenNotFoundError(cloud_id)
            return AtlassianTokenSnapshot(
                cloud_id=token.cloud_id,
                access_token=token.access_token,
                refresh_token=token.refresh_token,
                expires_at=token.expires_at,
            )

    def _persist_refreshed_token_sync(
        self,
        cloud_id: str,
        access_token: str,
        refresh_token: str,
        expires_at: datetime,
    ) -> AtlassianTokenSnapshot:
        with self.session_factory() as db:
            refreshed = self.token_manager.oauth_repository.update_refreshed_token(
                db=db,
                cloud_id=cloud_id,
                access_token=access_token,
                refresh_token=refresh_token,
                expires_at=expires_at,
            )
            if refreshed is None:
                raise AtlassianTokenNotFoundError(cloud_id)
            return AtlassianTokenSnapshot(
                cloud_id=refreshed.cloud_id,
                access_token=refreshed.access_token,
                refresh_token=refreshed.refresh_token,
                expires_at=refreshed.expires_at,
            )

    async def get_access_token(
        self,
        cloud_id: str,
        *,
        force_refresh: bool = False,
    ) -> str:
        snapshot = await run_in_threadpool(self._load_token_snapshot_sync, cloud_id)
        if not force_refresh and not self.token_manager._needs_refresh(snapshot.expires_at):
            return snapshot.access_token

        lock = self.token_manager._get_refresh_lock(cloud_id)
        async with lock:
            latest = await run_in_threadpool(self._load_token_snapshot_sync, cloud_id)
            if force_refresh:
                token_changed = latest.access_token != snapshot.access_token
                expires_changed = latest.expires_at != snapshot.expires_at
                if token_changed or expires_changed:
                    return latest.access_token
            elif not self.token_manager._needs_refresh(latest.expires_at):
                return latest.access_token

            new_tokens = await self.token_manager.oauth_client.refresh_access_token(
                latest.refresh_token
            )
            expires_at = datetime.now(timezone.utc) + timedelta(
                seconds=new_tokens.expires_in
            )
            refreshed = await run_in_threadpool(
                self._persist_refreshed_token_sync,
                latest.cloud_id,
                new_tokens.access_token,
                new_tokens.refresh_token,
                expires_at,
            )
            logger.info(
                "[ATLASSIAN][TOKEN] Refreshed access token: cloud_id=%s",
                latest.cloud_id,
            )
            return refreshed.access_token
