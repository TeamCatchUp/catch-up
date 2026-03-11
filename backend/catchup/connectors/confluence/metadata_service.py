"""
Confluence 메타데이터 동기화 서비스

- users -> spaces 순서로 동기화
- API 호출은 ConfluenceApiClient에 위임, 여기서는 오케스트레이션/DB upsert만 수행
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from catchup.connectors.atlassian.constants import REQUIRED_CONFLUENCE_SCOPES
from catchup.connectors.atlassian.token_manager import AtlassianTokenManager
from catchup.connectors.confluence.client import (
    ConfluenceApiClient,
)
from catchup.connectors.confluence.schemas import (
    ConfluenceSpaceResponse,
    ConfluenceUserResponse,
)
from catchup.db.atlassian import oauth_repository as atlassian_crud
from catchup.db.confluence import domain_repository as confluence_entities

logger = logging.getLogger(__name__)


class ConfluenceMetadataService:
    def __init__(self, token_manager: AtlassianTokenManager):
        self.token_manager = token_manager

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
                f"[CONFLUENCE][METADATA] No token found: cloud_id={cloud_id}"
            )
            return {"users": 0, "spaces": 0}

        granted_scopes = set((token.scopes or "").split())
        missing = REQUIRED_CONFLUENCE_SCOPES - granted_scopes
        if missing:
            logger.warning(
                f"[CONFLUENCE][METADATA] Missing scopes, skip: cloud_id={cloud_id}, missing={sorted(missing)}"
            )
            return {"users": 0, "spaces": 0}

        access_token = await self.token_manager.resolve_access_token(db, token)
        client = ConfluenceApiClient(cloud_id, access_token)

        users_count = await self._sync_users(
            db,
            client,
            cloud_id,
            auto_commit=auto_commit,
        )
        spaces_count = await self._sync_spaces(
            db,
            client,
            cloud_id,
            auto_commit=auto_commit,
        )

        return {"users": users_count, "spaces": spaces_count}

    async def _sync_users(
        self,
        db: Session,
        client: ConfluenceApiClient,
        cloud_id: str,
        *,
        auto_commit: bool = True,
    ) -> int:
        users_data = await client.get_users()
        payloads: list[dict] = []
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
            except Exception as e:
                logger.error(
                    f"[CONFLUENCE][METADATA] Failed to parse user: cloud_id={cloud_id}, error={e}"
                )
        if payloads:
            confluence_entities.upsert_users_bulk(
                db,
                payloads,
                auto_commit=auto_commit,
            )
        return len(payloads)

    async def _sync_spaces(
        self,
        db: Session,
        client: ConfluenceApiClient,
        cloud_id: str,
        *,
        auto_commit: bool = True,
    ) -> int:
        spaces = await client.get_spaces(space_type=None, status="current")
        payloads: list[dict] = []
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
            except Exception as e:
                logger.error(
                    f"[CONFLUENCE][METADATA] Failed to parse space: cloud_id={cloud_id}, error={e}"
                )
        sync_result = confluence_entities.sync_spaces_snapshot(
            db,
            cloud_id,
            payloads,
            auto_commit=auto_commit,
        )
        logger.info(
            "[CONFLUENCE][METADATA] Space snapshot synced: cloud_id=%s, upserted=%s, deleted=%s",
            cloud_id,
            sync_result["upserted"],
            sync_result["deleted"],
        )
        return len(payloads)
