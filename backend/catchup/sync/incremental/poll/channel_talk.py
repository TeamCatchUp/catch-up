from __future__ import annotations

import logging
from datetime import datetime
from datetime import timedelta
from datetime import timezone

from fastapi.concurrency import run_in_threadpool

from catchup.configs.config import settings
from catchup.sync.ingestion.adapters.channel_talk.article_models import (
    DEFAULT_ARTICLE_FULL_SYNC_STATES,
)
from catchup.connectors.channel_talk.document_space.client import (
    ChannelTalkDocumentsApiClient,
)
from catchup.connectors.channel_talk.document_space.http_client import (
    ChannelTalkDocumentsHttpClient,
)
from catchup.connectors.channel_talk.schemas.document_article import (
    ChannelTalkDocumentArticle,
)
from catchup.connectors.channel_talk.schemas.document_connection import (
    ChannelTalkDocumentCredentialsRecord,
)
from catchup.db.channel_talk import ChannelTalkDocumentCredentialsRepository
from catchup.db.engine import SessionLocal
from catchup.sync.incremental.resolve import build_channel_talk_document_article_change
from catchup.sync.incremental.schemas import RecordChange
from catchup.sync.incremental.service import get_incremental_service

logger = logging.getLogger(__name__)


def _load_due_document_connections_sync(
    *,
    now: datetime,
    stale_started_before: datetime,
) -> list[ChannelTalkDocumentCredentialsRecord]:
    with SessionLocal() as db:
        return ChannelTalkDocumentCredentialsRepository(db).list_due_document_connections(
            now=now,
            stale_started_before=stale_started_before,
        )


def _mark_started_sync(*, space_id: str, started_at: datetime) -> bool:
    with SessionLocal() as db:
        repository = ChannelTalkDocumentCredentialsRepository(db)
        marked = repository.mark_document_poll_started(
            space_id=space_id,
            started_at=started_at,
        )
        repository.commit()
        return marked


def _mark_succeeded_sync(*, space_id: str, polled_at: datetime) -> bool:
    with SessionLocal() as db:
        repository = ChannelTalkDocumentCredentialsRepository(db)
        marked = repository.mark_document_poll_succeeded(
            space_id=space_id,
            polled_at=polled_at,
        )
        repository.commit()
        return marked


def _mark_failed_sync(*, space_id: str, error: str) -> bool:
    with SessionLocal() as db:
        repository = ChannelTalkDocumentCredentialsRepository(db)
        marked = repository.mark_document_poll_failed(
            space_id=space_id,
            error=error,
        )
        repository.commit()
        return marked


async def poll_channel_talk_document_incremental_changes() -> dict[str, int]:
    now = datetime.now(timezone.utc)
    stale_minutes = max(
        1,
        int(settings.CHANNEL_TALK_DOCUMENT_INCREMENTAL_POLL_STALE_MINUTES),
    )
    due_connections = await run_in_threadpool(
        _load_due_document_connections_sync,
        now=now,
        stale_started_before=now - timedelta(minutes=stale_minutes),
    )

    changed = 0
    blocked = 0
    errors = 0

    for connection in due_connections:
        started_at = datetime.now(timezone.utc)
        await run_in_threadpool(
            _mark_started_sync,
            space_id=connection.space_id,
            started_at=started_at,
        )
        try:
            changes = await _collect_document_article_changes(
                connection=connection,
                now=started_at,
            )
            if changes:
                result = await get_incremental_service().dispatch_changes(
                    changes=changes,
                )
                blocked += result.blocked_count
                changed += len(result.record_keys)
            await run_in_threadpool(
                _mark_succeeded_sync,
                space_id=connection.space_id,
                polled_at=started_at,
            )
        except Exception as exc:
            errors += 1
            logger.exception(
                "[CHANNEL_TALK][DOCUMENT_POLL] Failed to poll document space: channel_id=%s space_id=%s",
                connection.channel_id,
                connection.space_id,
            )
            await run_in_threadpool(
                _mark_failed_sync,
                space_id=connection.space_id,
                error=str(exc),
            )

    return {
        "changed": changed,
        "blocked_full_sync_required": blocked,
        "errors": errors,
    }


async def _collect_document_article_changes(
    *,
    connection: ChannelTalkDocumentCredentialsRecord,
    now: datetime,
) -> list[RecordChange]:
    lookback_start = _resolve_lookback_start(connection=connection, now=now)
    client = ChannelTalkDocumentsApiClient(
        transport=ChannelTalkDocumentsHttpClient(
            access_key=connection.access_key or "",
            access_secret=connection.access_secret or "",
            space_id=connection.space_id,
        ),
    )

    changes: list[RecordChange] = []
    for state in DEFAULT_ARTICLE_FULL_SYNC_STATES:
        next_cursor: str | None = None
        page_count = 0
        while True:
            page = await client.list_articles(
                language="ko",
                state=state,
                since=next_cursor,
                order="desc",
            )
            page_count += 1
            should_stop = False
            for article in page.articles:
                timestamp = _article_timestamp(article)
                if timestamp is None:
                    continue
                if timestamp < lookback_start:
                    should_stop = True
                    continue
                changes.append(
                    build_channel_talk_document_article_change(
                        channel_id=connection.channel_id,
                        space_id=connection.space_id,
                        article_id=article.article_id,
                        last_event_at=timestamp,
                    )
                )
            if (
                should_stop
                or page.next_page_token is None
                or page_count
                >= max(1, int(settings.CHANNEL_TALK_DOCUMENT_INCREMENTAL_MAX_PAGES))
            ):
                break
            next_cursor = page.next_page_token
    return changes


def _resolve_lookback_start(
    *,
    connection: ChannelTalkDocumentCredentialsRecord,
    now: datetime,
) -> datetime:
    overlap = timedelta(
        minutes=max(
            0,
            int(settings.CHANNEL_TALK_DOCUMENT_INCREMENTAL_LOOKBACK_OVERLAP_MINUTES),
        )
    )
    if connection.last_incremental_polled_at is not None:
        return _to_utc(connection.last_incremental_polled_at) - overlap
    return now - timedelta(hours=max(1, connection.polling_cycle_hours)) - overlap


def _article_timestamp(article: ChannelTalkDocumentArticle) -> datetime | None:
    timestamp = article.updated_at or article.published_at or article.created_at
    if timestamp is None:
        return None
    return _to_utc(timestamp)


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
