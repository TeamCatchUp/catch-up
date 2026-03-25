"""Jira metadata refresh 전담 모듈.

users, projects, sprints를 RDBMS snapshot으로 동기화한다.
"""

import asyncio

import structlog
from fastapi.concurrency import run_in_threadpool

from catchup.connectors.atlassian.utils import parse_atlassian_datetime
from catchup.connectors.jira.client import JiraApiError
from catchup.connectors.jira.client import JiraRateLimitError
from catchup.connectors.jira.runtime import JiraRuntime
from catchup.configs.config import settings
from catchup.db.engine import SessionLocal
from catchup.db.jira import domain_repository as jira_entities

logger = structlog.get_logger()


class JiraMetadataSyncService:
    """Jira metadata snapshot 동기화"""

    def __init__(self, runtime: JiraRuntime):
        self.runtime = runtime

    async def sync_metadata(
        self,
        project_keys: list[str] | None = None,
        *,
        raise_on_error: bool = False,
    ) -> dict[str, dict[str, int]]:
        """users/projects/sprints 순서로 동기화"""
        results = {
            "users": {"synced": 0, "errors": 0},
            "projects": {"synced": 0, "errors": 0},
            "sprints": {"synced": 0, "errors": 0},
        }

        user_results = await self._sync_all_users()
        if raise_on_error and user_results["errors"] > 0:
            raise RuntimeError(
                f"jira user metadata refresh failed: cloud_id={self.runtime.cloud_id}"
            )

        project_results = await self._sync_all_projects(project_keys)
        if raise_on_error and project_results["errors"] > 0:
            raise RuntimeError(
                f"jira project metadata refresh failed: cloud_id={self.runtime.cloud_id}"
            )

        results["users"] = user_results
        results["projects"] = project_results

        if await self.runtime.client.is_agile_available():
            sprint_results = await self._sync_all_sprints()
            results["sprints"] = sprint_results
            if raise_on_error and sprint_results["errors"] > 0:
                raise RuntimeError(
                    f"jira sprint metadata refresh failed: cloud_id={self.runtime.cloud_id}"
                )

        return results

    async def _sync_all_projects(
        self,
        project_keys: list[str] | None = None,
    ) -> dict[str, int]:
        """접근 가능한 Jira project snapshot을 저장"""
        results = {"synced": 0, "errors": 0}
        projects_data: list[dict] = []

        def _persist_projects_db() -> dict[str, int]:
            with SessionLocal() as db:
                try:
                    result = jira_entities.sync_projects_snapshot(
                        db,
                        self.runtime.cloud_id,
                        projects_data,
                    )
                    db.commit()
                    return result
                except Exception:
                    db.rollback()
                    raise

        try:
            if project_keys:
                keys_to_sync = project_keys
            else:
                all_projects = await self.runtime.client.get_all_projects()
                keys_to_sync = [p.get("key") for p in all_projects if p.get("key")]
                logger.info(
                    "jira_metadata_projects_discovered",
                    cloud_id=self.runtime.cloud_id,
                    project_count=len(keys_to_sync),
                )

            for project_key in keys_to_sync:
                try:
                    project_data = await self.runtime.client.get_project(
                        project_key,
                        expand="description,lead",
                    )
                    lead = project_data.get("lead", {})
                    url = f"{self.runtime.site_url}/projects/{project_key}"

                    projects_data.append(
                        {
                            "cloud_id": self.runtime.cloud_id,
                            "project_key": project_key,
                            "project_id": project_data.get("id", ""),
                            "project_name": project_data.get("name", ""),
                            "description": project_data.get("description"),
                            "project_type": project_data.get("projectTypeKey"),
                            "lead_account_id": lead.get("accountId"),
                            "lead_display_name": lead.get("displayName"),
                            "url": url,
                        }
                    )
                    results["synced"] += 1
                except JiraRateLimitError:
                    raise
                except JiraApiError as exc:
                    logger.error(
                        "jira_metadata_project_sync_failed",
                        cloud_id=self.runtime.cloud_id,
                        project_key=project_key,
                        error=str(exc),
                    )
                    results["errors"] += 1

                await asyncio.sleep(settings.JIRA_API_RATE_LIMIT_DELAY)

            sync_result = await run_in_threadpool(_persist_projects_db)
            logger.info(
                "jira_metadata_project_snapshot_synced",
                cloud_id=self.runtime.cloud_id,
                upserted=sync_result["upserted"],
                deleted=sync_result["deleted"],
            )
        except JiraRateLimitError:
            raise
        except JiraApiError as exc:
            logger.error(
                "jira_metadata_project_list_failed",
                cloud_id=self.runtime.cloud_id,
                error=str(exc),
            )
            results["errors"] += 1
        except Exception as exc:
            logger.error(
                "jira_metadata_project_sync_db_failed",
                cloud_id=self.runtime.cloud_id,
                error=str(exc),
            )
            results["errors"] += 1

        logger.info(
            "jira_metadata_project_sync_completed",
            cloud_id=self.runtime.cloud_id,
            results=results,
        )
        return results

    async def _sync_all_sprints(self) -> dict[str, int]:
        """sprint snapshot을 저장"""
        results = {"synced": 0, "errors": 0}
        sprints_data: list[dict] = []

        def _persist_sprints_db() -> int:
            with SessionLocal() as db:
                try:
                    result = jira_entities.upsert_sprints_bulk(
                        db,
                        sprints_data,
                    )
                    db.commit()
                    return result
                except Exception:
                    db.rollback()
                    raise

        try:
            boards = await self.runtime.client.get_boards()

            for board in boards:
                board_id = board.get("id")
                project_key = board.get("location", {}).get("projectKey")

                try:
                    sprints_response = await self.runtime.client.get_board_sprints(board_id)
                    sprints = sprints_response.get("values", [])

                    for sprint_data in sprints:
                        sprints_data.append(
                            {
                                "cloud_id": self.runtime.cloud_id,
                                "sprint_id": sprint_data.get("id"),
                                "sprint_name": sprint_data.get("name", ""),
                                "state": sprint_data.get("state"),
                                "goal": sprint_data.get("goal"),
                                "project_key": project_key,
                                "board_id": board_id,
                                "start_date": parse_atlassian_datetime(
                                    sprint_data.get("startDate")
                                ),
                                "end_date": parse_atlassian_datetime(
                                    sprint_data.get("endDate")
                                ),
                                "complete_date": parse_atlassian_datetime(
                                    sprint_data.get("completeDate")
                                ),
                            }
                        )
                        results["synced"] += 1

                except JiraRateLimitError:
                    raise
                except JiraApiError as exc:
                    logger.error(
                        "jira_metadata_sprint_sync_failed",
                        cloud_id=self.runtime.cloud_id,
                        board_id=board_id,
                        error=str(exc),
                    )
                    results["errors"] += 1

                await asyncio.sleep(settings.JIRA_API_RATE_LIMIT_DELAY)

            if sprints_data:
                await run_in_threadpool(_persist_sprints_db)
                logger.info(
                    "jira_metadata_sprints_saved",
                    cloud_id=self.runtime.cloud_id,
                    sprint_count=len(sprints_data),
                )
        except JiraRateLimitError:
            raise
        except JiraApiError as exc:
            logger.error(
                "jira_metadata_board_fetch_failed",
                cloud_id=self.runtime.cloud_id,
                error=str(exc),
            )
            results["errors"] += 1
        except Exception as exc:
            logger.error(
                "jira_metadata_sprint_sync_db_failed",
                cloud_id=self.runtime.cloud_id,
                error=str(exc),
            )
            results["errors"] += 1

        logger.info(
            "jira_metadata_sprint_sync_completed",
            cloud_id=self.runtime.cloud_id,
            results=results,
        )
        return results

    async def _sync_all_users(self) -> dict[str, int]:
        """Jira user을 저장"""
        results = {"synced": 0, "errors": 0}
        users_data: list[dict] = []

        def _persist_users_db() -> int:
            with SessionLocal() as db:
                try:
                    result = jira_entities.upsert_users_bulk(
                        db,
                        users_data,
                    )
                    db.commit()
                    return result
                except Exception:
                    db.rollback()
                    raise

        try:
            all_users = await self.runtime.client.get_all_users()
            logger.info(
                "jira_metadata_users_fetched",
                cloud_id=self.runtime.cloud_id,
                user_count=len(all_users),
            )

            for user_data in all_users:
                account_id = user_data.get("accountId")
                if not account_id:
                    continue

                users_data.append(
                    {
                        "cloud_id": self.runtime.cloud_id,
                        "account_id": account_id,
                        "account_type": user_data.get("accountType", "atlassian"),
                        "active": user_data.get("active", True),
                        "display_name": user_data.get("displayName", "Unknown"),
                        "email_address": user_data.get("emailAddress"),
                        "avatar_url": user_data.get("avatarUrls", {}).get("48x48"),
                        "self_url": user_data.get("self"),
                    }
                )

            if users_data:
                saved_count = await run_in_threadpool(_persist_users_db)
                results["synced"] = saved_count
                logger.info(
                    "jira_metadata_users_saved",
                    cloud_id=self.runtime.cloud_id,
                    saved_count=saved_count,
                )
            else:
                logger.warning(
                    "jira_metadata_users_save_skipped",
                    cloud_id=self.runtime.cloud_id,
                    reason="no_valid_users",
                )
        except JiraRateLimitError:
            raise
        except JiraApiError as exc:
            logger.error(
                "jira_metadata_user_sync_api_failed",
                cloud_id=self.runtime.cloud_id,
                error=str(exc),
            )
            results["errors"] += 1
        except Exception as exc:
            logger.error(
                "jira_metadata_user_sync_db_failed",
                cloud_id=self.runtime.cloud_id,
                error=str(exc),
            )
            results["errors"] += 1

        logger.info(
            "jira_metadata_user_sync_completed",
            cloud_id=self.runtime.cloud_id,
            results=results,
        )
        return results
