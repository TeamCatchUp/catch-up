"""
APScheduler for Hourly Sync
"""

import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from catchup.audit.enums import AuditEventStatus, AuditLevel
from catchup.audit.metadata import IntegrationAuditMetadata
from catchup.audit.service import emit_audit_event
from catchup.connectors.atlassian.exceptions import (
    AtlassianAuthError,
    AtlassianTokenExpiredError,
)
from catchup.connectors.atlassian.oauth_client import AtlassianOAuthClient
from catchup.configs.config import settings
from catchup.db.atlassian.oauth_repository import (
    get_all_tokens as get_all_atlassian_tokens,
    update_refreshed_token as update_atlassian_refreshed_token,
)
from catchup.db.engine import SessionLocal
from catchup.connectors.jira.dynamic_webhook_service import get_jira_dynamic_webhook_service
from catchup.events.enums import EventType, IntegrationEventAction
from catchup.sync.incremental import (
    poll_confluence_incremental_changes,
    promote_incremental_records,
    publish_incremental_outbox,
)
from catchup.db.incremental import recover_stale_processing_records

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None
SEOUL_TZ = ZoneInfo("Asia/Seoul")


async def refresh_jira_dynamic_webhooks():
    """
    Jira Dynamic Webhook 등록 상태 보장 및 만료 갱신
    """
    logger.info("[JIRA][WEBHOOK][DYNAMIC] Starting webhook refresh job")
    dynamic_webhook_service = get_jira_dynamic_webhook_service()

    with SessionLocal() as db:
        cloud_ids = [token.cloud_id for token in get_all_atlassian_tokens(db)]

    for cloud_id in cloud_ids:
        try:
            result = await dynamic_webhook_service.ensure_registered(cloud_id=cloud_id)
            logger.info(
                f"[JIRA][WEBHOOK][DYNAMIC] Processed cloud: cloud_id={cloud_id}, result={result}"
            )
        except Exception as e:
            logger.error(
                f"[JIRA][WEBHOOK][DYNAMIC] Failed to process cloud: "
                f"cloud_id={cloud_id}, error={e}",
                exc_info=True,
            )

    logger.info("[JIRA][WEBHOOK][DYNAMIC] Webhook refresh job completed")

async def refresh_atlassian_tokens():
    """
    매일 자정(Asia/Seoul)에 Atlassian Access Token을 갱신함.
    """
    oauth_client = AtlassianOAuthClient()

    with SessionLocal() as db:
        tokens = get_all_atlassian_tokens(db)

        for token in tokens:
            cloud_id = token.cloud_id
            emit_audit_event(
                event_type=EventType.INTEGRATION,
                event_action=IntegrationEventAction.OAUTH_REFRESH,
                event_status=AuditEventStatus.ATTEMPT,
                level=AuditLevel.INFO,
                metadata=IntegrationAuditMetadata(
                    context=f"atlassian_oauth_refresh:cloud_id={cloud_id}",
                    provider="atlassian",
                ),
                immediate=True,
            )
            try:
                new_tokens = await oauth_client.refresh_access_token(token.refresh_token)
                update_atlassian_refreshed_token(
                    db=db,
                    cloud_id=cloud_id,
                    access_token=new_tokens.access_token,
                    refresh_token=new_tokens.refresh_token,
                    expires_at=datetime.now(timezone.utc) + timedelta(seconds=new_tokens.expires_in),
                )
            except AtlassianTokenExpiredError:
                db.rollback()
                emit_audit_event(
                    event_type=EventType.INTEGRATION,
                    event_action=IntegrationEventAction.OAUTH_REFRESH,
                    event_status=AuditEventStatus.FAIL,
                    level=AuditLevel.WARNING,
                    metadata=IntegrationAuditMetadata(
                        context=f"atlassian_oauth_refresh:cloud_id={cloud_id}",
                        provider="atlassian",
                    ),
                    immediate=True,
                )
            except AtlassianAuthError:
                db.rollback()
                emit_audit_event(
                    event_type=EventType.INTEGRATION,
                    event_action=IntegrationEventAction.OAUTH_REFRESH,
                    event_status=AuditEventStatus.FAIL,
                    level=AuditLevel.WARNING,
                    metadata=IntegrationAuditMetadata(
                        context=f"atlassian_oauth_refresh:cloud_id={cloud_id}",
                        provider="atlassian",
                    ),
                    immediate=True,
                )
            except Exception as e:
                db.rollback()
                emit_audit_event(
                    event_type=EventType.INTEGRATION,
                    event_action=IntegrationEventAction.OAUTH_REFRESH,
                    event_status=AuditEventStatus.FAIL,
                    level=AuditLevel.ERROR,
                    metadata=IntegrationAuditMetadata(
                        context=f"atlassian_oauth_refresh:cloud_id={cloud_id}",
                        provider="atlassian",
                    ),
                    immediate=True,
                )
                logger.error(
                    "[ATLASSIAN][TOKEN] token_refresh_unexpected_error cloud_id=%s error=%s",
                    cloud_id,
                    e,
                    exc_info=True,
                )


