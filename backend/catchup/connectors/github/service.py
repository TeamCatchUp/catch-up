"""
Github Ingestion Service

Github 데이터 동기화 및 PGVector 적재를 담당하는 서비스.

동기화 순서:
1. Repositories → RDBMS (Installation 접근 가능 레포 목록)
2. Issues → PGVector (comments 포함)
3. PRs → PGVector (reviews, comments, commits 포함)

API 호출 최적화:
- PR 동기화: GraphQL 배치 쿼리로 PR 목록 + 상세 정보를 한 번에 조회
- 페이지네이션으로 모든 PR을 처리 (25개/페이지)
- PR 100개 기준: REST 101회 → GraphQL 4회로 감소

Note:
- Commit은 PGVector에 개별 저장하지 않음 (Graph DB 노드로만 표현)
- PR Document에 포함된 Commit SHA 목록을 통해 Graph 연결
"""

import asyncio
import logging
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Literal

from fastapi.concurrency import run_in_threadpool
from langchain_core.documents import Document
from sqlalchemy.orm import Session

from catchup.connectors.github.client import (
    GitHubApiClient,
    GitHubApiError,
    GitHubRateLimitError,
    GitHubAuthError,
    GitHubNotFoundError,
)
from catchup.connectors.github.schemas import (
    GithubUser,
    GithubIssue,
    GithubPullRequest,
    GithubCommit,
)
from catchup.connectors.github.transformers import GithubTransformer
from catchup.components.vector_db.pgvector import PGVectorRepository
from catchup.components.summarizer import SummarizerService, SummarizeRequest, get_summarizer_service
from catchup.configs.config import settings
from catchup.db.engine import SessionLocal
from catchup.db.github import domain_repository as github_entities
from catchup.db.github.domain_repository import RepositoryUpsertData, UserUpsertData
from catchup.db.models import GithubEntityType, GithubInstallationType, SourceType
from catchup.db.user_source_mapping import find_premapped_names_by_source_type
from catchup.sync.audit import SyncAuditContext
from catchup.sync.common.schemas import TargetSyncResult

logger = logging.getLogger(__name__)


# Skip 가능한 에러 (로깅만 하고 진행)
SKIPPABLE_ERRORS = {
    "not_found",  # 삭제된 리소스
    "forbidden",  # 권한 없음
    "gone",  # 더 이상 존재하지 않음
}

GITHUB_NAME_CACHE_TTL = timedelta(seconds=300)


# ============================================================
# Operation Types for Logging
# ============================================================

class SyncOperation:
    """동기화 작업 타입 (로깅용)"""
    FULL_SYNC = "FULL_SYNC"
    INCREMENTAL_SYNC = "INCREMENTAL_SYNC"
    USER_SYNC = "USER_SYNC"
    REPO_SYNC = "REPO_SYNC"
    ISSUE_SYNC = "ISSUE_SYNC"
    PR_SYNC = "PR_SYNC"


def _convert_repos_to_dto(raw_repos: list[dict]) -> list[RepositoryUpsertData]:
    """GitHub API 응답 dict 리스트를 RepositoryUpsertData DTO 리스트로 변환"""
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


@dataclass(slots=True, frozen=True)
class GithubMetadataSnapshot:
    users: list[UserUpsertData] = field(default_factory=list)
    repositories: list[RepositoryUpsertData] = field(default_factory=list)


@dataclass(slots=True, frozen=True)
class GithubRepoRef:
    repo_id: int
    full_name: str
    owner: str
    repo: str


@dataclass(slots=True, frozen=True)
class GithubRecordGapItem:
    record_type: str
    expected_count: int = 0
    stored_count: int = 0
    missing_count: int = 0
    missing_ids: list[str] = field(default_factory=list)


@dataclass(slots=True, frozen=True)
class GithubRecordGapReport:
    records: list[GithubRecordGapItem] = field(default_factory=list)


@dataclass(slots=True, frozen=True)
class GithubRecordRetryItem:
    record_type: str
    requested_ids: list[str] = field(default_factory=list)
    retried_count: int = 0
    succeeded_count: int = 0
    failed_ids: list[str] = field(default_factory=list)
    remaining_missing_ids: list[str] = field(default_factory=list)


@dataclass(slots=True, frozen=True)
class GithubRecordRetryResult:
    records: list[GithubRecordRetryItem] = field(default_factory=list)


