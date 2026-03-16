"""
Confluence 메타데이터 동기화 서비스

- users -> spaces 순서로 동기화
- API 호출은 ConfluenceApiClient에 위임, 여기서는 오케스트레이션/DB upsert만 수행
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from catchup.connectors.atlassian.constants import REQUIRED_CONFLUENCE_SCOPES
from catchup.connectors.atlassian.token_manager import (
    AtlassianTokenManager,
    AtlassianTokenProvider,
)
from catchup.connectors.confluence.client import ConfluenceApiClient
from catchup.connectors.confluence.schemas import (
    ConfluenceSpaceResponse,
    ConfluenceUserResponse,
)
from catchup.db.atlassian import oauth_repository as atlassian_crud
from catchup.db.confluence import domain_repository as confluence_entities

logger = logging.getLogger(__name__)


@dataclass(slots=True, frozen=True)
class ConfluenceMetadataSnapshot:
    users: list[dict[str, Any]] = field(default_factory=list)
    spaces: list[dict[str, Any]] = field(default_factory=list)


class ConfluenceMetadataService:
    def __init__(self, token_manager: AtlassianTokenManager):
        self.token_manager = token_manager

    def persist_snapshot(
        self,
        db: Session,
        cloud_id: str,
        snapshot: ConfluenceMetadataSnapshot,
        *,
        auto_commit: bool = True,
    ) -> None:
        if snapshot.users:
            confluence_entities.upsert_users_bulk(
                db,
                snapshot.users,
                auto_commit=False,
            )

        sync_result = confluence_entities.sync_spaces_snapshot(
            db,
            cloud_id,
            snapshot.spaces,
            auto_commit=False,
        )
        logger.info(
            "[CONFLUENCE][METADATA] Space snapshot synced: cloud_id=%s, upserted=%s, deleted=%s",
            cloud_id,
            sync_result["upserted"],
            sync_result["deleted"],
        )

        if auto_commit:
            db.commit()
        else:
            db.flush()

    async def collect_snapshot(
        self,
        cloud_id: str,
        *,
        granted_scopes: set[str],
    ) -> ConfluenceMetadataSnapshot | None:
        missing = REQUIRED_CONFLUENCE_SCOPES - granted_scopes
        if missing:
            logger.warning(
                "[CONFLUENCE][METADATA] Missing scopes, skip: cloud_id=%s, missing=%s",
                cloud_id,
                sorted(missing),
            )
            return None

        client = ConfluenceApiClient(
            cloud_id,
            AtlassianTokenProvider(self.token_manager),
        )
        users = await self._collect_users(client, cloud_id)
        spaces = await self._collect_spaces(client, cloud_id)
        return ConfluenceMetadataSnapshot(users=users, spaces=spaces)

    async def sync_all(
        self,
        db: Session,
        cloud_id: str,
        *,
        auto_commit: bool = True,
    ) -> dict[str, Any]:
        token = atlassian_crud.get_token_by_cloud_id(db, cloud_id)
        if not token:
            logger.warning(
                "[CONFLUENCE][METADATA] No token found: cloud_id=%s",
                cloud_id,
            )
            return {"users": 0, "spaces": 0}

        snapshot = await self.collect_snapshot(
            cloud_id,
            granted_scopes=set((token.scopes or "").split()),
        )
        if snapshot is None:
            return {"users": 0, "spaces": 0}
        self.persist_snapshot(
            db,
            cloud_id,
            snapshot,
            auto_commit=auto_commit,
        )
        return {"users": len(snapshot.users), "spaces": len(snapshot.spaces)}

    async def _collect_users(
        self,
        client: ConfluenceApiClient,
        cloud_id: str,
    ) -> list[dict[str, Any]]:
        users_data = await client.get_users()
        payloads: list[dict[str, Any]] = []
        for raw_user in users_data:
            try:
                payload = raw_user.get("user") if isinstance(raw_user, dict) else raw_user
                if not payload or not payload.get("accountId"):
                    continue
                user = ConfluenceUserResponse.model_validate(payload)
                payloads.append(
                    {
                        "cloud_id": cloud_id,
                        "account_id": user.id,
                        "account_type": user.account_type,
                        "display_name": user.display_name,
                        "public_name": user.public_name,
                        "email": user.email,
                        "time_zone": user.time_zone,
                        "locale": user.locale,
                        "avatar_url": user.get_avatar_url(),
                        "is_external_collaborator": user.is_external_collaborator,
                        "synced_at": datetime.now(timezone.utc),
                    }
                )
            except Exception as exc:
                logger.error(
                    "[CONFLUENCE][METADATA] Failed to parse user: cloud_id=%s, error=%s",
                    cloud_id,
                    exc,
                )
        return payloads

    async def _collect_spaces(
        self,
        client: ConfluenceApiClient,
        cloud_id: str,
    ) -> list[dict[str, Any]]:
        spaces = await client.get_spaces(space_type=None, status="current")
        payloads: list[dict[str, Any]] = []
        for raw_space in spaces:
            try:
                space = ConfluenceSpaceResponse.model_validate(raw_space)
                description_text = ""
                if space.description:
                    description_text = space.description.get_plain_text()

                payloads.append(
                    {
                        "cloud_id": cloud_id,
                        "space_id": space.id,
                        "space_key": space.key,
                        "space_name": space.name,
                        "space_type": space.type,
                        "status": space.status,
                        "homepage_id": space.homepage_id,
                        "description": description_text[:2000] if description_text else None,
                        "synced_at": datetime.now(timezone.utc),
                    }
                )
            except Exception as exc:
                logger.error(
                    "[CONFLUENCE][METADATA] Failed to parse space: cloud_id=%s, error=%s",
                    cloud_id,
                    exc,
                )
        return payloads
