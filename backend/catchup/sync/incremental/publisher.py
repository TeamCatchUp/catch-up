from __future__ import annotations

import logging
from catchup.configs.config import settings
from catchup.db.engine import SessionLocal
from catchup.db.incremental import (
    claim_outbox_for_publish,
    complete_outbox_publish,
    complete_outbox_skip,
    fail_outbox_publish,
    get_record_state,
    list_pending_outbox_entries,
    recover_stale_outbox_claims,
    transition_record_status,
)
from catchup.db.models import IncrementalOutboxStatus, IncrementalRecordStatus, SyncConnector
from catchup.sync.common.schemas import SyncStreamTask
from catchup.sync.incremental.full_sync_guard import is_incremental_target_eligible
from catchup.sync.stream_runtime.stream_queue import publish_task

logger = logging.getLogger(__name__)


def _connector_key(connector: SyncConnector | str) -> str:
    if isinstance(connector, SyncConnector):
        return connector.value
    return str(connector).strip()


def build_incremental_event_id(record_key: str, generation: int) -> str:
    return f"inc:{record_key}:{generation}"


def build_incremental_job_id(
    *,
    connector: str,
    scope_id: str,
    parent_type: str,
    parent_id: str,
) -> str:
    return f"inc:{connector}:{scope_id}:{parent_type}:{parent_id}"


async def publish_incremental_outbox(
    *,
    connector: SyncConnector | None = None,
    limit: int | None = None,
) -> dict[str, int]:
    batch_limit = max(1, limit or int(settings.INCREMENTAL_OUTBOX_BATCH_SIZE))
    recovered = 0

    with SessionLocal() as db:
        # PUBLISHING STALE SECONDS 보다 오래 publishing 상태에서 머문 이벤트를 failed 처리
        recovered = recover_stale_outbox_claims(
            db,
            stale_seconds=max(1, int(settings.INCREMENTAL_OUTBOX_PUBLISHING_STALE_SECONDS)),
            connector=connector,
            limit=batch_limit,
        )
        outbox_entries = list_pending_outbox_entries(
            db,
            connector=connector,
            statuses=[IncrementalOutboxStatus.PENDING, IncrementalOutboxStatus.FAILED],
            limit=batch_limit,
        )

    published = 0
    blocked = 0
    skipped = 0
    errors = 0

    for entry in outbox_entries:
        try:
            with SessionLocal() as db:
                #  publishing으로 상태 전이
                if not claim_outbox_for_publish(db, outbox_id=entry.id):
                    skipped += 1
                    continue
                
                record = get_record_state(db, entry.record_key)
                if record is None:
                    if complete_outbox_skip(
                        db,
                        outbox_id=entry.id,
                        last_error="record_not_found",
                    ):
                        skipped += 1
                    continue

                if record.generation != entry.generation or record.status != IncrementalRecordStatus.QUEUED:
                    if complete_outbox_skip(
                        db,
                        outbox_id=entry.id,
                        last_error="stale_outbox",
                    ):
                        skipped += 1
                    continue

                connector_key = _connector_key(record.connector)

                if not is_incremental_target_eligible(
                    db,
                    connector=connector_key,
                    scope_id=record.scope_id,
                    target_type=record.parent_type,
                    target_id=record.parent_id,
                ):
                    transition_record_status(
                        db,
                        record_key=record.record_key,
                        from_statuses=[IncrementalRecordStatus.QUEUED],
                        to_status=IncrementalRecordStatus.DEAD,
                        expected_generation=record.generation,
                        attempt=int(record.attempt),
                        last_error="full_sync_required",
                    )
                    if complete_outbox_skip(
                        db,
                        outbox_id=entry.id,
                        last_error="full_sync_required",
                    ):
                        blocked += 1
                        logger.info(
                            "[INCREMENTAL][PUBLISH] Skipped due to missing full sync: connector=%s, scope_id=%s, parent_type=%s, parent_id=%s, record_key=%s, generation=%s",
                            connector_key,
                            record.scope_id,
                            record.parent_type,
                            record.parent_id,
                            record.record_key,
                            record.generation,
                        )
                    else:
                        skipped += 1
                    continue

                task = SyncStreamTask.incremental(
                    event_id=build_incremental_event_id(record.record_key, record.generation),
                    job_id=build_incremental_job_id(
                        connector=connector_key,
                        scope_id=record.scope_id,
                        parent_type=record.parent_type,
                        parent_id=record.parent_id,
                    ),
                    connector=connector_key,
                    scope_id=record.scope_id,
                    target_type=record.parent_type,
                    target_id=record.parent_id,
                    record_key=record.record_key,
                    generation=record.generation,
                    record_type=record.record_type,
                    record_id=record.record_id,
                    parent_type=record.parent_type,
                    parent_id=record.parent_id,
                    event_kind=record.event_kind,
                    last_event_at=record.last_event_at.isoformat(),
                    attempt=max(1, int(entry.attempt)),
                    max_attempts=max(1, int(settings.INCREMENTAL_MAX_ATTEMPTS)),
                )

            message_id = await publish_task(task)

            with SessionLocal() as db:
                if complete_outbox_publish(
                    db,
                    outbox_id=entry.id,
                    stream_message_id=message_id,
                    last_error=None,
                ):
                    published += 1
                    continue

            skipped += 1
        except Exception as exc:
            logger.exception(
                "[INCREMENTAL][PUBLISH] Failed to publish outbox: outbox_id=%s, record_key=%s, generation=%s",
                entry.id,
                entry.record_key,
                entry.generation,
            )
            with SessionLocal() as db:
                fail_outbox_publish(
                    db,
                    outbox_id=entry.id,
                    last_error=str(exc),
                )
            errors += 1

    return {
        "published": published,
        "blocked_full_sync_required": blocked,
        "skipped": skipped,
        "errors": errors,
        "recovered": recovered,
    }