class GithubIngestionService:
    """
    Github 데이터 수집 및 PGVector 적재 서비스

    Usage:
        service = GithubIngestionService(installation_id, access_token)
        await service.initialize()
        result = await service.full_sync(repo_ids=[12345, 67890], sync_from_dt=datetime.now(timezone.utc))
    """

    def __init__(
        self,
        repository: PGVectorRepository,
        installation_id: int,
        access_token: str,
        account_login: str,
        account_type: GithubInstallationType,
        enable_summarization: bool = True,
    ):
        """
        Args:
            installation_id: Github App Installation ID
            access_token: Installation Access Token
            enable_summarization: 임베딩 전 LLM 요약 활성화 여부
        """
        self.installation_id = installation_id
        self.access_token = access_token
        self.enable_summarization = enable_summarization

        self.client = GitHubApiClient(access_token)
        self.transformer: GithubTransformer | None = None
        self.repository = repository
        self.summarizer: SummarizerService | None = None
        self.account_login = account_login
        self.account_type = account_type

        self._github_name_cache: dict[str, str | None] = {}
        self._github_name_cache_loaded_at: datetime | None = None

    async def initialize(self) -> None:
        """
        서비스 초기화

        - PGVector 초기화
        - Transformer 생성
        - Summarizer 초기화 (요약 활성화 시)
        """
        self.repository.ensure_initialized()
        self.transformer = GithubTransformer()

        # Summarizer 초기화 (요약 활성화 시)
        if self.enable_summarization:
            self.summarizer = get_summarizer_service()
            logger.info("Summarization enabled for embedding optimization")

        logger.info(f"GithubIngestionService initialized for installation {self.installation_id}")

    # ============================================================
    # Sync Status Management Helpers
    # ============================================================

    def _start_sync(
        self,
        repo_full_name: str,
        entity_type: GithubEntityType,
        operation: str,
    ) -> None:
        """동기화 시작 로그 기록."""
        logger.info(f"[GITHUB][{operation}] Started: {entity_type.value} sync for {repo_full_name}")

    def _complete_sync(
        self,
        repo_full_name: str,
        entity_type: GithubEntityType,
        synced_count: int,
        operation: str,
    ) -> None:
        """동기화 완료 로그 기록."""
        logger.info(
            f"[GITHUB][{operation}] Completed: {entity_type.value} sync for {repo_full_name} "
            f"({synced_count} synced)"
        )

    def _fail_sync(
        self,
        repo_full_name: str,
        entity_type: GithubEntityType,
        error: str | Exception,
        operation: str,
    ) -> None:
        """동기화 실패 로그 기록."""
        error_msg = str(error)[:1000]
        logger.error(
            f"[GITHUB][{operation}] Failed: {entity_type.value} sync for {repo_full_name} - {error_msg}"
        )

    def _handle_rate_limit(
        self,
        repo_full_name: str,
        entity_type: GithubEntityType,
        error: GitHubRateLimitError,
        operation: str,
    ) -> None:
        """Rate limit 로그 기록."""
        logger.warning(
            f"[GITHUB][{operation}] Rate limit hit: {entity_type.value} sync for {repo_full_name} "
            f"(retry after {error.retry_after}s)"
        )

    @staticmethod
    def _resolve_github_real_name(
        name_map: dict[str, str | None],
        login: str | None,
    ) -> str | None:
        """
        PreMappingBuffer에서 preload된 github login → 실명 매핑을 조회한다.
        """
        if not login:
            return None

        return name_map.get(login)

    def _load_premapped_github_names_sync(self) -> dict[str, str | None]:
        with SessionLocal() as db:
            premapped = find_premapped_names_by_source_type(db, SourceType.GITHUB)
        return {login: name for login, name in premapped.items() if login}

    def _is_github_name_cache_fresh(self) -> bool:
        if self._github_name_cache_loaded_at is None:
            return False
        return (
            datetime.now(timezone.utc) - self._github_name_cache_loaded_at
        ) < GITHUB_NAME_CACHE_TTL

    def _ensure_premapped_github_names_sync(self, force: bool = False) -> int:
        """github login → 실명 매핑 캐시를 TTL 기준으로 유지한다."""
        # sync마다 전체 user mapping을 다시 읽지 않도록 TTL cache 기록
        if not force and self._is_github_name_cache_fresh():
            return len(self._github_name_cache)

        self._github_name_cache = self._load_premapped_github_names_sync()
        self._github_name_cache_loaded_at = datetime.now(timezone.utc)
        return len(self._github_name_cache)

    async def _ensure_premapped_github_names_async(self, force: bool = False) -> int:
        return await run_in_threadpool(
            self._ensure_premapped_github_names_sync,
            force,
        )

    def _get_github_name_map(self) -> dict[str, str | None]:
        return dict(self._github_name_cache)

    def _apply_user_display_name(
        self,
        name_map: dict[str, str | None],
        user: GithubUser | None,
    ) -> GithubUser | None:
        """
        사용자 객체의 name을 pre-mapping 이름으로 교체한다.
        매핑이 없으면 원본 사용자 객체를 그대로 반환.
        """
        if user is None:
            return None

        mapped_name = self._resolve_github_real_name(name_map, user.login)
        if not mapped_name:
            return user
        return user.model_copy(update={"name": mapped_name})

    def _apply_issue_user_mapping(
        self,
        name_map: dict[str, str | None],
        issue: GithubIssue,
    ) -> GithubIssue:
        """Issue 하위 사용자(작성자/assignee/comment)의 name을 실명으로 보정한다."""
        # 리팩토링: mutable service state 대신 name_map snapshot만 받아 pure helper처럼 동작한다.
        comments = [
            comment.model_copy(
                update={"author": self._apply_user_display_name(name_map, comment.author)}
            )
            for comment in issue.comments
        ]
        return issue.model_copy(update={
            "author": self._apply_user_display_name(name_map, issue.author),
            "assignees": [
                self._apply_user_display_name(name_map, assignee)
                for assignee in issue.assignees
            ],
            "comments": comments,
        })

    def _apply_pr_user_mapping(
        self,
        name_map: dict[str, str | None],
        pr: GithubPullRequest,
    ) -> GithubPullRequest:
        """PR 하위 사용자(작성자/리뷰어/review/comment/merge/commit author)의 name을 실명으로 보정한다."""
        comments = [
            comment.model_copy(
                update={"author": self._apply_user_display_name(name_map, comment.author)}
            )
            for comment in pr.comments
        ]
        reviews = [
            review.model_copy(
                update={"author": self._apply_user_display_name(name_map, review.author)}
            )
            for review in pr.reviews
        ]

        commits = []
        for commit in pr.commits:
            commit_author_name = self._resolve_github_real_name(
                name_map,
                commit.author_login,
            )
            if commit_author_name and commit.author_name != commit_author_name:
                commits.append(commit.model_copy(update={"author_name": commit_author_name}))
            else:
                commits.append(commit)

        return pr.model_copy(update={
            "author": self._apply_user_display_name(name_map, pr.author),
            "assignees": [
                self._apply_user_display_name(name_map, assignee)
                for assignee in pr.assignees
            ],
            "reviewers": [
                self._apply_user_display_name(name_map, reviewer)
                for reviewer in pr.reviewers
            ],
            "merged_by": self._apply_user_display_name(name_map, pr.merged_by),
            "reviews": reviews,
            "comments": comments,
            "commits": commits,
        })

    # ============================================================
    # Full Sync
    # ============================================================

    async def full_sync(
        self,
        repo_ids: list[int] | None = None,
        sync_from_dt: datetime | None = None,
        audit_context: SyncAuditContext | None = None,
    ) -> TargetSyncResult:
        """
        Github Full Sync
        """
        # Handler으로 부터 Session을 받지 않도록 수정
        preloaded_count = await self._ensure_premapped_github_names_async(force=False)
        logger.info(f"[GITHUB][FULL SYNC] Preloaded {preloaded_count} pre-mapping user names")
        name_map = self._get_github_name_map()
        results = {
            "repositories": {"synced": 0, "errors": 0},
            "issues": {"synced": 0, "errors": 0},
            "pull_requests": {"synced": 0, "errors": 0},
        }

        try:
            # 1. Repository 목록 조회 및 RDBMS 저장
            repos_to_sync = (
                await self._sync_repositories()
                if repo_ids is None
                else await self._get_repo_names_by_ids(repo_ids)
            )
            if repo_ids is not None and not repos_to_sync:
                results["repositories"]["errors"] = max(1, len(repo_ids))
                logger.error(
                    "[GITHUB][%s] No repositories resolved from repo_ids: installation_id=%s, repo_ids=%s",
                    SyncOperation.FULL_SYNC,
                    self.installation_id,
                    repo_ids,
                )

            results["repositories"]["synced"] = len(repos_to_sync)
            sync_from = sync_from_dt or (
                datetime.now(timezone.utc) - timedelta(days=settings.DEFAULT_SYNC_DAYS)
            )

            logger.info(
                f"[GITHUB][{SyncOperation.FULL_SYNC}] Syncing {len(repos_to_sync)} "
                f"repositories since {sync_from.isoformat()}"
            )

            # 2. 각 Repository별 동기화
            for repo_full_name in repos_to_sync:
                try:
                    owner, repo = repo_full_name.split("/", 1)

                    # Issue 동기화
                    issue_result = await self._sync_issues(
                        owner,
                        repo,
                        name_map=name_map,
                        since=sync_from,
                        audit_context=audit_context,
                    )
                    results["issues"]["synced"] += issue_result.get("synced", 0)
                    results["issues"]["errors"] += issue_result.get("errors", 0)

                    # PR 동기화 (Commits 포함)
                    pr_result = await self._sync_pull_requests(
                        owner,
                        repo,
                        name_map=name_map,
                        since=sync_from,
                        audit_context=audit_context,
                    )
                    results["pull_requests"]["synced"] += pr_result.get("synced", 0)
                    results["pull_requests"]["errors"] += pr_result.get("errors", 0)

                except Exception as e:
                    logger.error(f"[GITHUB][{SyncOperation.FULL_SYNC}] Failed to sync repository {repo_full_name}: {e}")
                    results["repositories"]["errors"] += 1

            return TargetSyncResult(
                synced_count=(
                    int(results["issues"]["synced"]) + int(results["pull_requests"]["synced"])
                ),
                error_count=(
                    int(results["repositories"]["errors"])
                    + int(results["issues"]["errors"])
                    + int(results["pull_requests"]["errors"])
                ),
            )

        except Exception as e:
            logger.error(f"[GITHUB][{SyncOperation.FULL_SYNC}] Full sync failed: {e}")
            raise

    async def _sync_users(
        self,
        db: Session,
        *,
        auto_commit: bool = True,
    ) -> dict[str, int]:
        """
        Organization 멤버 동기화 (RDBMS 저장)

        Installation이 Organization에 설치된 경우 멤버를 동기화.
        User 계정에 설치된 경우 해당 User만 저장.

        Returns:
            동기화 결과 {"synced": N, "errors": N}
        """
        repo_full_name = "_installation_"

        try:
            # 동기화 시작
            self._start_sync(repo_full_name, GithubEntityType.USER, SyncOperation.USER_SYNC)

            logger.info(
                f"[GITHUB][{SyncOperation.USER_SYNC}] Syncing {self.account_type} '{self.account_login}' "
                f"(installation_id={self.installation_id})"
            )

            users_data = []

            if self.account_type == GithubInstallationType.ORGANIZATION:
                # Organization 멤버 조회 (GraphQL)
                try:
                    members = await self.client.list_org_members_graphql(self.account_login)
                    logger.info(
                        f"[GITHUB][{SyncOperation.USER_SYNC}] Found {len(members)} members "
                        f"in organization '{self.account_login}'"
                    )
                    users_data.extend([
                        UserUpsertData(
                            database_id=m.get("database_id"),
                            login=m.get("login", ""),
                            name=m.get("name"),
                            email=m.get("email"),
                            avatar_url=m.get("avatar_url"),
                            org_role=m.get("org_role"),
                        )
                        for m in members
                    ])
                except GitHubApiError as e:
                    error_msg = (
                        f"Failed to fetch org members for '{self.account_login}': {e}. "
                        "Organization members permission may be required."
                    )
                    logger.warning(f"[GITHUB][{SyncOperation.USER_SYNC}] {error_msg}")
                    self._fail_sync(repo_full_name, GithubEntityType.USER, str(e), SyncOperation.USER_SYNC)
                    return {"synced": 0, "errors": 1}

            else:
                # User 계정인 경우 해당 User 정보만 조회
                try:
                    user_info = await self.client.get_user(self.account_login)
                    if user_info:
                        users_data.append(UserUpsertData(
                            database_id=user_info.get("id"),
                            login=user_info.get("login", ""),
                            name=user_info.get("name"),
                            email=user_info.get("email"),
                            avatar_url=user_info.get("avatar_url"),
                            org_role=None,
                        ))
                        logger.info(f"[GITHUB][{SyncOperation.USER_SYNC}] Found user '{self.account_login}'")
                except GitHubApiError as e:
                    logger.warning(f"[GITHUB][{SyncOperation.USER_SYNC}] Failed to fetch user '{self.account_login}': {e}")
                    self._fail_sync(repo_full_name, GithubEntityType.USER, str(e), SyncOperation.USER_SYNC)
                    return {"synced": 0, "errors": 1}

            # RDBMS에 벌크 저장
            if users_data:
                github_entities.upsert_users_bulk(
                    db,
                    users_data,
                    auto_commit=auto_commit,
                )

            # 동기화 완료
            self._complete_sync(repo_full_name, GithubEntityType.USER, len(users_data), SyncOperation.USER_SYNC)
            return {"synced": len(users_data), "errors": 0}

        except GitHubRateLimitError as e:
            self._handle_rate_limit(repo_full_name, GithubEntityType.USER, e, SyncOperation.USER_SYNC)
            raise

        except Exception as e:
            logger.error(f"[GITHUB][{SyncOperation.USER_SYNC}] Unexpected error: {e}", exc_info=True)
            self._fail_sync(repo_full_name, GithubEntityType.USER, str(e), SyncOperation.USER_SYNC)
            return {"synced": 0, "errors": 1}
        
    async def sync_installation_metadata(
        self,
        *,
        auto_commit: bool = True,
        raise_on_error: bool = False,
    ) -> dict[str, Any]:
        """
        Installtion 메타데이터 동기화 (Users + Repository)
        """
        snapshot, result = await self.collect_installation_metadata(
            raise_on_error=raise_on_error,
        )
        await run_in_threadpool(
            self._persist_installation_snapshot_sync,
            snapshot,
            auto_commit=auto_commit,
        )
        logger.info(
            f"[GITHUB][INSTALLATION] Completed User + Repository Sync "
            f"users : {result['users']}, repositories {result['repositories']}"
        )
        return result

    async def collect_installation_metadata(
        self,
        *,
        raise_on_error: bool = False,
    ) -> tuple[GithubMetadataSnapshot, dict[str, Any]]:
        logger.info(
            f"[GITHUB][INSTALLATION] Starting User + Repository Sync "
            f"for installation {self.installation_id}"
        )

        # gather() -> users/repositories metadata fetch를 병렬로 수행한다.
        users_snapshot, repository_snapshot = await asyncio.gather(
            self._collect_users_snapshot(),
            self._collect_repository_snapshot(),
            return_exceptions=True,
        )

        if isinstance(users_snapshot, Exception):
            raise users_snapshot
        if isinstance(repository_snapshot, Exception):
            raise repository_snapshot

        users, users_result = users_snapshot
        repositories = repository_snapshot
        if raise_on_error and users_result["errors"] > 0:
            raise RuntimeError(
                f"github user metadata refresh failed: installation_id={self.installation_id}"
            )

        repo_names = [repo.full_name for repo in repositories]

        snapshot = GithubMetadataSnapshot(
            users=users,
            repositories=repositories,
        )
        return snapshot, {"users": users_result, "repositories": repo_names}

    def persist_installation_snapshot(
        self,
        db: Session,
        snapshot: GithubMetadataSnapshot,
        *,
        auto_commit: bool = True,
    ) -> None:
        if snapshot.users:
            github_entities.upsert_users_bulk(
                db,
                snapshot.users,
                auto_commit=False,
            )

        sync_result = github_entities.sync_repositories_snapshot(
            db,
            self.installation_id,
            snapshot.repositories,
            auto_commit=False,
        )
        logger.info(
            "[GITHUB][%s] Repository snapshot synced: installation_id=%s, upserted=%s, deleted=%s",
            SyncOperation.REPO_SYNC,
            self.installation_id,
            sync_result["upserted"],
            sync_result["deleted"],
        )

        if auto_commit:
            db.commit()
        else:
            db.flush()

    def _persist_installation_snapshot_sync(
        self,
        snapshot: GithubMetadataSnapshot,
        *,
        auto_commit: bool = True,
    ) -> None:
        # 실제 Persist 시점에만 SessionLocal 생성
        with SessionLocal() as db:
            self.persist_installation_snapshot(
                db,
                snapshot,
                auto_commit=auto_commit,
            )

    async def _sync_repositories(
        self,
        *,
        auto_commit: bool = True,
    ) -> list[str]:
        """
        Installation에서 접근 가능한 Repository 목록 조회 및 RDBMS 저장

        Returns:
            Repository full_name 리스트
        """
        repo_full_name = "_installation_"

        try:
            # 동기화 시작
            self._start_sync(repo_full_name, GithubEntityType.REPOSITORY, SyncOperation.REPO_SYNC)

            raw_repos = await self.client.list_installation_repos()
            logger.info(f"[GITHUB][{SyncOperation.REPO_SYNC}] Found {len(raw_repos)} accessible repositories")

            # dict → DTO 변환
            repos_data = _convert_repos_to_dto(raw_repos)

            sync_result = await run_in_threadpool(
                self._sync_repositories_snapshot_sync,
                repos_data,
                auto_commit=auto_commit,
            )

            logger.info(
                "[GITHUB][%s] Repository snapshot synced: installation_id=%s, upserted=%s, deleted=%s",
                SyncOperation.REPO_SYNC,
                self.installation_id,
                sync_result["upserted"],
                sync_result["deleted"],
            )

            self._complete_sync(
                repo_full_name,
                GithubEntityType.REPOSITORY,
                len(repos_data),
                SyncOperation.REPO_SYNC,
            )
            return [repo.full_name for repo in repos_data]


        except GitHubRateLimitError as e:
            self._handle_rate_limit(repo_full_name, GithubEntityType.REPOSITORY, e, SyncOperation.REPO_SYNC)
            raise

        except GitHubApiError as e:
            logger.error(f"[GITHUB][{SyncOperation.REPO_SYNC}] API error: {e}")
            self._fail_sync(repo_full_name, GithubEntityType.REPOSITORY, str(e), SyncOperation.REPO_SYNC)
            raise

        except Exception as e:
            logger.error(f"[GITHUB][{SyncOperation.REPO_SYNC}] Unexpected error: {e}", exc_info=True)
            self._fail_sync(repo_full_name, GithubEntityType.REPOSITORY, str(e), SyncOperation.REPO_SYNC)
            raise

    async def _collect_users_snapshot(self) -> tuple[list[UserUpsertData], dict[str, int]]:
        try:
            logger.info(
                f"[GITHUB][{SyncOperation.USER_SYNC}] Syncing {self.account_type} '{self.account_login}' "
                f"(installation_id={self.installation_id})"
            )

            users_data: list[UserUpsertData] = []

            if self.account_type == GithubInstallationType.ORGANIZATION:
                try:
                    members = await self.client.list_org_members_graphql(self.account_login)
                    logger.info(
                        f"[GITHUB][{SyncOperation.USER_SYNC}] Found {len(members)} members "
                        f"in organization '{self.account_login}'"
                    )
                    users_data.extend([
                        UserUpsertData(
                            database_id=member.get("database_id"),
                            login=member.get("login", ""),
                            name=member.get("name"),
                            email=member.get("email"),
                            avatar_url=member.get("avatar_url"),
                            org_role=member.get("org_role"),
                        )
                        for member in members
                    ])
                except GitHubApiError as exc:
                    error_msg = (
                        f"Failed to fetch org members for '{self.account_login}': {exc}. "
                        "Organization members permission may be required."
                    )
                    logger.warning(f"[GITHUB][{SyncOperation.USER_SYNC}] {error_msg}")
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
                        logger.info(f"[GITHUB][{SyncOperation.USER_SYNC}] Found user '{self.account_login}'")
                except GitHubApiError as exc:
                    logger.warning(
                        f"[GITHUB][{SyncOperation.USER_SYNC}] Failed to fetch user '{self.account_login}': {exc}"
                    )
                    return [], {"synced": 0, "errors": 1}

            return users_data, {"synced": len(users_data), "errors": 0}
        except GitHubRateLimitError:
            raise
        except Exception as exc:
            logger.error(f"[GITHUB][{SyncOperation.USER_SYNC}] Unexpected error: {exc}", exc_info=True)
            return [], {"synced": 0, "errors": 1}

    async def _collect_repository_snapshot(self) -> list[RepositoryUpsertData]:
        raw_repos = await self.client.list_installation_repos()
        logger.info(f"[GITHUB][{SyncOperation.REPO_SYNC}] Found {len(raw_repos)} accessible repositories")
        return _convert_repos_to_dto(raw_repos)

    def _get_repo_names_by_ids_sync(self, repo_ids: list[int]) -> list[str]:
        """
        Repository ID 목록으로 full_name 조회

        Args:
            repo_ids: GitHub Repository ID 목록

        Returns:
            Repository full_name 리스트
        """
        with SessionLocal() as db:
            repos = github_entities.get_repositories_by_ids(
                db,
                self.installation_id,
                repo_ids,
            )
        repo_by_id = {repo.repo_id: repo for repo in repos}
        return [
            repo.full_name
            for repo_id in repo_ids
            if (repo := repo_by_id.get(repo_id)) is not None
        ]

    async def _get_repo_names_by_ids(self, repo_ids: list[int]) -> list[str]:
        return await run_in_threadpool(self._get_repo_names_by_ids_sync, repo_ids)

    def _sync_repositories_snapshot_sync(
        self,
        repos_data: list[RepositoryUpsertData],
        *,
        auto_commit: bool = True,
    ) -> dict[str, int]:
        with SessionLocal() as db:
            return github_entities.sync_repositories_snapshot(
                db,
                self.installation_id,
                repos_data,
                auto_commit=auto_commit,
            )

    def _resolve_sync_from_dt(
        self,
        sync_days: int | None,
    ) -> datetime:
        days = sync_days if sync_days is not None else settings.DEFAULT_SYNC_DAYS
        return datetime.now(timezone.utc) - timedelta(days=days)

    def _load_repo_ref_sync(
        self,
        repo_id: int,
    ) -> GithubRepoRef:
        # 리팩토링: 단건 repo ref는 전체 목록 조회 대신 get_repository_by_id로 해결한다.
        with SessionLocal() as db:
            repo_record = github_entities.get_repository_by_id(db, repo_id)

        if repo_record is None or repo_record.installation_id != self.installation_id:
            raise ValueError(f"github repository not found: repo_id={repo_id}")

        full_name = repo_record.full_name
        owner, repo = full_name.split("/", 1)
        return GithubRepoRef(
            repo_id=repo_id,
            full_name=full_name,
            owner=owner,
            repo=repo,
        )

    async def _get_repo_ref(
        self,
        repo_id: int,
    ) -> GithubRepoRef:
        return await run_in_threadpool(self._load_repo_ref_sync, repo_id)

    @staticmethod
    def _extract_record_ids_from_doc_ids(doc_ids: list[str]) -> list[str]:
        record_ids: list[str] = []
        for doc_id in doc_ids:
            if not doc_id or ":" not in doc_id:
                continue
            record_ids.append(doc_id.rsplit(":", 1)[-1])
        return record_ids

    @staticmethod
    def _sort_record_ids(record_ids: set[str]) -> list[str]:
        def _key(value: str) -> tuple[int, int | str]:
            try:
                return (0, int(value))
            except ValueError:
                return (1, value)

        return sorted(record_ids, key=_key)

    def _build_gap_item(
        self,
        *,
        record_type: str,
        expected_ids: list[str],
        stored_ids: list[str],
        stored_count: int,
    ) -> GithubRecordGapItem:
        missing_ids = self._sort_record_ids(set(expected_ids) - set(stored_ids))
        return GithubRecordGapItem(
            record_type=record_type,
            expected_count=len(expected_ids),
            stored_count=stored_count,
            missing_count=len(missing_ids),
            missing_ids=missing_ids,
        )

    def _build_issue_document(
        self,
        owner: str,
        repo: str,
        issue_data: dict[str, Any],
        name_map: dict[str, str | None],
    ) -> Document:
        issue = self.transformer.parse_issue(issue_data)
        issue = self._apply_issue_user_mapping(name_map, issue)
        return self.transformer.transform_issue(
            issue,
            owner,
            repo,
            self.installation_id,
        )

    def _build_pull_request_document(
        self,
        owner: str,
        repo: str,
        pr_data: dict[str, Any],
        name_map: dict[str, str | None],
    ) -> Document:
        pr = self.transformer.parse_pull_request(pr_data)
        pr = self._apply_pr_user_mapping(name_map, pr)
        return self.transformer.transform_pull_request(
            pr,
            owner,
            repo,
            self.installation_id,
        )

    def _build_issue_batch_sync(
        self,
        owner: str,
        repo: str,
        issue_batch: list[dict[str, Any]],
        name_map: dict[str, str | None],
    ) -> tuple[list[Document], list[str], int]:
        documents: list[Document] = []
        doc_ids: list[str] = []
        error_count = 0

        for issue_data in issue_batch:
            try:
                doc = self._build_issue_document(owner, repo, issue_data, name_map)
                documents.append(doc)
                doc_ids.append(doc.id)
            except Exception as exc:
                logger.warning(
                    "[GITHUB][%s] Failed to process issue #%s: %s",
                    SyncOperation.ISSUE_SYNC,
                    issue_data.get("number"),
                    exc,
                )
                error_count += 1

        return documents, doc_ids, error_count

    def _build_pull_request_batch_sync(
        self,
        owner: str,
        repo: str,
        pr_batch: list[dict[str, Any]],
        name_map: dict[str, str | None],
    ) -> tuple[list[Document], list[str], int]:
        documents: list[Document] = []
        doc_ids: list[str] = []
        error_count = 0

        for pr_data in pr_batch:
            try:
                doc = self._build_pull_request_document(owner, repo, pr_data, name_map)
                documents.append(doc)
                doc_ids.append(doc.id)
            except Exception as exc:
                logger.warning(
                    "[GITHUB][%s] Failed to process PR #%s: %s",
                    SyncOperation.PR_SYNC,
                    pr_data.get("number"),
                    exc,
                )
                logger.debug("PR processing error traceback:\n%s", traceback.format_exc())
                error_count += 1

        return documents, doc_ids, error_count

    def _build_issue_documents_sync(
        self,
        owner: str,
        repo: str,
        issue_items: list[tuple[str, dict[str, Any]]],
        name_map: dict[str, str | None],
    ) -> tuple[list[Document], list[str]]:
        documents: list[Document] = []
        failed_ids: list[str] = []

        for record_id, issue_data in issue_items:
            try:
                documents.append(
                    self._build_issue_document(owner, repo, issue_data, name_map)
                )
            except Exception as exc:
                logger.warning(
                    "[GITHUB][REPAIR] Failed to build issue doc: installation_id=%s, repo=%s/%s, issue_id=%s, error=%s",
                    self.installation_id,
                    owner,
                    repo,
                    record_id,
                    exc,
                )
                failed_ids.append(record_id)

        return documents, failed_ids

    def _build_pull_request_documents_sync(
        self,
        owner: str,
        repo: str,
        pr_items: list[tuple[str, dict[str, Any]]],
        name_map: dict[str, str | None],
    ) -> tuple[list[Document], list[str]]:
        documents: list[Document] = []
        failed_ids: list[str] = []

        for record_id, pr_data in pr_items:
            try:
                documents.append(
                    self._build_pull_request_document(owner, repo, pr_data, name_map)
                )
            except Exception as exc:
                logger.warning(
                    "[GITHUB][REPAIR] Failed to build pr doc: installation_id=%s, repo=%s/%s, pr_id=%s, error=%s",
                    self.installation_id,
                    owner,
                    repo,
                    record_id,
                    exc,
                )
                failed_ids.append(record_id)

        return documents, failed_ids
    

    async def _fetch_issue_nodes(
        self,
        *,
        owner: str,
        repo: str,
        issue_ids: list[str],
    ) -> tuple[list[tuple[str, dict[str, Any]]], list[str]]:
        return await self._fetch_retry_nodes(
            owner=owner,
            repo=repo,
            record_ids=issue_ids,
            record_type="issue",
        )

    async def _fetch_pull_request_nodes(
        self,
        *,
        owner: str,
        repo: str,
        pull_request_ids: list[str],
    ) -> tuple[list[tuple[str, dict[str, Any]]], list[str]]:
        return await self._fetch_retry_nodes(
            owner=owner,
            repo=repo,
            record_ids=pull_request_ids,
            record_type="pull_request",
        )

    async def _fetch_retry_nodes(
        self,
        *,
        owner: str,
        repo: str,
        record_ids: list[str],
        record_type: Literal["issue", "pull_request"],
        concurrency: int = 8,
    ) -> tuple[list[tuple[str, dict[str, Any]]], list[str]]:
        if not record_ids:
            return [], []

        if record_type == "issue":
            entity_label = "issue"
            id_label = "issue_id"
        else:
            entity_label = "pull request"
            id_label = "pr_id"

        semaphore = asyncio.Semaphore(max(1, min(concurrency, len(record_ids))))

        async def _fetch_one(
            record_id: str,
        ) -> tuple[str, dict[str, Any] | None, bool]:
            try:
                number = int(record_id)
            except ValueError:
                logger.warning(
                    "[GITHUB][REPAIR] Invalid %s id: installation_id=%s, repo=%s/%s, %s=%s",
                    entity_label,
                    self.installation_id,
                    owner,
                    repo,
                    id_label,
                    record_id,
                )
                return record_id, None, True

            try:
                async with semaphore:
                    if record_type == "issue":
                        data = await self.client.get_issue_graphql(owner, repo, number)
                    else:
                        data = await self.client.get_pull_request_graphql(owner, repo, number)

                if not data:
                    return record_id, None, True

                return record_id, data, False
            except Exception as exc:
                logger.warning(
                    "[GITHUB][REPAIR] Failed to fetch %s: installation_id=%s, repo=%s/%s, %s=%s, error=%s",
                    entity_label,
                    self.installation_id,
                    owner,
                    repo,
                    id_label,
                    record_id,
                    exc,
                )
                return record_id, None, True

        results = await asyncio.gather(*[_fetch_one(record_id) for record_id in record_ids])

        items: list[tuple[str, dict[str, Any]]] = []
        failed_ids: list[str] = []
        for record_id, data, failed in results:
            if failed or data is None:
                failed_ids.append(record_id)
                continue
            items.append((record_id, data))

        return items, failed_ids

    async def _retry_record_batch(
        self,
        *,
        repo_ref: GithubRepoRef,
        record_type: Literal["issue", "pull_request"],
        requested_ids: list[str],
    ) -> GithubRecordRetryItem:
        await self._ensure_premapped_github_names_async(force=False)
        name_map = self._get_github_name_map()

        if record_type == "issue":
            nodes, failed_ids = await self._fetch_issue_nodes(
                owner=repo_ref.owner,
                repo=repo_ref.repo,
                issue_ids=requested_ids,
            )
            documents, build_failed_ids = await run_in_threadpool(
                self._build_issue_documents_sync,
                repo_ref.owner,
                repo_ref.repo,
                nodes,
                name_map,
            )
        else:
            nodes, failed_ids = await self._fetch_pull_request_nodes(
                owner=repo_ref.owner,
                repo=repo_ref.repo,
                pull_request_ids=requested_ids,
            )
            documents, build_failed_ids = await run_in_threadpool(
                self._build_pull_request_documents_sync,
                repo_ref.owner,
                repo_ref.repo,
                nodes,
                name_map,
            )

        failed_ids.extend(build_failed_ids)
        succeeded_count = 0

        if documents:
            try:
                upsert_documents = documents
                if self.summarizer:
                    upsert_documents = await self._summarize_documents(
                        documents,
                        repo_full_name=repo_ref.full_name,
                        entity_type=record_type,
                        audit_context=None,
                    )

                await self.repository.upsert_documents(
                    upsert_documents,
                    [doc.id for doc in upsert_documents],
                    audit_context=None,
                    context=(
                        f"entity_type={record_type},"
                        f"repo={repo_ref.full_name},"
                        f"mode=partial_retry,"
                        f"doc_count={len(upsert_documents)}"
                    ),
                )
                succeeded_count = len(upsert_documents)
            except Exception as exc:
                logger.error(
                    "[GITHUB][REPAIR] Failed to upsert %s docs: installation_id=%s, repo=%s, error=%s",
                    record_type,
                    self.installation_id,
                    repo_ref.full_name,
                    exc,
                    exc_info=True,
                )
                failed_ids.extend(
                    self._extract_record_ids_from_doc_ids([doc.id for doc in documents])
                )

        return GithubRecordRetryItem(
            record_type=record_type,
            requested_ids=requested_ids,
            retried_count=len(requested_ids),
            succeeded_count=succeeded_count,
            failed_ids=self._sort_record_ids(set(failed_ids)),
        )

    async def build_record_gap_report(
        self,
        *,
        repo_id: int,
        sync_days: int | None = None,
        sync_from_dt: datetime | None = None,
    ) -> GithubRecordGapReport:
        repo_ref = await self._get_repo_ref(repo_id)
        sync_from_dt = sync_from_dt or self._resolve_sync_from_dt(sync_days)

        (
            expected_issue_ids,
            expected_pull_request_ids,
            stored_issue_doc_ids,
            stored_pull_request_doc_ids,
        ) = await asyncio.gather(
            self.client.list_issue_numbers_graphql(
                repo_ref.owner,
                repo_ref.repo,
                since=sync_from_dt,
            ),
            self.client.list_pull_request_numbers_graphql(
                repo_ref.owner,
                repo_ref.repo,
                since=sync_from_dt,
            ),
            self.repository.list_github_record_ids(
                owner=repo_ref.owner,
                repo=repo_ref.repo,
                entity_type="issue",
                since=sync_from_dt,
            ),
            self.repository.list_github_record_ids(
                owner=repo_ref.owner,
                repo=repo_ref.repo,
                entity_type="pr",
                since=sync_from_dt,
            ),
        )

        issue_item = self._build_gap_item(
            record_type="issue",
            expected_ids=expected_issue_ids,
            stored_ids=self._extract_record_ids_from_doc_ids(stored_issue_doc_ids),
            stored_count=len(stored_issue_doc_ids),
        )
        pull_request_item = self._build_gap_item(
            record_type="pull_request",
            expected_ids=expected_pull_request_ids,
            stored_ids=self._extract_record_ids_from_doc_ids(stored_pull_request_doc_ids),
            stored_count=len(stored_pull_request_doc_ids),
        )

        return GithubRecordGapReport(records=[issue_item, pull_request_item])

    async def retry_missing_records(
        self,
        *,
        repo_id: int,
        sync_days: int | None = None,
        sync_from_dt: datetime | None = None,
        issue_ids: list[str] | None = None,
        pull_request_ids: list[str] | None = None,
    ) -> GithubRecordRetryResult:
        repo_ref = await self._get_repo_ref(repo_id)
        requested_issue_ids = list(issue_ids or [])
        requested_pull_request_ids = list(pull_request_ids or [])
        retry_tasks = []

        if requested_issue_ids:
            retry_tasks.append(
                self._retry_record_batch(
                    repo_ref=repo_ref,
                    record_type="issue",
                    requested_ids=requested_issue_ids,
                )
            )

        if requested_pull_request_ids:
            retry_tasks.append(
                self._retry_record_batch(
                    repo_ref=repo_ref,
                    record_type="pull_request",
                    requested_ids=requested_pull_request_ids,
                )
            )

        result_items = await asyncio.gather(*retry_tasks) if retry_tasks else []
        return GithubRecordRetryResult(records=result_items)

    async def incremental_sync(
        self,
        *,
        repo_id: int,
        record_type: str,
        record_id: str,
        event_kind: str,
        since: datetime | None,
        audit_context: SyncAuditContext | None,
    ) -> dict[str, int | bool]:
        repo_names = await self._get_repo_names_by_ids([repo_id])
        if not repo_names:
            raise ValueError(f"github repository not found: repo_id={repo_id}")

        owner, repo = repo_names[0].split("/", 1)
        normalized_record_type = record_type.strip().lower()
        normalized_event_kind = event_kind.strip().lower()

        if normalized_event_kind == "deleted":
            return await self._delete_incremental_record(
                owner=owner,
                repo=repo,
                record_type=normalized_record_type,
                record_id=record_id,
            )

        await self._ensure_premapped_github_names_async(force=False)
        name_map = self._get_github_name_map()

        if normalized_record_type == "issue":
            result = await self._sync_issues(
                owner,
                repo,
                name_map=name_map,
                since=since,
                audit_context=audit_context,
            )
        elif normalized_record_type == "pull_request":
            result = await self._sync_pull_requests(
                owner,
                repo,
                name_map=name_map,
                since=since,
                audit_context=audit_context,
            )
        else:
            raise ValueError(f"unsupported github record_type: {record_type}")

        return {
            "synced": int(result.get("synced", 0)),
            "errors": int(result.get("errors", 0)),
            "skipped": False,
        }

    async def _delete_incremental_record(
        self,
        *,
        owner: str,
        repo: str,
        record_type: str,
        record_id: str,
    ) -> dict[str, int | bool]:
        if record_type == "issue":
            doc_id = f"github:issue:{owner}/{repo}:{record_id}"
        elif record_type == "pull_request":
            doc_id = f"github:pr:{owner}/{repo}:{record_id}"
        else:
            raise ValueError(f"unsupported github delete record_type: {record_type}")

        await self.repository.delete_documents([doc_id])
        logger.info(
            "[GITHUB][INCREMENTAL] Deleted document: installation_id=%s, record_type=%s, doc_id=%s",
            self.installation_id,
            record_type,
            doc_id,
        )
        return {
            "synced": 1,
            "errors": 0,
            "skipped": False,
        }

    # ============================================================
    # Issue Sync
    # ============================================================

    async def _sync_issues(
        self,
        owner: str,
        repo: str,
        *,
        name_map: dict[str, str | None],
        since: datetime | None = None,
        audit_context: SyncAuditContext | None = None,
    ) -> dict[str, int]:
        """
        Repository의 Issue 동기화

        Args:
            owner: Repository owner
            repo: Repository name
            since: 이 시간 이후 업데이트된 Issue만 동기화

        Returns:
            동기화 결과 {"synced": N, "errors": N}
        """
        full_name = f"{owner}/{repo}"
        total_synced = 0
        errors = 0

        try:
            # 동기화 시작
            self._start_sync(full_name, GithubEntityType.ISSUE, SyncOperation.ISSUE_SYNC)

            batch_idx = 0
            async for issue_batch in self.client.list_issues_graphql(
                owner=owner,
                repo=repo,
                since=since,
            ):
                batch_idx += 1
                batch_documents, batch_doc_ids, batch_errors = await run_in_threadpool(
                    self._build_issue_batch_sync,
                    owner,
                    repo,
                    issue_batch,
                    name_map,
                )
                errors += batch_errors

                if not batch_documents:
                    continue

                if self.summarizer:
                    batch_documents = await self._summarize_documents(
                        batch_documents,
                        repo_full_name=full_name,
                        entity_type="issue",
                        audit_context=audit_context,
                    )

                await self.repository.upsert_documents(
                    batch_documents,
                    batch_doc_ids,
                    audit_context=audit_context,
                    context=(
                        f"entity_type=issue,repo={full_name},batch={batch_idx},"
                        f"doc_count={len(batch_documents)}"
                    ),
                )
                total_synced += len(batch_documents)

                logger.info(
                    f"[GITHUB][{SyncOperation.ISSUE_SYNC}] Batch {batch_idx}: upserted {len(batch_documents)} issue docs in {full_name}"
                )

            self._complete_sync(full_name, GithubEntityType.ISSUE, total_synced, SyncOperation.ISSUE_SYNC)
            return {"synced": total_synced, "errors": errors}

        except GitHubRateLimitError as e:
            self._handle_rate_limit(full_name, GithubEntityType.ISSUE, e, SyncOperation.ISSUE_SYNC)
            raise

        except Exception as e:
            logger.error(f"[GITHUB][{SyncOperation.ISSUE_SYNC}] Sync failed for {full_name}: {e}", exc_info=True)
            self._fail_sync(full_name, GithubEntityType.ISSUE, str(e), SyncOperation.ISSUE_SYNC)
            return {"synced": total_synced, "errors": errors + 1}

    # ============================================================
    # Pull Request Sync
    # ============================================================

    async def _sync_pull_requests(
        self,
        owner: str,
        repo: str,
        *,
        name_map: dict[str, str | None],
        since: datetime | None = None,
        audit_context: SyncAuditContext | None = None,
    ) -> dict[str, int]:
        """
        Repository의 Pull Request 동기화

        GraphQL 배치 쿼리로 PR 목록과 상세 정보(Reviews, Comments, Commits)를 한 번에 조회.
        REST API 1+N회 호출 대신 GraphQL 페이지네이션으로 최소화.

        Note: File Changes는 조회하지 않음 (Commits으로 대체)

        Args:
            owner: Repository owner
            repo: Repository name
            since: 이 시간 이후 업데이트된 PR만 동기화

        Returns:
            동기화 결과 {"synced": N, "errors": N}
        """
        full_name = f"{owner}/{repo}"
        total_synced = 0
        errors = 0

        try:
            # 동기화 시작
            self._start_sync(full_name, GithubEntityType.PULL_REQUEST, SyncOperation.PR_SYNC)

            batch_idx = 0
            async for pr_batch in self.client.list_pull_requests_graphql(
                owner=owner,
                repo=repo,
                since=since,
            ):
                batch_idx += 1
                batch_documents, batch_doc_ids, batch_errors = await run_in_threadpool(
                    self._build_pull_request_batch_sync,
                    owner,
                    repo,
                    pr_batch,
                    name_map,
                )
                errors += batch_errors

                if not batch_documents:
                    continue

                if self.summarizer:
                    batch_documents = await self._summarize_documents(
                        batch_documents,
                        repo_full_name=full_name,
                        entity_type="pull_request",
                        audit_context=audit_context,
                    )

                await self.repository.upsert_documents(
                    batch_documents,
                    batch_doc_ids,
                    audit_context=audit_context,
                    context=(
                        f"entity_type=pull_request,repo={full_name},batch={batch_idx},"
                        f"doc_count={len(batch_documents)}"
                    ),
                )
                total_synced += len(batch_documents)

                logger.info(
                    f"[GITHUB][{SyncOperation.PR_SYNC}] Batch {batch_idx}: upserted {len(batch_documents)} PR docs in {full_name}"
                )

            self._complete_sync(full_name, GithubEntityType.PULL_REQUEST, total_synced, SyncOperation.PR_SYNC)
            return {"synced": total_synced, "errors": errors}

        except GitHubRateLimitError as e:
            self._handle_rate_limit(full_name, GithubEntityType.PULL_REQUEST, e, SyncOperation.PR_SYNC)
            raise

        except Exception as e:
            logger.error(f"[GITHUB][{SyncOperation.PR_SYNC}] Sync failed for {full_name}: {e}", exc_info=True)
            self._fail_sync(full_name, GithubEntityType.PULL_REQUEST, str(e), SyncOperation.PR_SYNC)
            return {"synced": total_synced, "errors": errors + 1}

    async def _summarize_documents(
        self,
        documents: list[Document],
        *,
        repo_full_name: str,
        entity_type: str,
        audit_context: SyncAuditContext | None = None,
    ) -> list[Document]:
        """
        문서들의 page_content를 LLM으로 요약하여 교체

        contextual_content(구조화된 정보 포함)를 요약 입력으로 사용하여
        더 풍부한 컨텍스트 기반 요약 생성.

        Args:
            documents: 요약할 Document 리스트

        Returns:
            page_content가 요약된 Document 리스트
        """
        if not self.summarizer or not documents:
            return documents

        # SummarizeRequest 리스트 생성 (source + entity_type → source_type)
        requests = []
        for doc in documents:
            content = doc.metadata.get("contextual_content", doc.page_content)
            entity_type = doc.metadata.get("entity_type", "issue")
            source_type = f"github_{entity_type}"  # github_issue, github_pr, github_commit
            requests.append(SummarizeRequest(content=content, source_type=source_type))

        # 일괄 요약
        summarized = await self.summarizer.summarize_batch(
            requests,
            audit_context=audit_context,
            context=(
                f"entity_type={entity_type},repo={repo_full_name},"
                f"doc_count={len(documents)}"
            ),
        )

        # 요약된 텍스트로 교체
        for doc, summary in zip(documents, summarized):
            doc.page_content = summary

        logger.debug(f"Summarized {len(documents)} documents for embedding")
        return documents
