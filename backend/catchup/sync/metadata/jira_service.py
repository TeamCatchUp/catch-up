from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi.concurrency import run_in_threadpool

from catchup.configs.config import settings
from catchup.connectors.atlassian.exceptions import AtlassianTokenExpiredError
from catchup.connectors.atlassian.exceptions import AtlassianTokenNotFoundError
from catchup.connectors.atlassian.oauth_client import AtlassianOAuthClient
from catchup.connectors.atlassian.token_manager import AtlassianTokenManager
from catchup.connectors.atlassian.token_manager import AtlassianTokenProvider
from catchup.connectors.atlassian.utils import parse_atlassian_datetime
from catchup.connectors.jira.client import JiraApiClient
from catchup.connectors.jira.client import JiraApiError
from catchup.connectors.jira.client import JiraRateLimitError
from catchup.db.atlassian import oauth_repository
from catchup.db.engine import SessionLocal
from catchup.db.jira import domain_repository as jira_entities
from catchup.sync.common.exceptions import SyncConnectorException
from catchup.sync.common.exceptions import SyncInternalException

logger = logging.getLogger(__name__)


class JiraMetadataService:
    def __init__(
        self,
        *,
        cloud_id: str,
        client: JiraApiClient,
        site_url: str,
    ) -> None:
        self.cloud_id = cloud_id
        self.client = client
        self.site_url = site_url.rstrip("/")

    async def sync_metadata(
        self,
        project_keys: list[str] | None = None,
        *,
        raise_on_error: bool = False,
    ) -> dict[str, dict[str, int]]:
        results = {
            "users": {"synced": 0, "errors": 0},
            "projects": {"synced": 0, "errors": 0},
            "sprints": {"synced": 0, "errors": 0},
        }

        user_results = await self.sync_users()
        if raise_on_error and user_results["errors"] > 0:
            raise RuntimeError(f"jira user metadata refresh failed: cloud_id={self.cloud_id}")

        project_results = await self.sync_projects(project_keys)
        if raise_on_error and project_results["errors"] > 0:
            raise RuntimeError(f"jira project metadata refresh failed: cloud_id={self.cloud_id}")

        results["users"] = user_results
        results["projects"] = project_results

        if await self.client.is_agile_available():
            sprint_results = await self.sync_sprints()
            results["sprints"] = sprint_results
            if raise_on_error and sprint_results["errors"] > 0:
                raise RuntimeError(
                    f"jira sprint metadata refresh failed: cloud_id={self.cloud_id}"
                )

        return results

    async def sync_projects(
        self,
        project_keys: list[str] | None = None,
    ) -> dict[str, int]:
        results = {"synced": 0, "errors": 0}
        projects_data: list[dict] = []

        try:
            if project_keys:
                keys_to_sync = project_keys
            else:
                all_projects = await self.client.get_all_projects()
                keys_to_sync = [p.get("key") for p in all_projects if p.get("key")]
                logger.info("Found %s accessible Jira projects", len(keys_to_sync))

            for project_key in keys_to_sync:
                try:
                    project_data = await self.client.get_project(
                        project_key,
                        expand="description,lead",
                    )
                    projects_data.append(self._build_project_snapshot_row(project_data))
                    results["synced"] += 1
                except JiraRateLimitError:
                    raise
                except JiraApiError as exc:
                    logger.error("Failed to sync Jira project %s: %s", project_key, exc)
                    results["errors"] += 1

                await asyncio.sleep(settings.JIRA_API_RATE_LIMIT_DELAY)

            await self.persist_project_snapshot(projects_data)
        except JiraRateLimitError:
            raise
        except JiraApiError as exc:
            logger.error("Failed to get Jira project list: %s", exc)
            results["errors"] += 1
        except Exception as exc:
            logger.error("Failed to sync Jira projects: %s", exc)
            results["errors"] += 1

        logger.info("Jira project sync completed: %s", results)
        return results

    async def sync_project_snapshot_from_listing(self) -> list[dict[str, Any]]:
        raw_projects = await self.client.get_all_projects()
        projects_data = [
            row
            for raw_project in raw_projects
            if (row := self._build_project_snapshot_row(raw_project))["project_key"]
        ]
        logger.info("Found %s accessible Jira projects", len(projects_data))
        await self.persist_project_snapshot(projects_data)
        return projects_data

    async def persist_project_snapshot(
        self,
        projects_data: list[dict[str, Any]],
    ) -> dict[str, int]:
        sync_result = await run_in_threadpool(
            self._persist_project_snapshot_db,
            projects_data,
        )
        logger.info(
            "[JIRA][METADATA] Project snapshot synced: cloud_id=%s, upserted=%s, deleted=%s",
            self.cloud_id,
            sync_result["upserted"],
            sync_result["deleted"],
        )
        return sync_result

    def _persist_project_snapshot_db(
        self,
        projects_data: list[dict[str, Any]],
    ) -> dict[str, int]:
        with SessionLocal() as db:
            try:
                result = jira_entities.sync_projects_snapshot(
                    db,
                    self.cloud_id,
                    projects_data,
                )
                db.commit()
                return result
            except Exception:
                db.rollback()
                raise

    def _build_project_snapshot_row(
        self,
        raw_project: dict[str, Any],
    ) -> dict[str, Any]:
        project_key = str(raw_project.get("key") or "").strip()
        project_name = str(raw_project.get("name") or project_key).strip() or project_key
        lead = raw_project.get("lead")
        lead_data = lead if isinstance(lead, dict) else {}
        return {
            "cloud_id": self.cloud_id,
            "project_key": project_key,
            "project_id": str(raw_project.get("id") or ""),
            "project_name": project_name,
            "description": raw_project.get("description"),
            "project_type": raw_project.get("projectTypeKey"),
            "lead_account_id": lead_data.get("accountId"),
            "lead_display_name": lead_data.get("displayName"),
            "url": f"{self.site_url}/projects/{project_key}" if self.site_url else None,
        }

    async def sync_sprints(self) -> dict[str, int]:
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
            boards = await self.client.get_boards()

            for board in boards:
                board_id = board.get("id")
                project_key = board.get("location", {}).get("projectKey")

                try:
                    sprints_response = await self.client.get_board_sprints(board_id)
                    sprints = sprints_response.get("values", [])

                    for sprint_data in sprints:
                        sprints_data.append(
                            {
                                "cloud_id": self.cloud_id,
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
                    logger.error("Failed to sync Jira sprints for board %s: %s", board_id, exc)
                    results["errors"] += 1

                await asyncio.sleep(settings.JIRA_API_RATE_LIMIT_DELAY)

            if sprints_data:
                await run_in_threadpool(_persist_sprints_db)
                logger.info("Saved %s Jira sprints to RDBMS", len(sprints_data))
        except JiraRateLimitError:
            raise
        except JiraApiError as exc:
            logger.error("Failed to get Jira boards: %s", exc)
            results["errors"] += 1
        except Exception as exc:
            logger.error("Failed to sync Jira sprints: %s", exc)
            results["errors"] += 1

        logger.info("Jira sprint sync completed: %s", results)
        return results

    async def sync_users(self) -> dict[str, int]:
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
            all_users = await self.client.get_all_users()
            logger.info("Fetched %s users from Jira API", len(all_users))

            for user_data in all_users:
                account_id = user_data.get("accountId")
                if not account_id:
                    continue
                users_data.append(
                    {
                        "cloud_id": self.cloud_id,
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
                logger.info("Saved %s Jira users to RDBMS", saved_count)
            else:
                logger.warning("No valid Jira users to save")
        except JiraRateLimitError:
            raise
        except JiraApiError as exc:
            logger.error("Failed to sync Jira users: %s", exc)
            results["errors"] += 1
        except Exception as exc:
            logger.error("Failed to sync Jira users: %s", exc, exc_info=True)
            results["errors"] += 1

        logger.info("Jira user sync completed: %s", results)
        return results


def _load_site_url_db(cloud_id: str) -> str:
    with SessionLocal() as db:
        token_record = oauth_repository.get_token_by_cloud_id(
            db,
            cloud_id,
        )
        if token_record is None:
            raise AtlassianTokenNotFoundError(cloud_id)
        return token_record.site_url or ""


async def create_jira_metadata_service(
    cloud_id: str,
) -> JiraMetadataService:
    token_manager = AtlassianTokenManager(
        oauth_client=AtlassianOAuthClient(),
        oauth_repository=oauth_repository,
    )

    try:
        token_provider = AtlassianTokenProvider(token_manager)
        site_url = await run_in_threadpool(_load_site_url_db, cloud_id)
    except AtlassianTokenNotFoundError as exc:
        raise SyncConnectorException(
            f"Jira 연결을 찾을 수 없습니다: {cloud_id}",
            metadata={"cloud_id": cloud_id},
        ) from exc
    except AtlassianTokenExpiredError as exc:
        raise SyncConnectorException(
            f"Jira 인증이 만료되었습니다. 재연결이 필요합니다: {cloud_id}",
            metadata={"cloud_id": cloud_id},
        ) from exc
    except Exception as exc:
        logger.error(
            "[JIRA][METADATA] Failed to resolve access token: cloud_id=%s, error=%s",
            cloud_id,
            exc,
            exc_info=True,
        )
        raise SyncInternalException(
            "Jira access token 획득 중 오류가 발생했습니다",
            metadata={"cloud_id": cloud_id},
        ) from exc

    return JiraMetadataService(
        cloud_id=cloud_id,
        client=JiraApiClient(cloud_id, token_provider),
        site_url=site_url or "",
    )
