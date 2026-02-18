"""
Confluence 메타데이터 동기화 서비스

- users -> spaces -> space members 순서로 동기화
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
    ConfluenceAuthError,
    ConfluenceApiError,
)
from catchup.connectors.confluence.schemas import (
    ConfluenceSpaceResponse,
    ConfluenceUserResponse,
    ConfluenceRoleAssignmentResponse,
)
from catchup.db.atlassian import oauth_repository as atlassian_crud
from catchup.db.confluence import domain_repository as confluence_entities

logger = logging.getLogger(__name__)


class ConfluenceMetadataService:
    def __init__(self, token_manager: AtlassianTokenManager):
        self.token_manager = token_manager

    async def sync_all(self, db: Session, cloud_id: str) -> dict[str, Any]:
        token = atlassian_crud.get_token_by_cloud_id(db, cloud_id)
        if not token:
            logger.warning(
                f"[CONFLUENCE][METADATA] No token found: cloud_id={cloud_id}"
            )
            return {"users": 0, "spaces": 0, "members": 0}

        granted_scopes = set((token.scopes or "").split())
        missing = REQUIRED_CONFLUENCE_SCOPES - granted_scopes
        if missing:
            logger.warning(
                f"[CONFLUENCE][METADATA] Missing scopes, skip: cloud_id={cloud_id}, missing={sorted(missing)}"
            )
            return {"users": 0, "spaces": 0, "members": 0}

        access_token = await self.token_manager.resolve_access_token(db, token)
        client = ConfluenceApiClient(cloud_id, access_token)

        users_count = await self._sync_users(db, client, cloud_id)
        spaces_count = await self._sync_spaces(db, client, cloud_id)
        members_count = await self._sync_space_members(db, client, cloud_id)

        return {"users": users_count, "spaces": spaces_count, "members": members_count}

    async def _sync_users(self, db: Session, client: ConfluenceApiClient, cloud_id: str) -> int:
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
            confluence_entities.upsert_users_bulk(db, payloads)
        return len(payloads)

    async def _sync_spaces(self, db: Session, client: ConfluenceApiClient, cloud_id: str) -> int:
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
        if payloads:
            confluence_entities.upsert_spaces_bulk(db, payloads)
        return len(payloads)

    async def _sync_space_members(self, db: Session, client: ConfluenceApiClient, cloud_id: str) -> int:
        spaces = confluence_entities.get_spaces_by_cloud_id(db, cloud_id)
        total_members = 0
        role_scope_failed = False

        for space in spaces:
            space_id = space.space_id
            try:
                assignments = await client.get_space_role_assignments(space_id)
            except ConfluenceAuthError as e:
                if not role_scope_failed:
                    logger.error(
                        f"[CONFLUENCE][METADATA] Role assignment fetch unauthorized (scope?): cloud_id={cloud_id}, space_id={space_id}, error={e}"
                    )
                    role_scope_failed = True
                break
            except ConfluenceApiError as e:
                status = getattr(e, "status_code", None)
                if status == 404:
                    try:
                        assignments = await client.get_space_permissions(space_id)
                    except Exception as e_perm:
                        logger.error(
                            f"[CONFLUENCE][METADATA] Failed to fetch permissions fallback: cloud_id={cloud_id}, space_id={space_id}, error={e_perm}"
                        )
                        continue
                else:
                    logger.error(
                        f"[CONFLUENCE][METADATA] Failed to fetch role assignments: cloud_id={cloud_id}, space_id={space_id}, error={e}"
                    )
                    continue

            space_members: list[dict] = []
            for raw_assignment in assignments:
                try:
                    if "role" in raw_assignment:
                        assignment = ConfluenceRoleAssignmentResponse.model_validate(raw_assignment)
                        if assignment.principal_type.lower() != "user":
                            continue
                        space_members.append(
                            {
                                "cloud_id": cloud_id,
                                "space_id": space_id,
                                "account_id": assignment.principal_id,
                                "role_id": assignment.role.id,
                                "role_key": assignment.role.key,
                                "role_name": assignment.role.name,
                                "principal_type": assignment.principal_type,
                                "synced_at": datetime.now(timezone.utc),
                            }
                        )
                    else:
                        subject = (raw_assignment or {}).get("subject", {})
                        subj_type = subject.get("type", "")
                        account_id = subject.get("user", {}).get("accountId") if isinstance(subject.get("user"), dict) else None
                        if subj_type.lower() != "user" or not account_id:
                            continue
                        perm_id = str(raw_assignment.get("id", "")) or f"perm:{space_id}"
                        operation = raw_assignment.get("operation", {}) if isinstance(raw_assignment, dict) else {}
                        role_key = operation.get("key")
                        role_name = role_key or operation.get("access")
                        space_members.append(
                            {
                                "cloud_id": cloud_id,
                                "space_id": space_id,
                                "account_id": account_id,
                                "role_id": perm_id,
                                "role_key": role_key,
                                "role_name": role_name,
                                "principal_type": subj_type,
                                "synced_at": datetime.now(timezone.utc),
                            }
                        )
                except Exception as e:
                    logger.error(
                        f"[CONFLUENCE][METADATA] Failed to parse role assignment: cloud_id={cloud_id}, space_id={space_id}, error={e}"
                    )

            confluence_entities.delete_space_members_by_space(db, cloud_id, space_id)
            if space_members:
                confluence_entities.upsert_space_members_bulk(db, space_members)
                total_members += len(space_members)
                logger.info(
                    f"[CONFLUENCE][METADATA] Saved {len(space_members)} members for space_id={space_id}"
                )

        if spaces:
            logger.info(
                f"[CONFLUENCE][METADATA] Completed member sync: cloud_id={cloud_id}, members={total_members}"
            )

        return total_members
