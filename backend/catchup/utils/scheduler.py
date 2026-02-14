"""
APScheduler for Hourly Sync
"""

import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session

from catchup.db.engine import SessionLocal
from catchup.utils.webhook_buffer import get_webhook_buffer
from catchup.connectors.github.factory import create_github_ingestion_service
from catchup.connectors.github.schemas import IncrementalSyncRequest
from catchup.connectors.slack.factory import create_slack_ingestion_service
from catchup.db.github.installation_repository import get_all_installations
from catchup.db.slack.oauth_repository import get_all_slack_tokens
from catchup.db.jira.oauth_repository import get_all_jira_tokens
from catchup.configs.config import settings

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None

async def flush_github_events():
    """
    APScheduler가 정각에 실행하는 메인 함수
    Redis에 버퍼링 된 Github Webhook 이벤트를 처리하고, Incremental Sync를 수행
    """
    logger.info("Starting Github Webhook Flush")

    # Redis 버퍼 인스턴스 가져오기
    buffer = get_webhook_buffer()

    # 데이터베이스 세션 개설
    with SessionLocal() as db:
        installations = get_all_installations(db)

        # 각 Installation에 대해서 순회하며 이벤트 처리
        for installation in installations:
            # Suspended Installation Check
            if installation.suspended_at:
                logger.debug(f"Skipping Suspended Installation {installation.installation_id}")
                continue
        
            installation_id = installation.installation_id

            try:
                # Redis에 버퍼링 중인 이벤트가 있는 Repository 조회
                repos_with_events = await buffer.get_github_buffered_repos(installation_id)

                # Event가 없는 Installation은 Skip
                if not repos_with_events:
                    logger.debug(f"No Buffered events for installation {installation_id}")
                    continue
                
                # Repository별 Entity-Type으로 그룹화
                repos_to_sync = {}
                for repo_id, entity_type in repos_with_events:
                    if repo_id not in repos_to_sync:
                        repos_to_sync[repo_id] = set()
                    repos_to_sync[repo_id].add(entity_type)
                
                logger.info(
                    f"Flushing Github Events for Installation {installation_id}: "
                    f"{len(repos_to_sync)} repos affected"
                )

                service = await create_github_ingestion_service(db, installation_id)

                for repo_id, entity_types in repos_to_sync.items():
                    try:
                        # Entity-Type별로 Buffer Clear (동기화 실행중에 도착한 Event는 다음 TTL에 처리)
                        for entity_type in entity_types:
                            event_count = await buffer.clear_github_buffer(
                                installation_id, repo_id, entity_type
                            )
                            logger.info(f"Cleared {event_count} {entity_type} events for repo {repo_id}")

                        # Repository 단위로 Incremental Sync 수행
                        sync_request = IncrementalSyncRequest(
                            repo_ids=[repo_id],
                            entity_types=entity_types,
                            update_repos=False,
                        )
                        result = await service.incremental_sync(db, sync_request)
                        logger.info(f"Github Incremental Sync Result for repo {repo_id}: {result}")

                    # Repository 단위 Error Handling
                    except Exception as e:
                        logger.error(f"Failed to Sync Repo {repo_id}: {e}", exc_info=True)
            
            # Installation 단위 Error Handling
            except Exception as e:
                logger.error(
                    f"Failed to flush events for installation {installation_id} : {e}",
                    exc_info = True
                )
    logger.info("Github Webhook Flush Completed")

