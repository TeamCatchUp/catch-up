from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from fastapi.concurrency import run_in_threadpool

from catchup.configs.config import settings
from catchup.connectors.atlassian.oauth_client import AtlassianOAuthClient
from catchup.connectors.atlassian.token_manager import (
    AtlassianTokenManager,
    AtlassianTokenProvider,
)
from catchup.connectors.atlassian.utils import parse_atlassian_datetime
from catchup.connectors.confluence.client import ConfluenceApiClient
from catchup.db.atlassian import oauth_repository
from catchup.db.confluence import domain_repository as confluence_domain
from catchup.db.engine import SessionLocal
from catchup.events.enums import SyncTriggerEventAction
from catchup.sync.incremental.resolve import build_confluence_record_change
from catchup.sync.incremental.service import get_incremental_service

logger = logging.getLogger(__name__)


def _load_tokens_sync():
    with SessionLocal() as db:
        return oauth_repository.get_all_tokens(db)


def _load_spaces_sync(cloud_id: str):
    with SessionLocal() as db:
        return confluence_domain.get_spaces_by_cloud_id(db, cloud_id)


async def poll_confluence_incremental_changes() -> dict[str, int]:
    lookback_minutes = max(1, int(settings.CONFLUENCE_INCREMENTAL_POLL_LOOKBACK_MINUTES))
    since = datetime.now(timezone.utc) - timedelta(minutes=lookback_minutes)
    changed = 0
    blocked = 0
    errors = 0

    token_manager = AtlassianTokenManager(
        oauth_client=AtlassianOAuthClient(),
        oauth_repository=oauth_repository,
    )
    token_provider = AtlassianTokenProvider(token_manager)

    tokens = await run_in_threadpool(_load_tokens_sync)

    for token in tokens:
        try:
            spaces = await run_in_threadpool(_load_spaces_sync, token.cloud_id)
            client = ConfluenceApiClient(token.cloud_id, token_provider)
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

                changes = [*page_changes, *blogpost_changes]
                if not changes:
                    continue

                result = await get_incremental_service().ingest_changes_async(
                    changes=changes,
                    event_name=space_key,
                    context_name="space_key",
                    action=SyncTriggerEventAction.CONFLUENCE_POLLING_STARTED,
                )
                blocked += result.blocked_count
                if result.blocked_count > 0:
                    logger.info(
                        "[CONFLUENCE][POLL] Incremental blocked before ingest: cloud_id=%s, source=poll, blocked_count=%s",
                        token.cloud_id,
                        result.blocked_count,
                    )
                if not result.record_keys:
                    continue
                changed += len(result.record_keys)
        except Exception:
            logger.exception(
                "[CONFLUENCE][POLL] Failed to poll cloud: cloud_id=%s",
                token.cloud_id,
            )
            errors += 1

    return {
        "changed": changed,
        "blocked_full_sync_required": blocked,
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
