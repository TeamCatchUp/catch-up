"""
APScheduler for Hourly Sync
"""

import logging
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from catchup.configs.config import settings
from catchup.db.engine import SessionLocal
from catchup.connectors.jira.dynamic_webhook_service import get_jira_dynamic_webhook_service
from catchup.db.atlassian.oauth_repository import get_all_tokens as get_all_atlassian_tokens
from catchup.connectors.atlassian.oauth_client import AtlassianOAuthClient
from catchup.sync.incremental import (
    poll_confluence_incremental_changes,
    promote_incremental_records,
    publish_incremental_outbox,
)
from catchup.db.incremental import recover_stale_processing_records

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


async def refresh_jira_dynamic_webhooks():
    """
    Jira Dynamic Webhook 등록 상태 보장 및 만료 갱신
    """
    logger.info("[JIRA][WEBHOOK][DYNAMIC] Starting webhook refresh job")
    dynamic_webhook_service = get_jira_dynamic_webhook_service()

    with SessionLocal() as db:
        tokens = get_all_atlassian_tokens(db)

        for token in tokens:
            cloud_id = token.cloud_id
            try:
                result = await dynamic_webhook_service.ensure_registered(
                    db=db,
                    cloud_id=cloud_id,
                )
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
    30분 간격으로 Atlassian Access Token을 갱신함.
    """
    logger.info("[ATLASSIAN][TOKEN] Starting Token Refresh Job")

    oauth_client = AtlassianOAuthClient()

    with SessionLocal() as db:
        tokens = get_all_atlassian_tokens(db)

        if not tokens:
            logger.debug("[ATLASSIAN][TOKEN] No Atlassian Tokens Found")
            return
        
        refreshed_count = 0
        for token in tokens:
            cloud_id = token.cloud_id
            try:
                new_tokens = await oauth_client.refresh_access_token(token.refresh_token)

                token.access_token = new_tokens.access_token
                token.refresh_token = new_tokens.refresh_token
                token.expires_at = datetime.now(timezone.utc) + timedelta(seconds=new_tokens.expires_in)
                db.commit()

                refreshed_count += 1
                logger.info(
                    f"[ATLASSIAN][TOKEN] Token Refreshed : cloud_id = {cloud_id}"
                )
            except Exception as e:
                db.rollback()
                logger.error(
                    "[ATLASSIAN][TOKEN] Token refresh failed: cloud_id=%s, error=%s",
                    cloud_id, e,
                    exc_info=True,
                )
    logger.info(
        "[ATLASSIAN][TOKEN] Token Refresh Job Completed"
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

    _scheduler = AsyncIOScheduler()
    token_refresh_minutes = settings.ATLASSIAN_TOKEN_REFRESH_INTERVAL_MINUTES

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
        trigger=CronTrigger(minute=f"*/{token_refresh_minutes}"),
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
        "[SCHEDULER][INIT] Scheduler initialized: jira_webhook_refresh=%s, token_refresh_minutes=%s, incremental_interval_minutes=%s, confluence_poll_interval_minutes=%s",
        jira_webhook_refresh_hours,
        token_refresh_minutes,
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