async def flush_slack_events():
    logger.info("Starting Slack Webhook Flush")
    buffer = get_webhook_buffer()

    with SessionLocal() as db:
        tokens = get_all_slack_tokens(db)

        for token in tokens:
            team_id = token.team_id

            try:
                channels_with_events = await buffer.get_slack_buffered_channels(team_id)

                if not channels_with_events:
                    logger.debug(f"No Buffered Events for Slack team {team_id}")
                    continue

                logger.info(
                    f"Flushing Slack Events for Team {team_id}: "
                    f"{len(channels_with_events)} channels affected"
                )

                # Create service instance
                service = await create_slack_ingestion_service(db, team_id)

                for channel_id in channels_with_events:
                    try:
                        event_count = await buffer.clear_slack_buffer(team_id, channel_id)
                        logger.info(
                            f"Cleared {event_count} message events for channel {channel_id}"
                        )
                    except Exception as e:
                        logger.error(
                            f"Failed to Clear Buffer for Channel {channel_id}: {e}",
                            exc_info=True
                        )

                try:
                    result = await service.incremental_sync(db)
                    logger.info(f"Slack incremental sync result for team {team_id}: {result}")
                except Exception as e:
                    logger.error(f"Failed to sync Slack team {team_id}: {e}", exc_info=True)

            except Exception as e:
                logger.error(
                    f"Failed to Flush Events for Slack Team {team_id}: {e}",
                    exc_info=True
                )

    logger.info("Slack Webhook Flush Completed")


async def flush_jira_events():
    logger.info("Starting Jira webhook flush job")
    buffer = get_webhook_buffer()

    with SessionLocal() as db:
        tokens = get_all_jira_tokens(db)

        for token in tokens:
            cloud_id = token.cloud_id

            try:
                projects_with_events = await buffer.get_jira_buffered_projects(cloud_id)

                if not projects_with_events:
                    logger.debug(f"No buffered events for Jira cloud {cloud_id}")
                    continue

                logger.info(
                    f"Flushing Jira events for cloud {cloud_id}: "
                    f"{len(projects_with_events)} projects affected"
                )


                # Clear buffer for each project
                for project_key in projects_with_events:
                    try:
                        event_count = await buffer.clear_jira_buffer(cloud_id, project_key)
                        logger.info(
                            f"Cleared {event_count} issue events for project {project_key}"
                        )
                    except Exception as e:
                        logger.error(
                            f"Failed to clear buffer for project {project_key}: {e}",
                            exc_info=True
                        )

                # try:
                #     result = await service.incremental_sync(db)
                #     logger.info(f"Jira incremental sync result for cloud {cloud_id}: {result}")
                # except Exception as e:
                #     logger.error(f"Failed to sync Jira cloud {cloud_id}: {e}", exc_info=True)

                logger.warning(
                    f"Jira incremental sync skipped for cloud {cloud_id}: "
                    "Incremental sync path is disabled"
                )

            except Exception as e:
                logger.error(
                    f"Failed to flush events for Jira cloud {cloud_id}: {e}",
                    exc_info=True
                )

    logger.info("Jira webhook flush job completed")


def init_scheduler():

    global _scheduler

    if not settings.WEBHOOK_ENABLE_AUTO_SYNC:
        logger.info("Auto Sync is Disabled in Settings")
        return
    
    if _scheduler is not None:
        logger.warning("Scheduler already Initialized")
        return

    _scheduler = AsyncIOScheduler()

    interval_hours = settings.WEBHOOK_FLUSH_INTERVAL_HOURS

    # TODO:
    # Jira token lifecycle 보장을 위해 별도 주기 작업 추가 필요

    _scheduler.add_job(
        flush_github_events,
        trigger = CronTrigger(hour=f"*/{interval_hours}", minute = 0),
        id="github_webhook_flush",
        name= "Github Webhook Event Flush",
        replace_existing = True,
        misfire_grace_time = 300, 
    )

    _scheduler.add_job(
        flush_slack_events,
        trigger=CronTrigger(hour=f"*/{interval_hours}", minute=0),
        id="slack_webhook_flush",
        name="Slack Webhook Event Flush",
        replace_existing=True,
        misfire_grace_time=300,
    )

    _scheduler.add_job(
        flush_jira_events,
        trigger=CronTrigger(hour=f"*/{interval_hours}", minute=0),
        id="jira_webhook_flush",
        name="Jira Webhook Event Flush",
        replace_existing=True,
        misfire_grace_time=300,
    )

    _scheduler.start()
    logger.info(f"Scheduler initialized with {interval_hours}-hour interval")


def shutdown_scheduler():
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=True)
        _scheduler = None
        logger.info("Scheduler Shut Down")

def get_scheduler() -> AsyncIOScheduler | None:
    return _scheduler
