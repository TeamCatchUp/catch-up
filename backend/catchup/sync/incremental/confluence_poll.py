from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from catchup.configs.config import settings
from catchup.connectors.atlassian.oauth_client import AtlassianOAuthClient
from catchup.connectors.atlassian.token_manager import (
    AtlassianTokenManager,
    AtlassianTokenProvider,
)
from catchup.connectors.atlassian.utils import parse_atlassian_datetime
from catchup.connectors.confluence.client import ConfluenceApiClient
from catchup.audit.enums import AuditEventStatus, AuditLevel
from catchup.db.atlassian import oauth_repository
from catchup.db.confluence import domain_repository as confluence_domain
from catchup.db.engine import SessionLocal
from catchup.db.models import SyncConnector
from catchup.events.enums import SyncTriggerEventAction
from catchup.sync.audit import SyncAuditContext, emit_sync_trigger_audit
from catchup.sync.incremental.full_sync_guard import filter_record_changes_by_full_sync
from catchup.sync.incremental.ingress import build_confluence_record_change, ingest_record_changes

logger = logging.getLogger(__name__)


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

    with SessionLocal() as db:
        tokens = oauth_repository.get_all_tokens(db)

    for token in tokens:
        try:
            with SessionLocal() as db:
                spaces = confluence_domain.get_spaces_by_cloud_id(db, token.cloud_id)

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

                with SessionLocal() as db:
                    changes = [*page_changes, *blogpost_changes]
                    guard_result = filter_record_changes_by_full_sync(db, changes)
                    blocked_count = len(guard_result.blocked_changes)
                    if blocked_count > 0:
                        blocked += blocked_count
                        blocked_targets = guard_result.blocked_targets
                        if not guard_result.allowed_changes:
                            logger.info(
                                "[CONFLUENCE][POLL] Incremental blocked before ingest: cloud_id=%s, source=poll, blocked_count=%s, blocked_targets=%s",
                                token.cloud_id,
                                blocked_count,
                                [
                                    f"{target.target_type}:{target.target_id}"
                                    for target in blocked_targets
                                ],
                            )
                        else:
                            logger.info(
                                "[CONFLUENCE][POLL] Incremental partially blocked before ingest: cloud_id=%s, source=poll, allowed_count=%s, blocked_count=%s, blocked_targets=%s",
                                token.cloud_id,
                                len(guard_result.allowed_changes),
                                blocked_count,
                                [
                                    f"{target.target_type}:{target.target_id}"
                                    for target in blocked_targets
                                ],
                            )

                    if guard_result.allowed_changes:
                        first_change = guard_result.allowed_changes[0]
                        audit_context = SyncAuditContext(
                            connector=SyncConnector.CONFLUENCE,
                            scope_id=first_change.scope_id,
                            target_id=first_change.parent_id,
                        )
                        emit_sync_trigger_audit(
                            action=SyncTriggerEventAction.CONFLUENCE_POLLING_STARTED,
                            status=AuditEventStatus.ATTEMPT,
                            audit_context=audit_context,
                            context=(
                                f"stage=record_change_ingest,space_key={first_change.parent_id},"
                                f"change_count={len(guard_result.allowed_changes)}"
                            ),
                        )
                        try:
                            changed += len(ingest_record_changes(db, guard_result.allowed_changes))
                        except Exception as exc:
                            emit_sync_trigger_audit(
                                action=SyncTriggerEventAction.CONFLUENCE_POLLING_STARTED,
                                status=AuditEventStatus.FAIL,
                                audit_context=audit_context,
                                context=(
                                    f"stage=record_change_ingest_failed,space_key={first_change.parent_id},"
                                    f"error={str(exc).strip()[:200]}"
                                ),
                                level=AuditLevel.ERROR,
                            )
                            raise
                        emit_sync_trigger_audit(
                            action=SyncTriggerEventAction.CONFLUENCE_POLLING_STARTED,
                            status=AuditEventStatus.SUCCESS,
                            audit_context=audit_context,
                            context=(
                                f"stage=record_change_ingested,space_key={first_change.parent_id},"
                                f"blocked_count={blocked_count}"
                            ),
                        )
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
