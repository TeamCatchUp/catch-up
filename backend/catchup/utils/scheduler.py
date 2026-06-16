"""
APScheduler for Hourly Sync
"""

import asyncio
import logging
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from catchup.agents.triggers.publisher import publish_pending_agent_trigger_outbox
from catchup.agents.triggers.recovery import recover_stale_agent_trigger_executions
from catchup.agents.triggers.recovery import scan_and_dispatch_due_debounce_runs
from catchup.audit.enums import AuditEventStatus
from catchup.audit.enums import AuditLevel
from catchup.audit.metadata import IntegrationAuditMetadata
from catchup.audit.service import emit_audit_event
from catchup.configs.config import settings
from catchup.connectors.atlassian.exceptions import AtlassianAuthError
from catchup.connectors.atlassian.exceptions import AtlassianTokenExpiredError
from catchup.connectors.atlassian.oauth_client import AtlassianOAuthClient
from catchup.connectors.jira.dynamic_webhook_service import (
    get_jira_dynamic_webhook_service,
)
from catchup.db.atlassian.oauth_repository import (
    get_all_tokens as get_all_atlassian_tokens,
)
from catchup.db.atlassian.oauth_repository import (
    update_refreshed_token as update_atlassian_refreshed_token,
)
from catchup.db.engine import SessionLocal
from catchup.db.incremental import recover_stale_processing_records
from catchup.events.enums import EventType
from catchup.events.enums import IntegrationEventAction
from catchup.sync.backfill.github_issue_v2 import GithubIssueV2BackfillService
from catchup.sync.backfill.github_pr_v2 import GithubPrV2BackfillService
from catchup.sync.backfill.jira_issue_v2 import JiraIssueV2BackfillService
from catchup.sync.backfill.slack_message_v2 import SlackMessageV2BackfillService
from catchup.sync.incremental import get_incremental_service
from catchup.sync.incremental.dead_record_recovery import (
    recover_incremental_dead_records,
)

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
            result = await dynamic_webhook_service.ensure_registered(
                cloud_id=cloud_id,
                source="cron_job",
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
    service = get_incremental_service()
    promote_result = service.promote_records()
    publish_result = await service.publish_outbox()
    logger.info(
        "[INCREMENTAL][SCHEDULER] Runtime cycle completed: recovered_processing=%s promote=%s publish=%s",
        recovered_processing,
        promote_result,
        publish_result,
    )


async def recover_incremental_dead_records_job():
    logger.info("[INCREMENTAL][DEAD][SCHEDULER] Starting dead record recovery cycle")
    result = await recover_incremental_dead_records()
    logger.info(
        "[INCREMENTAL][DEAD][SCHEDULER] Dead record recovery cycle completed: result=%s",
        result.to_log_fields(),
    )


async def run_agent_trigger_recovery_jobs():
    logger.info("[AGENT_TRIGGER][SCHEDULER] Starting recovery cycle")
    due_count, outbox_count, stale_execution_count = await asyncio.to_thread(
        _run_agent_trigger_recovery_jobs_sync
    )
    logger.info(
        "[AGENT_TRIGGER][SCHEDULER] Recovery cycle completed: due=%s outbox=%s stale_execution=%s",
        due_count,
        outbox_count,
        stale_execution_count,
    )


def _run_agent_trigger_recovery_jobs_sync() -> tuple[int, int, int]:
    """스케줄러 thread 안에서 Trigger recovery용 DB 세션을 짧게 소유한다."""
    with SessionLocal() as db:
        due_count = scan_and_dispatch_due_debounce_runs(db=db)
        outbox_count = publish_pending_agent_trigger_outbox(db=db)
        stale_execution_count = recover_stale_agent_trigger_executions(db=db)
        return due_count, outbox_count, stale_execution_count


async def poll_confluence_incremental():
    logger.info("[CONFLUENCE][POLL] Starting incremental poll")
    result = await get_incremental_service().poll_confluence_changes()
    logger.info("[CONFLUENCE][POLL] Incremental poll completed: result=%s", result)


async def poll_channel_talk_document_incremental():
    logger.info("[CHANNEL_TALK][DOCUMENT_POLL] Starting incremental poll")
    result = await get_incremental_service().poll_channel_talk_document_changes()
    logger.info(
        "[CHANNEL_TALK][DOCUMENT_POLL] Incremental poll completed: result=%s",
        result,
    )


async def run_github_pr_v2_backfill_job():
    logger.info("[GITHUB][PR_V2_BACKFILL][SCHEDULER] Starting backfill batch")
    service = GithubPrV2BackfillService()
    result = await service.backfill_batch(
        limit=settings.VECTOR_STORE_V2_BACKFILL_BATCH_SIZE,
    )
    logger.info(
        "[GITHUB][PR_V2_BACKFILL][SCHEDULER] Backfill batch completed: scanned=%s succeeded=%s skipped=%s failed=%s",
        result.scanned,
        result.succeeded,
        result.skipped,
        result.failed,
    )


async def run_github_issue_v2_backfill_job():
    logger.info("[GITHUB][ISSUE_V2_BACKFILL][SCHEDULER] Starting backfill batch")
    service = GithubIssueV2BackfillService()
    result = await service.backfill_batch(
        limit=settings.VECTOR_STORE_V2_BACKFILL_BATCH_SIZE,
    )
    logger.info(
        "[GITHUB][ISSUE_V2_BACKFILL][SCHEDULER] Backfill batch completed: scanned=%s succeeded=%s skipped=%s failed=%s",
        result.scanned,
        result.succeeded,
        result.skipped,
        result.failed,
    )


async def run_slack_message_v2_backfill_job():
    logger.info("[SLACK][MESSAGE_V2_BACKFILL][SCHEDULER] Starting backfill batch")
    service = SlackMessageV2BackfillService()
    result = await service.backfill_batch(
        limit=settings.VECTOR_STORE_V2_BACKFILL_BATCH_SIZE,
    )
    logger.info(
        "[SLACK][MESSAGE_V2_BACKFILL][SCHEDULER] Backfill batch completed: scanned=%s succeeded=%s skipped=%s failed=%s",
        result.scanned,
        result.succeeded,
        result.skipped,
        result.failed,
    )


async def run_jira_issue_v2_backfill_job():
    logger.info("[JIRA][ISSUE_V2_BACKFILL][SCHEDULER] Starting backfill batch")
    service = JiraIssueV2BackfillService()
    result = await service.backfill_batch(
        limit=settings.VECTOR_STORE_V2_BACKFILL_BATCH_SIZE,
    )
    logger.info(
        "[JIRA][ISSUE_V2_BACKFILL][SCHEDULER] Backfill batch completed: scanned=%s succeeded=%s skipped=%s failed=%s",
        result.scanned,
        result.succeeded,
        result.skipped,
        result.failed,
    )


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

    _scheduler.add_job(
        recover_incremental_dead_records_job,
        trigger=CronTrigger(minute=0, timezone=SEOUL_TZ),
        id="incremental_dead_record_recovery",
        name="Incremental Dead Record Recovery",
        replace_existing=True,
        misfire_grace_time=300,
    )

    _scheduler.add_job(
        run_agent_trigger_recovery_jobs,
        trigger=CronTrigger(minute="*/1", timezone=SEOUL_TZ),
        id="agent_trigger_recovery",
        name="Agent Trigger Recovery",
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

    channel_talk_document_due_scan_interval_minutes = (
        settings.CHANNEL_TALK_DOCUMENT_DUE_SCAN_INTERVAL_MINUTES
    )
    _scheduler.add_job(
        poll_channel_talk_document_incremental,
        trigger=CronTrigger(
            minute=f"*/{channel_talk_document_due_scan_interval_minutes}"
        ),
        id="channel_talk_document_incremental_poll",
        name="Channel Talk Document Incremental Due Scan",
        replace_existing=True,
        misfire_grace_time=120,
    )

    # TODO : 시작 시점만 정하고 각 Job 종료 이후에 다음 Job이 시작되도록 변경 고려 (현재는 각 Job이 독립적으로 실행되어 동시에 여러 Job이 실행될 수 있음)
    if settings.VECTOR_STORE_V2_BACKFILL_SCHEDULE_ENABLED:
        _scheduler.add_job(
            run_github_pr_v2_backfill_job,
            trigger=CronTrigger(hour=4, minute=15, timezone=SEOUL_TZ),
            id="github_pr_v2_backfill",
            name="GitHub PR v2 Backfill",
            replace_existing=True,
            misfire_grace_time=900,
        )
        _scheduler.add_job(
            run_github_issue_v2_backfill_job,
            trigger=CronTrigger(hour=6, minute=40, timezone=SEOUL_TZ),
            id="github_issue_v2_backfill",
            name="GitHub Issue v2 Backfill",
            replace_existing=True,
            misfire_grace_time=900,
        )
        _scheduler.add_job(
            run_slack_message_v2_backfill_job,
            trigger=CronTrigger(hour=12, minute=50, timezone=SEOUL_TZ),
            id="slack_message_v2_backfill",
            name="Slack Message v2 Backfill",
            replace_existing=True,
            misfire_grace_time=900,
        )
        _scheduler.add_job(
            run_jira_issue_v2_backfill_job,
            trigger=CronTrigger(hour=21, minute=15, timezone=SEOUL_TZ),
            id="jira_issue_v2_backfill",
            name="Jira Issue v2 Backfill",
            replace_existing=True,
            misfire_grace_time=900,
        )
    
    _scheduler.start()
    logger.info(
        "[SCHEDULER][INIT] Scheduler initialized: jira_webhook_refresh=%s, token_refresh=%s, incremental_interval_minutes=%s, confluence_poll_interval_minutes=%s, channel_talk_document_due_scan_interval_minutes=%s",
        jira_webhook_refresh_hours,
        "daily 00:00 Asia/Seoul",
        incremental_interval_minutes,
        confluence_poll_interval_minutes,
        channel_talk_document_due_scan_interval_minutes,
    )


def shutdown_scheduler():
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=True)
        _scheduler = None
        logger.info("Scheduler Shut Down")


def get_scheduler() -> AsyncIOScheduler | None:
    return _scheduler
