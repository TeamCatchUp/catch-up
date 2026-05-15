from __future__ import annotations

import logging
from datetime import datetime
from datetime import timedelta
from datetime import timezone

from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select

from catchup.configs.config import settings
from catchup.connectors.atlassian.oauth_client import AtlassianOAuthClient
from catchup.connectors.atlassian.token_manager import AtlassianTokenManager
from catchup.connectors.atlassian.token_manager import AtlassianTokenProvider
from catchup.connectors.atlassian.utils import parse_atlassian_datetime
from catchup.connectors.confluence.client import ConfluenceApiClient
from catchup.db.atlassian import oauth_repository
from catchup.db.confluence import domain_repository as confluence_domain
from catchup.db.engine import SessionLocal
from catchup.db.models import IncrementalRecordState
from catchup.sync.incremental.resolve import build_confluence_record_change
from catchup.sync.incremental.schemas import RecordChange
from catchup.sync.incremental.service import get_incremental_service

logger = logging.getLogger(__name__)

CONFLUENCE_DELETED_CONTENT_STATUSES = ("trashed",)


def _load_tokens_sync():
    with SessionLocal() as db:
        return oauth_repository.get_all_tokens(db)


def _load_spaces_sync(cloud_id: str):
    with SessionLocal() as db:
        return confluence_domain.get_spaces_by_cloud_id(db, cloud_id)


def _load_existing_deleted_record_keys_sync(record_keys: list[str]) -> set[str]:
    normalized_record_keys = [
        record_key.strip()
        for record_key in record_keys
        if record_key and record_key.strip()
    ]
    if not normalized_record_keys:
        return set()

    with SessionLocal() as db:
        stmt = select(IncrementalRecordState.record_key).where(
            IncrementalRecordState.record_key.in_(normalized_record_keys),
            IncrementalRecordState.event_kind == "deleted",
        )
        return set(db.execute(stmt).scalars().all())


async def poll_confluence_incremental_changes() -> dict[str, int]:
    lookback_minutes = max(1, int(settings.CONFLUENCE_INCREMENTAL_POLL_LOOKBACK_MINUTES))
    polled_at = datetime.now(timezone.utc)
    since = polled_at - timedelta(minutes=lookback_minutes)
    deleted_max_pages = max(
        1,
        int(settings.CONFLUENCE_INCREMENTAL_DELETED_POLL_MAX_PAGES),
    )
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
                deleted_page_changes = await _collect_deleted_page_changes(
                    client=client,
                    cloud_id=token.cloud_id,
                    space_id=space_id,
                    space_key=space_key,
                    observed_at=polled_at,
                    max_batches=deleted_max_pages,
                )
                deleted_blogpost_changes = await _collect_deleted_blogpost_changes(
                    client=client,
                    cloud_id=token.cloud_id,
                    space_id=space_id,
                    space_key=space_key,
                    observed_at=polled_at,
                    max_batches=deleted_max_pages,
                )

                changes = [
                    *page_changes,
                    *blogpost_changes,
                    *deleted_page_changes,
                    *deleted_blogpost_changes,
                ]
                changes = await _filter_repeated_deleted_changes(changes)
                if not changes:
                    continue

                result = await get_incremental_service().dispatch_changes(
                    changes=changes,
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


async def _filter_repeated_deleted_changes(
    changes: list[RecordChange],
) -> list[RecordChange]:
    deleted_record_keys = [
        change.record_key
        for change in changes
        if change.event_kind == "deleted"
    ]
    if not deleted_record_keys:
        return changes

    existing_deleted_record_keys = await run_in_threadpool(
        _load_existing_deleted_record_keys_sync,
        deleted_record_keys,
    )
    if not existing_deleted_record_keys:
        return changes

    return [
        change
        for change in changes
        if change.event_kind != "deleted"
        or change.record_key not in existing_deleted_record_keys
    ]


async def _collect_page_changes(
    *,
    client: ConfluenceApiClient,
    cloud_id: str,
    space_id: str,
    space_key: str,
    since: datetime,
    status: str = "current",
    event_kind: str = "updated",
    observed_at: datetime | None = None,
    max_batches: int | None = None,
) -> list:
    changes = []
    should_stop = False
    batch_count = 0
    async for batch in client.iter_pages(
        space_id=space_id,
        status=status,
        body_format="storage",
    ):
        batch_count += 1
        for raw_page in batch:
            page_id = str(raw_page.get("id") or "").strip()
            event_at = observed_at or parse_atlassian_datetime(
                ((raw_page.get("version") or {}).get("createdAt"))
            )
            if not page_id or event_at is None:
                continue
            if event_kind != "deleted" and event_at < since:
                should_stop = True
                continue
            changes.append(
                build_confluence_record_change(
                    cloud_id=cloud_id,
                    space_key=space_key,
                    record_type="page",
                    record_id=page_id,
                    last_event_at=event_at,
                    event_kind=event_kind,
                )
            )
        if should_stop or (max_batches is not None and batch_count >= max_batches):
            break
    return changes


async def _collect_blogpost_changes(
    *,
    client: ConfluenceApiClient,
    cloud_id: str,
    space_id: str,
    space_key: str,
    since: datetime,
    status: str = "current",
    event_kind: str = "updated",
    observed_at: datetime | None = None,
    max_batches: int | None = None,
) -> list:
    changes = []
    should_stop = False
    batch_count = 0
    async for batch in client.iter_blogposts(
        space_id=space_id,
        status=status,
        body_format="storage",
    ):
        batch_count += 1
        for raw_blogpost in batch:
            blogpost_id = str(raw_blogpost.get("id") or "").strip()
            event_at = observed_at or parse_atlassian_datetime(
                ((raw_blogpost.get("version") or {}).get("createdAt"))
            )
            if not blogpost_id or event_at is None:
                continue
            if event_kind != "deleted" and event_at < since:
                should_stop = True
                continue
            changes.append(
                build_confluence_record_change(
                    cloud_id=cloud_id,
                    space_key=space_key,
                    record_type="blogpost",
                    record_id=blogpost_id,
                    last_event_at=event_at,
                    event_kind=event_kind,
                )
            )
        if should_stop or (max_batches is not None and batch_count >= max_batches):
            break
    return changes


async def _collect_deleted_page_changes(
    *,
    client: ConfluenceApiClient,
    cloud_id: str,
    space_id: str,
    space_key: str,
    observed_at: datetime,
    max_batches: int,
) -> list:
    changes = []
    for status in CONFLUENCE_DELETED_CONTENT_STATUSES:
        changes.extend(
            await _collect_page_changes(
                client=client,
                cloud_id=cloud_id,
                space_id=space_id,
                space_key=space_key,
                since=observed_at,
                status=status,
                event_kind="deleted",
                observed_at=observed_at,
                max_batches=max_batches,
            )
        )
    return changes


async def _collect_deleted_blogpost_changes(
    *,
    client: ConfluenceApiClient,
    cloud_id: str,
    space_id: str,
    space_key: str,
    observed_at: datetime,
    max_batches: int,
) -> list:
    changes = []
    for status in CONFLUENCE_DELETED_CONTENT_STATUSES:
        changes.extend(
            await _collect_blogpost_changes(
                client=client,
                cloud_id=cloud_id,
                space_id=space_id,
                space_key=space_key,
                since=observed_at,
                status=status,
                event_kind="deleted",
                observed_at=observed_at,
                max_batches=max_batches,
            )
        )
    return changes
