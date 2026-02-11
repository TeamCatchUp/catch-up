"""
GitHub Ingestion Service

GitHub 데이터 동기화 및 PGVector 적재를 담당하는 서비스.

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
from datetime import datetime, timezone, timedelta
from typing import Any

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
    GitHubUser,
    GitHubIssue,
    GitHubPullRequest,
    GitHubCommit,
    PRFileContext,
)
from catchup.connectors.github.transformers import GitHubTransformer
from catchup.components.vector_db.pgvector.repository import PGVectorRepository
from catchup.components.summarizer import SummarizerService, SummarizeRequest, get_summarizer_service
from catchup.configs.config import settings
from catchup.db.github import sync_repository as github_sync
from catchup.db.github import domain_repository as github_entities
from catchup.db.github import installation_repository as github_installation
from catchup.db.models import GitHubEntityType, GitHubSyncStatus, GithubInstallationType

logger = logging.getLogger(__name__)


# Skip 가능한 에러 (로깅만 하고 진행)
SKIPPABLE_ERRORS = {
    "not_found",  # 삭제된 리소스
    "forbidden",  # 권한 없음
    "gone",  # 더 이상 존재하지 않음
}


class GitHubIngestionService:
    """
    GitHub 데이터 수집 및 PGVector 적재 서비스

    Usage:
        service = GitHubIngestionService(installation_id, access_token)
        await service.initialize()
        result = await service.full_sync(db, repo_ids=[12345, 67890])
    """

    def __init__(
        self,
        installation_id: int,
        access_token: str,
        enable_summarization: bool = True,
    ):
        """
        Args:
            installation_id: GitHub App Installation ID
            access_token: Installation Access Token
            enable_summarization: 임베딩 전 LLM 요약 활성화 여부
        """
        self.installation_id = installation_id
        self.access_token = access_token
        self.enable_summarization = enable_summarization

        self.client = GitHubApiClient(access_token)
        self.transformer: GitHubTransformer | None = None
        self.repository = PGVectorRepository()
        self.summarizer: SummarizerService | None = None

        # 사용자 캐시 (멘션 변환용)
        self.user_cache: dict[str, GitHubUser] = {}

    async def initialize(self) -> None:
        """
        서비스 초기화

        - PGVector 초기화
        - Transformer 생성
        - Summarizer 초기화 (요약 활성화 시)
        """
        await self.repository.initialize()
        self.transformer = GitHubTransformer(self.user_cache)

        # Summarizer 초기화 (요약 활성화 시)
        if self.enable_summarization:
            self.summarizer = get_summarizer_service()
            logger.info("Summarization enabled for embedding optimization")

        logger.info(f"GitHubIngestionService initialized for installation {self.installation_id}")

    # ============================================================
    # Full Sync
    # ============================================================

    async def full_sync(
        self,
        db: Session,
        repo_ids: list[int] | None = None,
        sync_issues: bool = True,
        sync_prs: bool = True,
        sync_commits: bool = False,  # Deprecated: Commit은 PR Document에 포함
        sync_repos: bool = True,
        sync_users: bool = False,  # Installation 시점에 동기화되므로 기본 False
        branch: str | None = None,
    ) -> dict[str, Any]:
        """
        전체 동기화 수행

        Args:
            db: SQLAlchemy Session
            repo_ids: 동기화할 Repository ID 목록 (None이면 모든 접근 가능 레포)
            sync_issues: Issue 동기화 여부
            sync_prs: PR 동기화 여부
            sync_commits: Deprecated (무시됨). Commit은 PR Document에 포함됨
            sync_repos: Repository 메타데이터 동기화 여부
            sync_users: User 동기화 여부 (기본 False - Installation 시점에 동기화됨)
            branch: 코드베이스 동기화 대상 브랜치 (향후 구현 예정, 현재 미사용)

        Returns:
            동기화 결과 딕셔너리
        """
        results = {
            "repositories": {"synced": 0, "errors": 0},
            "issues": {"synced": 0, "errors": 0},
            "pull_requests": {"synced": 0, "errors": 0},
            "users": {"synced": 0, "errors": 0},
        }

        try:
            # 0. User 동기화 (Organization 멤버 → RDBMS)
            if sync_users:
                user_result = await self._sync_users(db)
                results["users"]["synced"] = user_result.get("synced", 0)
                results["users"]["errors"] = user_result.get("errors", 0)

            # 1. Repository 목록 조회 및 RDBMS 저장
            if sync_repos or repo_ids is None:
                repos_to_sync = await self._sync_repositories(db)
                results["repositories"]["synced"] = len(repos_to_sync)
            else:
                # repo_ids로 full_name 조회
                repos_to_sync = self._get_repo_names_by_ids(db, repo_ids)

            # 필터링: 지정된 repo_ids만 동기화
            if repo_ids:
                target_names = set(self._get_repo_names_by_ids(db, repo_ids))
                repos_to_sync = [r for r in repos_to_sync if r in target_names]

            logger.info(f"Syncing {len(repos_to_sync)} repositories")

            # 2. 각 Repository별 동기화
            for repo_full_name in repos_to_sync:
                try:
                    owner, repo = repo_full_name.split("/", 1)

                    # Issue 동기화
                    if sync_issues:
                        issue_result = await self._sync_issues(db, owner, repo)
                        results["issues"]["synced"] += issue_result.get("synced", 0)
                        results["issues"]["errors"] += issue_result.get("errors", 0)

                    # PR 동기화 (Commits 포함)
                    if sync_prs:
                        pr_result = await self._sync_pull_requests(db, owner, repo)
                        results["pull_requests"]["synced"] += pr_result.get("synced", 0)
                        results["pull_requests"]["errors"] += pr_result.get("errors", 0)

                except Exception as e:
                    logger.error(f"Failed to sync repository {repo_full_name}: {e}")
                    results["repositories"]["errors"] += 1

            return results

        except Exception as e:
            logger.error(f"Full sync failed: {e}")
            raise

    async def _sync_users(self, db: Session) -> dict[str, int]:
        """
        Organization 멤버 동기화 (RDBMS 저장)

        Installation이 Organization에 설치된 경우에만 동기화.
        User 계정에 설치된 경우 해당 User만 저장.

        Returns:
            동기화 결과 {"synced": N, "errors": N}
        """
        try:
            # Installation 정보 조회
            installation = github_installation.get_installation_by_installation_id(
                db, self.installation_id
            )

            if not installation:
                logger.warning(f"Installation {self.installation_id} not found in DB")
                return {"synced": 0, "errors": 0}

            account_login = installation.account_login
            account_type = installation.account_type

            logger.info(
                f"Syncing users for {account_type} '{account_login}' "
                f"(installation_id={self.installation_id})"
            )

            users_data = []

            if account_type == GithubInstallationType.ORGANIZATION:
                # Organization 멤버 조회 (GraphQL)
                try:
                    members = await self.client.list_org_members_graphql(account_login)
                    logger.info(f"Found {len(members)} members in organization '{account_login}'")
                    users_data.extend(members)
                except GitHubApiError as e:
                    # Organization 멤버 조회 권한이 없을 수 있음
                    logger.warning(
                        f"Failed to fetch org members for '{account_login}': {e}. "
                        "Organization members permission may be required."
                    )
                    return {"synced": 0, "errors": 1}

            else:
                # User 계정인 경우 해당 User 정보만 조회
                try:
                    user_info = await self.client.get_user(account_login)
                    if user_info:
                        users_data.append({
                            "database_id": user_info.get("id"),
                            "login": user_info.get("login"),
                            "name": user_info.get("name"),
                            "email": user_info.get("email"),
                            "avatar_url": user_info.get("avatar_url"),
                            "org_role": None,
                        })
                        logger.info(f"Found user '{account_login}'")
                except GitHubApiError as e:
                    logger.warning(f"Failed to fetch user '{account_login}': {e}")
                    return {"synced": 0, "errors": 1}

            # RDBMS에 벌크 저장
            if users_data:
                github_entities.upsert_users_bulk(db, users_data)

                # User 캐시 업데이트 (멘션 변환용)
                for user in users_data:
                    self.user_cache[user["login"]] = GitHubUser(
                        id=user["database_id"],
                        login=user["login"],
                        avatar_url=user.get("avatar_url"),
                    )

            logger.info(f"User sync completed: {len(users_data)} users synced")
            return {"synced": len(users_data), "errors": 0}

        except Exception as e:
            logger.error(f"User sync failed: {e}")
            return {"synced": 0, "errors": 1}

    async def _sync_repositories(self, db: Session) -> list[str]:
        """
        Installation에서 접근 가능한 Repository 목록 조회 및 RDBMS 저장

        Returns:
            Repository full_name 리스트
        """
        try:
            repos_data = await self.client.list_installation_repos()
            logger.info(f"Found {len(repos_data)} accessible repositories")

            # RDBMS에 벌크 저장
            github_entities.upsert_repositories_bulk(
                db, self.installation_id, repos_data
            )

            return [repo["full_name"] for repo in repos_data]

        except GitHubApiError as e:
            logger.error(f"Failed to list installation repositories: {e}")
            return []

    def _get_repo_names_by_ids(self, db: Session, repo_ids: list[int]) -> list[str]:
        """
        Repository ID 목록으로 full_name 조회

        Args:
            db: SQLAlchemy Session
            repo_ids: GitHub Repository ID 목록

        Returns:
            Repository full_name 리스트
        """
        repos = github_entities.get_repositories_by_installation(db, self.installation_id)
        repo_id_set = set(repo_ids)
        return [repo.full_name for repo in repos if repo.repo_id in repo_id_set]

    # ============================================================
    # Issue Sync
    # ============================================================

    async def _sync_issues(
        self,
        db: Session,
        owner: str,
        repo: str,
        since: datetime | None = None,
    ) -> dict[str, int]:
        """
        Repository의 Issue 동기화

        Args:
            db: SQLAlchemy Session
            owner: Repository owner
            repo: Repository name
            since: 이 시간 이후 업데이트된 Issue만 동기화

        Returns:
            동기화 결과 {"synced": N, "errors": N}
        """
        full_name = f"{owner}/{repo}"
        documents = []
        doc_ids = []
        errors = 0

        try:
            # 동기화 시작 상태 기록
            github_sync.create_or_update_sync_state(
                db, self.installation_id, full_name,
                GitHubEntityType.ISSUE, GitHubSyncStatus.IN_PROGRESS
            )

            # Issue 목록 조회
            issues_data = await self.client.list_all_issues(
                owner=owner, repo=repo, state="all", since=since
            )
            logger.info(f"Found {len(issues_data)} issues in {full_name}")

            for issue_data in issues_data:
                try:
                    # 코멘트 조회
                    comments = []
                    if issue_data.get("comments", 0) > 0:
                        comments = await self.client.get_issue_comments(
                            owner, repo, issue_data["number"]
                        )

                    # 파싱 및 변환
                    issue = self.transformer.parse_issue(issue_data, comments)
                    doc = self.transformer.transform_issue(
                        issue, owner, repo, self.installation_id
                    )
                    documents.append(doc)
                    doc_ids.append(doc.id)

                except Exception as e:
                    logger.warning(f"Failed to process issue #{issue_data.get('number')}: {e}")
                    errors += 1

            # PGVector에 Upsert
            if documents:
                # 요약 적용 (summarizer가 활성화된 경우)
                if self.summarizer:
                    documents = await self._summarize_documents(documents)
                await self.repository.upsert_documents(documents, doc_ids)

            # 동기화 완료 상태 기록
            github_sync.mark_sync_completed(
                db, self.installation_id, full_name,
                GitHubEntityType.ISSUE, len(documents)
            )

            return {"synced": len(documents), "errors": errors}

        except GitHubRateLimitError as e:
            logger.warning(f"Rate limit hit during issue sync, waiting {e.retry_after}s")
            github_sync.mark_sync_failed(
                db, self.installation_id, full_name,
                GitHubEntityType.ISSUE, f"Rate limit: retry after {e.retry_after}s"
            )
            raise

        except Exception as e:
            logger.error(f"Issue sync failed for {full_name}: {e}")
            github_sync.mark_sync_failed(
                db, self.installation_id, full_name,
                GitHubEntityType.ISSUE, str(e)[:1000]
            )
            return {"synced": len(documents), "errors": errors + 1}

    # ============================================================
    # Pull Request Sync
    # ============================================================

    async def _sync_pull_requests(
        self,
        db: Session,
        owner: str,
        repo: str,
        since: datetime | None = None,
    ) -> dict[str, int]:
        """
        Repository의 Pull Request 동기화

        GraphQL 배치 쿼리로 PR 목록과 상세 정보(Reviews, Comments, Commits)를 한 번에 조회.
        REST API 1+N회 호출 대신 GraphQL 페이지네이션으로 최소화.

        Note: File Changes는 조회하지 않음 (Commits으로 대체)

        Args:
            db: SQLAlchemy Session
            owner: Repository owner
            repo: Repository name
            since: 이 시간 이후 업데이트된 PR만 동기화

        Returns:
            동기화 결과 {"synced": N, "errors": N}
        """
        full_name = f"{owner}/{repo}"
        documents = []
        doc_ids = []
        errors = 0

        try:
            # 동기화 시작 상태 기록
            github_sync.create_or_update_sync_state(
                db, self.installation_id, full_name,
                GitHubEntityType.PULL_REQUEST, GitHubSyncStatus.IN_PROGRESS
            )

            # GraphQL 배치 쿼리로 PR 목록 + 상세 정보 한 번에 조회
            prs_data = await self.client.list_pull_requests_graphql(
                owner=owner,
                repo=repo,
                states=None,  # 모든 상태
                since=since,
                reviews_limit=settings.GITHUB_SYNC_REVIEWS_LIMIT,
                commits_limit=100,
            )
            logger.info(f"Found {len(prs_data)} pull requests in {full_name} (GraphQL batch)")

            for idx, pr_data in enumerate(prs_data):
                try:
                    # 진행 상황 로깅
                    if (idx + 1) % 50 == 0:
                        logger.info(f"Processing PR {idx + 1}/{len(prs_data)} in {full_name}")

                    # GraphQL 응답에 포함된 상세 정보 추출
                    reviews = pr_data.pop("_reviews", [])
                    comments = pr_data.pop("_comments", [])
                    commits = pr_data.pop("_commits", [])

                    # 파싱 및 변환
                    pr = self.transformer.parse_pull_request(pr_data, reviews, comments, commits)
                    doc = self.transformer.transform_pull_request(
                        pr, owner, repo, self.installation_id
                    )
                    documents.append(doc)
                    doc_ids.append(doc.id)

                except Exception as e:
                    import traceback
                    logger.warning(f"Failed to process PR #{pr_data.get('number')}: {e}")
                    logger.debug(f"PR processing error traceback:\n{traceback.format_exc()}")
                    errors += 1

            # PGVector에 Upsert
            if documents:
                # 요약 적용 (summarizer가 활성화된 경우)
                if self.summarizer:
                    documents = await self._summarize_documents(documents)
                await self.repository.upsert_documents(documents, doc_ids)

            # 동기화 완료 상태 기록
            github_sync.mark_sync_completed(
                db, self.installation_id, full_name,
                GitHubEntityType.PULL_REQUEST, len(documents)
            )

            logger.info(f"PR sync completed for {full_name}: {len(documents)} synced, {errors} errors")
            return {"synced": len(documents), "errors": errors}

        except GitHubRateLimitError as e:
            logger.warning(f"Rate limit hit during PR sync, waiting {e.retry_after}s")
            github_sync.mark_sync_failed(
                db, self.installation_id, full_name,
                GitHubEntityType.PULL_REQUEST, f"Rate limit: retry after {e.retry_after}s"
            )
            raise

        except Exception as e:
            logger.error(f"PR sync failed for {full_name}: {e}")
            github_sync.mark_sync_failed(
                db, self.installation_id, full_name,
                GitHubEntityType.PULL_REQUEST, str(e)[:1000]
            )
            return {"synced": len(documents), "errors": errors + 1}

    # ============================================================
    # Incremental Sync
    # ============================================================

    async def incremental_sync(
        self,
        db: Session,
        repo_ids: list[int] | None = None,
    ) -> dict[str, Any]:
        """
        증분 동기화 수행

        마지막 성공적인 동기화 이후 변경된 데이터만 동기화.

        Args:
            db: SQLAlchemy Session
            repo_ids: 동기화할 Repository ID 목록 (None이면 모든 접근 가능 레포)

        Returns:
            동기화 결과 딕셔너리
        """
        results = {
            "repositories": {"synced": 0, "errors": 0},
            "issues": {"synced": 0, "errors": 0},
            "pull_requests": {"synced": 0, "errors": 0},
        }

        try:
            # Note: User는 Installation 시점에 동기화되므로 여기서는 생략

            # Repository 목록 조회
            repos_to_sync = await self._sync_repositories(db)
            results["repositories"]["synced"] = len(repos_to_sync)

            # 필터링: 지정된 repo_ids만 동기화
            if repo_ids:
                target_names = set(self._get_repo_names_by_ids(db, repo_ids))
                repos_to_sync = [r for r in repos_to_sync if r in target_names]

            for repo_full_name in repos_to_sync:
                try:
                    owner, repo = repo_full_name.split("/", 1)

                    # 각 엔티티 타입별 마지막 동기화 시간 조회
                    issue_state = github_sync.get_sync_state(
                        db, self.installation_id, repo_full_name, GitHubEntityType.ISSUE
                    )
                    pr_state = github_sync.get_sync_state(
                        db, self.installation_id, repo_full_name, GitHubEntityType.PULL_REQUEST
                    )

                    # Issue 증분 동기화
                    issue_since = issue_state.last_successful_sync_at if issue_state else None
                    issue_result = await self._sync_issues(db, owner, repo, since=issue_since)
                    results["issues"]["synced"] += issue_result.get("synced", 0)
                    results["issues"]["errors"] += issue_result.get("errors", 0)

                    # PR 증분 동기화
                    pr_since = pr_state.last_successful_sync_at if pr_state else None
                    pr_result = await self._sync_pull_requests(db, owner, repo, since=pr_since)
                    results["pull_requests"]["synced"] += pr_result.get("synced", 0)
                    results["pull_requests"]["errors"] += pr_result.get("errors", 0)

                except Exception as e:
                    logger.error(f"Incremental sync failed for {repo_full_name}: {e}")
                    results["repositories"]["errors"] += 1

            return results

        except Exception as e:
            logger.error(f"Incremental sync failed: {e}")
            raise

    async def _summarize_documents(
        self,
        documents: list[Document],
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
        summarized = await self.summarizer.summarize_batch(requests)

        # 요약된 텍스트로 교체
        for doc, summary in zip(documents, summarized):
            doc.page_content = summary

        logger.debug(f"Summarized {len(documents)} documents for embedding")
        return documents


# ============================================================
# Legacy GithubService (하위 호환성 유지)
# ============================================================

class GithubService:
    """
    기존 GithubService (PR 컨텍스트 조회용)

    Note: 새로운 코드에서는 GitHubIngestionService 사용 권장
    """

    def __init__(self):
        import httpx
        self.token = settings.GITHUB_TOKEN
        self.base_url = settings.GITHUB_BASE_URL
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "application/vnd.github.v3+json",
        }

    async def get_pr_context(
        self, owner: str, repo: str, pr_number: int
    ) -> list[PRFileContext]:
        import httpx

        async with httpx.AsyncClient(headers=self.headers, timeout=20.0) as client:
            try:
                base_path = f"{self.base_url}/{owner}/{repo}/pulls/{pr_number}"
                files_url = f"{base_path}/files"
                comments_url = f"{base_path}/comments"

                logger.info(f"Fetching file context for PR {owner}/{repo}#{pr_number}")

                # Diff와 Review를 병렬 조회
                responses = await asyncio.gather(
                    client.get(files_url, params={"per_page": 100}),
                    client.get(comments_url, params={"per_page": 100}),
                )

                for resp in responses:
                    resp.raise_for_status()

                files_data = responses[0].json()
                comments_data = responses[1].json()

                return self._merge_files_and_comments(files_data, comments_data)

            except httpx.HTTPStatusError as e:
                logger.error(
                    f"GitHub API Error: {e.response.status_code} - {e.response.text}"
                )
                return []
            except Exception as e:
                logger.error(f"Failed to fetch PR file context: {e}")
                return []

    def _merge_files_and_comments(
        self, files_data: list[dict[str, Any]], comments_data: list[dict[str, Any]]
    ) -> list[PRFileContext]:
        from catchup.connectors.github.schemas import PRComment

        merged_files: dict[str, dict] = {}

        for file in files_data:
            filename = file["filename"]
            status = file["status"]
            patch_content = file.get("patch", "")
            prev_filename = file.get("previous_filename")

            additions = file["additions"]
            deletions = file["deletions"]

            # RENAMED이고 additions, deletions이 0인 경우 파일 이름만 변경
            if status == "renamed":
                if additions == 0 and deletions == 0:
                    patch_content = None

            merged_files[filename] = {
                "path": filename,
                "status": status,
                "additions": additions,
                "deletions": deletions,
                "previous_filename": prev_filename,
                "patch": patch_content,
                "comments": [],
            }

        for comment in comments_data:
            path = comment["path"]

            if path in merged_files:
                comment_obj = {
                    "id": comment["id"],
                    "author": comment["user"]["login"]
                    if comment["user"]
                    else "unknown",
                    "body": comment["body"],
                    "created_at": comment["created_at"],
                    "diff_hunk": comment.get("diff_hunk", ""),
                    "line": comment.get("line"),
                    "original_line": comment.get("original_line"),
                }
                merged_files[path]["comments"].append(PRComment(**comment_obj))

        result = []
        for file_data in merged_files.values():
            result.append(PRFileContext(**file_data))

        return result
