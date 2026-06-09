from __future__ import annotations

import logging
from dataclasses import dataclass
from dataclasses import field
from typing import Any

from fastapi.concurrency import run_in_threadpool
from httpx import HTTPStatusError
from httpx import RequestError

from catchup.connectors.github.auth import get_github_app_service
from catchup.connectors.github.client import GitHubApiClient
from catchup.connectors.github.client import GitHubApiError
from catchup.connectors.github.client import GitHubRateLimitError
from catchup.db.engine import SessionLocal
from catchup.db.github import domain_repository as github_entities
from catchup.db.github.domain_repository import RepositoryUpsertData
from catchup.db.github.domain_repository import UserUpsertData
from catchup.db.github.installation_repository import (
    get_installation_by_installation_id,
)
from catchup.db.models import GithubInstallationType
from catchup.sync.common.exceptions import SyncConnectorException
from catchup.sync.common.exceptions import SyncInternalException

logger = logging.getLogger(__name__)


@dataclass(slots=True, frozen=True)
class GithubMetadataSnapshot:
    users: list[UserUpsertData] = field(default_factory=list)
    repositories: list[RepositoryUpsertData] = field(default_factory=list)


def convert_repos_to_dto(raw_repos: list[dict]) -> list[RepositoryUpsertData]:
    return [
        RepositoryUpsertData(
            repo_id=repo.get("id", 0),
            owner=repo.get("owner", {}).get("login", ""),
            name=repo.get("name", ""),
            full_name=repo.get("full_name", ""),
            html_url=repo.get("html_url", ""),
            description=repo.get("description"),
            default_branch=repo.get("default_branch", "main"),
            language=repo.get("language"),
            topics=repo.get("topics", []),
            stargazers_count=repo.get("stargazers_count", 0),
            forks_count=repo.get("forks_count", 0),
            open_issues_count=repo.get("open_issues_count", 0),
            private=repo.get("private", False),
            archived=repo.get("archived", False),
            disabled=repo.get("disabled", False),
            pushed_at=repo.get("pushed_at"),
            repo_created_at=repo.get("created_at"),
            repo_updated_at=repo.get("updated_at"),
        )
        for repo in raw_repos
    ]


class GithubMetadataService:
    def __init__(
        self,
        *,
        installation_id: int,
        access_token: str,
        account_login: str,
        account_type: GithubInstallationType,
    ) -> None:
        self.installation_id = installation_id
        self.account_login = account_login
        self.account_type = account_type
        self.client = GitHubApiClient(access_token)

    async def sync_installation_metadata(
        self,
        *,
        raise_on_error: bool = False,
    ) -> dict[str, Any]:
        snapshot, result = await self.collect_installation_metadata(
            raise_on_error=raise_on_error,
        )
        await run_in_threadpool(
            self._persist_installation_snapshot,
            snapshot,
        )
        logger.info(
            "[GITHUB][INSTALLATION] Completed User + Repository Sync users=%s repositories=%s",
            result["users"],
            result["repositories"],
        )
        return result

    async def sync_repository_snapshot(self) -> list[RepositoryUpsertData]:
        repositories = await self._collect_repository_snapshot()
        await self.persist_repository_snapshot(repositories)
        return repositories

    async def persist_repository_snapshot(
        self,
        repositories: list[RepositoryUpsertData],
    ) -> list[str]:
        await run_in_threadpool(
            self._persist_repository_snapshot_db,
            repositories,
        )
        return [repo.full_name for repo in repositories]

    async def collect_installation_metadata(
        self,
        *,
        raise_on_error: bool = False,
    ) -> tuple[GithubMetadataSnapshot, dict[str, Any]]:
        logger.info(
            "[GITHUB][INSTALLATION] Starting User + Repository Sync for installation %s",
            self.installation_id,
        )

        users, users_result = await self._collect_users_snapshot()
        if raise_on_error and users_result["errors"] > 0:
            raise GitHubApiError(
                f"github user metadata refresh failed: installation_id={self.installation_id}",
                metadata={"installation_id": self.installation_id},
            )

        repositories = await self._collect_repository_snapshot()
        repo_names = [repo.full_name for repo in repositories]

        return (
            GithubMetadataSnapshot(
                users=users,
                repositories=repositories,
            ),
            {"users": users_result, "repositories": repo_names},
        )

    def _persist_installation_snapshot(
        self,
        snapshot: GithubMetadataSnapshot,
    ) -> None:
        with SessionLocal() as db:
            if snapshot.users:
                github_entities.upsert_users_bulk(
                    db,
                    snapshot.users,
                )
            sync_result = self._persist_repository_snapshot(
                db,
                snapshot.repositories,
            )
            db.commit()

        logger.info(
            "[GITHUB][REPO_SYNC] Repository snapshot synced: installation_id=%s, upserted=%s, deleted=%s",
            self.installation_id,
            sync_result["upserted"],
            sync_result["deleted"],
        )

    def _persist_repository_snapshot_db(
        self,
        repositories: list[RepositoryUpsertData],
    ) -> None:
        with SessionLocal() as db:
            sync_result = self._persist_repository_snapshot(
                db,
                repositories,
            )
            db.commit()

        logger.info(
            "[GITHUB][REPO_SYNC] Repository snapshot synced: installation_id=%s, upserted=%s, deleted=%s",
            self.installation_id,
            sync_result["upserted"],
            sync_result["deleted"],
        )

    def _persist_repository_snapshot(
        self,
        db,
        repositories: list[RepositoryUpsertData],
    ) -> dict[str, int]:
        return github_entities.sync_repositories_snapshot(
            db,
            self.installation_id,
            repositories,
        )

    async def _collect_users_snapshot(self) -> tuple[list[UserUpsertData], dict[str, int]]:
        try:
            logger.info(
                "[GITHUB][USER_SYNC] Syncing %s '%s' (installation_id=%s)",
                self.account_type,
                self.account_login,
                self.installation_id,
            )

            users_data: list[UserUpsertData] = []

            if self.account_type == GithubInstallationType.ORGANIZATION:
                try:
                    members = await self.client.list_org_members_graphql(self.account_login)
                    logger.info(
                        "[GITHUB][USER_SYNC] Found %s members in organization '%s'",
                        len(members),
                        self.account_login,
                    )
                    users_data.extend(
                        [
                            UserUpsertData(
                                database_id=member.get("database_id"),
                                login=member.get("login", ""),
                                name=member.get("name"),
                                email=member.get("email"),
                                avatar_url=member.get("avatar_url"),
                                org_role=member.get("org_role"),
                            )
                            for member in members
                        ]
                    )
                except GitHubRateLimitError:
                    raise
                except GitHubApiError as exc:
                    logger.warning(
                        "[GITHUB][USER_SYNC] Failed to fetch org members for '%s': %s",
                        self.account_login,
                        exc,
                    )
                    return [], {"synced": 0, "errors": 1}
            else:
                try:
                    user_info = await self.client.get_user(self.account_login)
                    if user_info:
                        users_data.append(
                            UserUpsertData(
                                database_id=user_info.get("id"),
                                login=user_info.get("login", ""),
                                name=user_info.get("name"),
                                email=user_info.get("email"),
                                avatar_url=user_info.get("avatar_url"),
                                org_role=None,
                            )
                        )
                        logger.info(
                            "[GITHUB][USER_SYNC] Found user '%s'",
                            self.account_login,
                        )
                except GitHubRateLimitError:
                    raise
                except GitHubApiError as exc:
                    logger.warning(
                        "[GITHUB][USER_SYNC] Failed to fetch user '%s': %s",
                        self.account_login,
                        exc,
                    )
                    return [], {"synced": 0, "errors": 1}

            return users_data, {"synced": len(users_data), "errors": 0}
        except GitHubRateLimitError:
            raise
        except Exception as exc:
            logger.error("[GITHUB][USER_SYNC] Unexpected error: %s", exc, exc_info=True)
            return [], {"synced": 0, "errors": 1}

    async def _collect_repository_snapshot(self) -> list[RepositoryUpsertData]:
        raw_repos = await self.client.list_installation_repos()
        logger.info("[GITHUB][REPO_SYNC] Found %s accessible repositories", len(raw_repos))
        return convert_repos_to_dto(raw_repos)


