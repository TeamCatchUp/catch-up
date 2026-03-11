from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from catchup.configs.config import settings
from catchup.connectors.atlassian.oauth_client import AtlassianOAuthClient
from catchup.connectors.atlassian.token_manager import AtlassianTokenManager
from catchup.connectors.atlassian.utils import parse_atlassian_datetime
from catchup.connectors.confluence.client import ConfluenceApiClient
from catchup.db.atlassian import oauth_repository
from catchup.db.confluence import domain_repository as confluence_domain
from catchup.db.engine import SessionLocal
from catchup.sync.incremental.ingress import build_confluence_record_change, ingest_record_changes

logger = logging.getLogger(__name__)


async def poll_confluence_incremental_changes() -> dict[str, int]:
    lookback_minutes = max(1, int(settings.CONFLUENCE_INCREMENTAL_POLL_LOOKBACK_MINUTES))
    since = datetime.now(timezone.utc) - timedelta(minutes=lookback_minutes)
    changed = 0
    errors = 0

    token_manager = AtlassianTokenManager(
        oauth_client=AtlassianOAuthClient(),
        oauth_repository=oauth_repository,
    )

    with SessionLocal() as db:
        tokens = oauth_repository.get_all_tokens(db)

    for token in tokens:
        try:
            with SessionLocal() as db:
                access_token = await token_manager.resolve_access_token_by_cloud_id(db, token.cloud_id)
                spaces = confluence_domain.get_spaces_by_cloud_id(db, token.cloud_id)

            client = ConfluenceApiClient(token.cloud_id, access_token)
            for space in spaces:
                space_id = (space.space_id or "").strip()
                space_key = (space.space_key or "").strip()
                if not space_id or not space_key:
                    continue

                page_changes = await _collect_page_changes(
                    client=client,
                    cloud_id=token.cloud_id,
                    space_id=space_id,
                    space_key=space_key,
                    since=since,
                )
                blogpost_changes = await _collect_blogpost_changes(
                    client=client,
                    cloud_id=token.cloud_id,
                    space_id=space_id,
                    space_key=space_key,
                    since=since,
                )

                with SessionLocal() as db:
                    changed += len(ingest_record_changes(db, [*page_changes, *blogpost_changes]))
        except Exception:
            logger.exception(
                "[CONFLUENCE][POLL] Failed to poll cloud: cloud_id=%s",
                token.cloud_id,
            )
            errors += 1

    return {
        "changed": changed,
        "errors": errors,
    }


async def _collect_page_changes(
    *,
    client: ConfluenceApiClient,
    cloud_id: str,
    space_id: str,
    space_key: str,
    since: datetime,
) -> list:
    changes = []
    should_stop = False
    async for batch in client.iter_pages(space_id=space_id, body_format="storage"):
        for raw_page in batch:
            page_id = str(raw_page.get("id") or "").strip()
            modified_at = parse_atlassian_datetime(
                ((raw_page.get("version") or {}).get("createdAt"))
            )
            if not page_id or modified_at is None:
                continue
            if modified_at < since:
                should_stop = True
                continue
            changes.append(
                build_confluence_record_change(
                    cloud_id=cloud_id,
                    space_key=space_key,
                    record_type="page",
                    record_id=page_id,
                    last_event_at=modified_at,
                )
            )
        if should_stop:
            break
    return changes


async def _collect_blogpost_changes(
    *,
    client: ConfluenceApiClient,
    cloud_id: str,
    space_id: str,
    space_key: str,
    since: datetime,
) -> list:
    changes = []
    should_stop = False
    async for batch in client.iter_blogposts(space_id=space_id, body_format="storage"):
        for raw_blogpost in batch:
            blogpost_id = str(raw_blogpost.get("id") or "").strip()
            modified_at = parse_atlassian_datetime(
                ((raw_blogpost.get("version") or {}).get("createdAt"))
            )
            if not blogpost_id or modified_at is None:
                continue
            if modified_at < since:
                should_stop = True
                continue
            changes.append(
                build_confluence_record_change(
                    cloud_id=cloud_id,
                    space_key=space_key,
                    record_type="blogpost",
                    record_id=blogpost_id,
                    last_event_at=modified_at,
                )
            )
        if should_stop:
            break
    return changes