async def run_incremental_runtime_jobs():
    logger.info("[INCREMENTAL][SCHEDULER] Starting promoter/publisher cycle")
    with SessionLocal() as db:
        recovered_processing = recover_stale_processing_records(
            db,
            stale_seconds=max(1, int(settings.SYNC_LOCK_CHANNEL_TTL_SECONDS)),
        )
    promote_result = promote_incremental_records()
    publish_result = await publish_incremental_outbox()
    logger.info(
        "[INCREMENTAL][SCHEDULER] Runtime cycle completed: recovered_processing=%s promote=%s publish=%s",
        recovered_processing,
        promote_result,
        publish_result,
    )


async def poll_confluence_incremental():
    logger.info("[CONFLUENCE][POLL] Starting incremental poll")
    result = await poll_confluence_incremental_changes()
    logger.info("[CONFLUENCE][POLL] Incremental poll completed: result=%s", result)



def init_scheduler():
    global _scheduler
    if _scheduler is not None:
        logger.warning("Scheduler already Initialized")
        return

    _scheduler = AsyncIOScheduler(timezone=SEOUL_TZ)

    jira_webhook_refresh_hours = settings.JIRA_WEBHOOK_REFRESH_INTERVAL_HOURS
    _scheduler.add_job(
        refresh_jira_dynamic_webhooks,
        trigger=CronTrigger(
            hour=f"*/{jira_webhook_refresh_hours}",
            minute=20,
        ),
        id="jira_dynamic_webhook_refresh",
        name="Jira Dynamic Webhook Refresh",
        replace_existing=True,
        misfire_grace_time=300,
    )

    _scheduler.add_job(
        refresh_atlassian_tokens,
        trigger=CronTrigger(hour=0, minute=0, timezone=SEOUL_TZ),
        id="atlassian_token_refresh",
        name="Atlassian OAuth Token Refresh",
        replace_existing=True,
        misfire_grace_time = 300,
    )

    incremental_interval_minutes = settings.INCREMENTAL_RUNTIME_INTERVAL_MINUTES
    _scheduler.add_job(
        run_incremental_runtime_jobs,
        trigger=CronTrigger(minute=f"*/{incremental_interval_minutes}"),
        id="incremental_runtime_cycle",
        name="Incremental Runtime Cycle",
        replace_existing=True,
        misfire_grace_time=60,
    )

    confluence_poll_interval_minutes = settings.CONFLUENCE_INCREMENTAL_POLL_INTERVAL_MINUTES
    _scheduler.add_job(
        poll_confluence_incremental,
        trigger=CronTrigger(minute=f"*/{confluence_poll_interval_minutes}"),
        id="confluence_incremental_poll",
        name="Confluence Incremental Poll",
        replace_existing=True,
        misfire_grace_time=120,
    )
    
    _scheduler.start()
    logger.info(
        "[SCHEDULER][INIT] Scheduler initialized: jira_webhook_refresh=%s, token_refresh=%s, incremental_interval_minutes=%s, confluence_poll_interval_minutes=%s",
        jira_webhook_refresh_hours,
        "daily 00:00 Asia/Seoul",
        incremental_interval_minutes,
        confluence_poll_interval_minutes,
    )


def shutdown_scheduler():
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=True)
        _scheduler = None
        logger.info("Scheduler Shut Down")


def get_scheduler() -> AsyncIOScheduler | None:
    return _scheduler