def _extract_http_error_message(exc: HTTPStatusError) -> str:
    response = exc.response

    try:
        payload = response.json()
    except ValueError:
        payload = None

    if isinstance(payload, dict):
        message = payload.get("message")
        if isinstance(message, str) and message.strip():
            return message.strip()

    text = response.text.strip()
    if text:
        return text

    return str(exc)


def _load_installation_sync(installation_id: int):
    with SessionLocal() as db:
        return get_installation_by_installation_id(db, installation_id)


async def create_github_metadata_service(
    installation_id: int,
) -> GithubMetadataService:
    installation = await run_in_threadpool(_load_installation_sync, installation_id)

    if not installation:
        raise SyncConnectorException(
            f"Github Installation not found: {installation_id}",
            metadata={"installation_id": installation_id},
        )

    try:
        github_app_service = get_github_app_service()
        access_token = await github_app_service.get_installation_access_token(
            installation_id
        )
        return GithubMetadataService(
            installation_id=installation_id,
            access_token=access_token,
            account_login=installation.account_login,
            account_type=installation.account_type,
        )
    except HTTPStatusError as exc:
        status_code = exc.response.status_code
        detail = _extract_http_error_message(exc)
        metadata = {
            "installation_id": installation_id,
            "status_code": status_code,
            "detail": detail,
        }

        if status_code == 401:
            raise SyncConnectorException(
                "GitHub App 인증에 실패했습니다. GITHUB_APP_ID와 GITHUB_APP_PRIVATE_KEY 조합, 앱 키 재발급 여부를 확인하세요.",
                metadata=metadata,
                code="github_auth_failed",
            ) from exc

        if 400 <= status_code < 500:
            raise SyncConnectorException(
                "GitHub installation access token 발급에 실패했습니다.",
                metadata=metadata,
                code="github_installation_token_failed",
            ) from exc

        logger.error(
            "[GITHUB][METADATA] GitHub API request failed: installation_id=%s, status_code=%s, detail=%s",
            installation_id,
            status_code,
            detail,
            exc_info=True,
        )
        raise SyncInternalException(
            "GitHub API 요청 중 오류가 발생했습니다",
            metadata=metadata,
            code="github_api_failed",
        ) from exc
    except RequestError as exc:
        logger.error(
            "[GITHUB][METADATA] GitHub API network request failed: installation_id=%s, error=%s",
            installation_id,
            exc,
            exc_info=True,
        )
        raise SyncInternalException(
            "GitHub API 네트워크 요청 중 오류가 발생했습니다",
            metadata={"installation_id": installation_id},
            code="github_api_network_failed",
        ) from exc
    except SyncConnectorException:
        raise
    except Exception as exc:
        logger.error(
            "[GITHUB][METADATA] Failed to initialize metadata service: installation_id=%s, error=%s",
            installation_id,
            exc,
            exc_info=True,
        )
        raise SyncInternalException(
            "Github metadata service initialization failed",
            metadata={"installation_id": installation_id},
        ) from exc
