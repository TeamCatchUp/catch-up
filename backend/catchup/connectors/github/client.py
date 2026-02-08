"""
GitHub REST API Client

githubkit 기반 비동기 클라이언트.

## GitHub API 구조

GitHub REST API v3를 사용하며, GitHub App Installation Token으로 인증.

- Installation Access Token: GitHub App이 설치된 Organization/User의 리소스에 접근
- Rate Limit: 5,000 requests/hour (인증된 요청)
- 페이지네이션: per_page (최대 100), page 파라미터 사용

## Rate Limiting

- X-RateLimit-Remaining: 남은 요청 수
- X-RateLimit-Reset: Rate limit 리셋 Unix timestamp
- 429/403 응답 시 X-RateLimit-Reset까지 대기
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from githubkit import GitHub, Response
from githubkit.exception import RequestFailed, RequestTimeout
from githubkit.versions.latest.models import (
    Issue,
    PullRequest,
    Commit,
    Repository,
    IssueComment,
    PullRequestReview,
    DiffEntry,
)

from catchup.configs.config import settings

logger = logging.getLogger(__name__)


# ============================================================
# 예외 클래스 정의
# ============================================================

from catchup.connectors.base import (
    AuthenticationError,
    ConnectorApiError,
    NotFoundError,
    RateLimitError,
)


class GitHubApiError(ConnectorApiError):
    """
    GitHub API 에러 기본 클래스

    모든 GitHub API 관련 예외의 부모 클래스.
    status_code를 통해 HTTP 상태 코드 확인 가능.
    """

    service = "github"


class GitHubRateLimitError(RateLimitError, GitHubApiError):
    """
    Rate limit 초과 에러 (HTTP 429 또는 403 with rate limit)

    retry_after 속성으로 재시도까지 대기해야 할 시간(초) 확인 가능.

    처리 방법:
        try:
            await client.list_issues(...)
        except GitHubRateLimitError as e:
            await asyncio.sleep(e.retry_after)
            # 재시도
    """

    service = "github"


class GitHubAuthError(AuthenticationError, GitHubApiError):
    """
    인증 에러 (HTTP 401)

    Installation Access Token이 만료되었거나 유효하지 않을 때 발생.

    처리 방법:
        try:
            await client.list_issues(...)
        except GitHubAuthError:
            # GitHubAppService.get_installation_access_token()으로 토큰 재발급 후 재시도
    """

    service = "github"


class GitHubNotFoundError(NotFoundError, GitHubApiError):
    """
    리소스를 찾을 수 없음 (HTTP 404)

    Repository가 삭제되었거나 접근 권한이 없을 때 발생.
    """

    service = "github"


# ============================================================
# GitHub API 클라이언트
# ============================================================

class GitHubApiClient:
    """
    GitHub REST API 비동기 클라이언트

    githubkit을 래핑하여 Rate limiting, 페이지네이션, 에러 핸들링을 처리.

    - 초기화
    client = GitHubApiClient(access_token="ghs_xxxx...")

    - Rate Limiting
    - 동시 요청 수: GITHUB_SYNC_MAX_CONCURRENT_REQUESTS (기본값: 10)
    - 요청 간 딜레이: GITHUB_API_RATE_LIMIT_DELAY (기본값: 0.1초)
    - 429/403 Rate Limit 응답 시 X-RateLimit-Reset까지 대기 후 재시도

    Attributes:
        access_token: GitHub Installation Access Token
    """

    def __init__(self, access_token: str):
        self.access_token = access_token
        self._github = GitHub(access_token)

        # Rate limiting을 위한 세마포어
        self._semaphore = asyncio.Semaphore(int(settings.GITHUB_SYNC_MAX_CONCURRENT_REQUESTS))

        # 요청 간 딜레이 (초)
        self._rate_limit_delay = float(settings.GITHUB_API_RATE_LIMIT_DELAY)

    def _handle_error(self, e: RequestFailed) -> None:
        """
        GitHub API 에러를 적절한 예외로 변환
        """
        status_code = e.response.status_code if e.response else None

        if status_code == 401:
            raise GitHubAuthError("Invalid or expired access token")

        if status_code == 404:
            raise GitHubNotFoundError("Resource not found")

        if status_code == 403:
            # Rate limit 확인
            headers = e.response.headers if e.response else {}
            remaining = int(headers.get("x-ratelimit-remaining", 1))

            if remaining == 0:
                reset_timestamp = int(headers.get("x-ratelimit-reset", 0))
                now = int(datetime.now(timezone.utc).timestamp())
                retry_after = max(reset_timestamp - now, 60)
                raise GitHubRateLimitError(retry_after=retry_after, remaining=0)

        if status_code == 429:
            headers = e.response.headers if e.response else {}
            retry_after = int(headers.get("retry-after", 60))
            raise GitHubRateLimitError(retry_after=retry_after)

        raise GitHubApiError(str(e), status_code)

    async def _with_rate_limit(self, coro):
        """
        Rate limiting을 적용하여 코루틴 실행
        """
        async with self._semaphore:
            try:
                result = await coro
                await asyncio.sleep(self._rate_limit_delay)
                return result
            except RequestFailed as e:
                self._handle_error(e)
            except RequestTimeout as e:
                raise GitHubApiError(f"Request timeout: {e}", None)

    # ============================================================
    # Repository APIs
    # ============================================================

    async def get_repository(self, owner: str, repo: str) -> dict[str, Any]:
        """
        Repository 정보 조회

        Args:
            owner: Repository owner (user or org)
            repo: Repository name

        Returns:
            Repository 정보 딕셔너리
        """
        response = await self._with_rate_limit(
            self._github.rest.repos.async_get(owner=owner, repo=repo)
        )
        return response.parsed_data.model_dump() if response else {}

    async def list_installation_repos(self, per_page: int = 100) -> list[dict[str, Any]]:
        """
        Installation에서 접근 가능한 모든 Repository 목록 조회

        Args:
            per_page: 페이지당 결과 수 (최대 100)

        Returns:
            Repository 정보 리스트
        """
        repos = []
        page = 1

        while True:
            response = await self._with_rate_limit(
                self._github.rest.apps.async_list_repos_accessible_to_installation(
                    per_page=per_page,
                    page=page
                )
            )

            if not response or not response.parsed_data.repositories:
                break

            for repo in response.parsed_data.repositories:
                repos.append(repo.model_dump())

            if len(response.parsed_data.repositories) < per_page:
                break

            page += 1

        return repos

    # ============================================================
    # Issue APIs
    # ============================================================

    async def list_issues(
        self,
        owner: str,
        repo: str,
        state: str = "all",
        since: datetime | None = None,
        per_page: int = 100,
        page: int = 1,
    ) -> list[dict[str, Any]]:
        """
        Repository의 Issue 목록 조회 (PR 제외)

        Args:
            owner: Repository owner
            repo: Repository name
            state: Issue 상태 (open, closed, all)
            since: 이 시간 이후 업데이트된 Issue만 조회
            per_page: 페이지당 결과 수
            page: 페이지 번호

        Returns:
            Issue 정보 리스트 (pull_request 필드가 없는 것만)
        """
        params = {
            "owner": owner,
            "repo": repo,
            "state": state,
            "per_page": per_page,
            "page": page,
            "sort": "updated",
            "direction": "desc",
        }

        if since:
            params["since"] = since.isoformat()

        response = await self._with_rate_limit(
            self._github.rest.issues.async_list_for_repo(**params)
        )

        if not response:
            return []

        # PR은 제외 (pull_request 필드가 있으면 PR)
        issues = []
        for issue in response.parsed_data:
            issue_dict = issue.model_dump()
            if not issue_dict.get("pull_request"):
                issues.append(issue_dict)

        return issues

    async def list_all_issues(
        self,
        owner: str,
        repo: str,
        state: str = "all",
        since: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """
        Repository의 모든 Issue 조회 (페이지네이션 자동 처리)

        Args:
            owner: Repository owner
            repo: Repository name
            state: Issue 상태 (open, closed, all)
            since: 이 시간 이후 업데이트된 Issue만 조회

        Returns:
            모든 Issue 정보 리스트
        """
        all_issues = []
        page = 1
        per_page = settings.GITHUB_SYNC_BATCH_SIZE

        while True:
            issues = await self.list_issues(
                owner=owner,
                repo=repo,
                state=state,
                since=since,
                per_page=per_page,
                page=page,
            )

            if not issues:
                break

            all_issues.extend(issues)

            if len(issues) < per_page:
                break

            page += 1

        return all_issues

    async def get_issue(self, owner: str, repo: str, issue_number: int) -> dict[str, Any]:
        """
        Issue 상세 정보 조회

        Args:
            owner: Repository owner
            repo: Repository name
            issue_number: Issue 번호

        Returns:
            Issue 상세 정보
        """
        response = await self._with_rate_limit(
            self._github.rest.issues.async_get(
                owner=owner,
                repo=repo,
                issue_number=issue_number
            )
        )
        return response.parsed_data.model_dump() if response else {}

    async def get_issue_comments(
        self,
        owner: str,
        repo: str,
        issue_number: int,
        per_page: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Issue의 코멘트 목록 조회

        Args:
            owner: Repository owner
            repo: Repository name
            issue_number: Issue 번호
            per_page: 페이지당 결과 수

        Returns:
            코멘트 리스트
        """
        comments = []
        page = 1

        while True:
            response = await self._with_rate_limit(
                self._github.rest.issues.async_list_comments(
                    owner=owner,
                    repo=repo,
                    issue_number=issue_number,
                    per_page=per_page,
                    page=page,
                )
            )

            if not response or not response.parsed_data:
                break

            for comment in response.parsed_data:
                comments.append(comment.model_dump())

            if len(response.parsed_data) < per_page:
                break

            # 최대 코멘트 수 제한
            if len(comments) >= settings.GITHUB_SYNC_COMMENTS_LIMIT:
                break

            page += 1

        return comments[:settings.GITHUB_SYNC_COMMENTS_LIMIT]

    # ============================================================
    # Pull Request APIs
    # ============================================================

    async def list_pull_requests(
        self,
        owner: str,
        repo: str,
        state: str = "all",
        per_page: int = 100,
        page: int = 1,
    ) -> list[dict[str, Any]]:
        """
        Repository의 Pull Request 목록 조회

        Args:
            owner: Repository owner
            repo: Repository name
            state: PR 상태 (open, closed, all)
            per_page: 페이지당 결과 수
            page: 페이지 번호

        Returns:
            Pull Request 정보 리스트
        """
        response = await self._with_rate_limit(
            self._github.rest.pulls.async_list(
                owner=owner,
                repo=repo,
                state=state,
                sort="updated",
                direction="desc",
                per_page=per_page,
                page=page,
            )
        )

        if not response:
            return []

        return [pr.model_dump() for pr in response.parsed_data]

    async def list_all_pull_requests(
        self,
        owner: str,
        repo: str,
        state: str = "all",
        since: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """
        Repository의 모든 Pull Request 조회 (페이지네이션 자동 처리)

        Args:
            owner: Repository owner
            repo: Repository name
            state: PR 상태 (open, closed, all)
            since: 이 시간 이후 업데이트된 PR만 필터링 (클라이언트 측)

        Returns:
            모든 Pull Request 정보 리스트
        """
        all_prs = []
        page = 1
        per_page = settings.GITHUB_SYNC_BATCH_SIZE

        while True:
            prs = await self.list_pull_requests(
                owner=owner,
                repo=repo,
                state=state,
                per_page=per_page,
                page=page,
            )

            if not prs:
                break

            # since 필터링 (클라이언트 측)
            for pr in prs:
                if since:
                    updated_at = pr.get("updated_at")
                    if updated_at:
                        # datetime 객체 또는 문자열 처리
                        if isinstance(updated_at, datetime):
                            pr_updated = updated_at
                        else:
                            pr_updated = datetime.fromisoformat(str(updated_at).replace("Z", "+00:00"))
                        if pr_updated < since:
                            # 이전 PR은 스킵 (정렬되어 있으므로 여기서 종료)
                            return all_prs

                all_prs.append(pr)

            if len(prs) < per_page:
                break

            page += 1

        return all_prs

    async def get_pull_request(
        self,
        owner: str,
        repo: str,
        pull_number: int,
    ) -> dict[str, Any]:
        """
        Pull Request 상세 정보 조회

        Args:
            owner: Repository owner
            repo: Repository name
            pull_number: PR 번호

        Returns:
            Pull Request 상세 정보
        """
        response = await self._with_rate_limit(
            self._github.rest.pulls.async_get(
                owner=owner,
                repo=repo,
                pull_number=pull_number,
            )
        )
        return response.parsed_data.model_dump() if response else {}

    async def get_pr_reviews(
        self,
        owner: str,
        repo: str,
        pull_number: int,
        per_page: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Pull Request의 리뷰 목록 조회

        Args:
            owner: Repository owner
            repo: Repository name
            pull_number: PR 번호
            per_page: 페이지당 결과 수

        Returns:
            리뷰 리스트
        """
        reviews = []
        page = 1

        while True:
            response = await self._with_rate_limit(
                self._github.rest.pulls.async_list_reviews(
                    owner=owner,
                    repo=repo,
                    pull_number=pull_number,
                    per_page=per_page,
                    page=page,
                )
            )

            if not response or not response.parsed_data:
                break

            for review in response.parsed_data:
                reviews.append(review.model_dump())

            if len(response.parsed_data) < per_page:
                break

            # 최대 리뷰 수 제한
            if len(reviews) >= settings.GITHUB_SYNC_REVIEWS_LIMIT:
                break

            page += 1

        return reviews[:settings.GITHUB_SYNC_REVIEWS_LIMIT]

    async def get_pr_files(
        self,
        owner: str,
        repo: str,
        pull_number: int,
        per_page: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Pull Request의 변경된 파일 목록 조회

        Args:
            owner: Repository owner
            repo: Repository name
            pull_number: PR 번호
            per_page: 페이지당 결과 수

        Returns:
            변경된 파일 리스트
        """
        files = []
        page = 1

        while True:
            response = await self._with_rate_limit(
                self._github.rest.pulls.async_list_files(
                    owner=owner,
                    repo=repo,
                    pull_number=pull_number,
                    per_page=per_page,
                    page=page,
                )
            )

            if not response or not response.parsed_data:
                break

            for file in response.parsed_data:
                files.append(file.model_dump())

            if len(response.parsed_data) < per_page:
                break

            page += 1

        return files

    async def get_pr_comments(
        self,
        owner: str,
        repo: str,
        pull_number: int,
        per_page: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Pull Request의 리뷰 코멘트 목록 조회 (파일별 코멘트)

        Args:
            owner: Repository owner
            repo: Repository name
            pull_number: PR 번호
            per_page: 페이지당 결과 수

        Returns:
            리뷰 코멘트 리스트
        """
        comments = []
        page = 1

        while True:
            response = await self._with_rate_limit(
                self._github.rest.pulls.async_list_review_comments(
                    owner=owner,
                    repo=repo,
                    pull_number=pull_number,
                    per_page=per_page,
                    page=page,
                )
            )

            if not response or not response.parsed_data:
                break

            for comment in response.parsed_data:
                comments.append(comment.model_dump())

            if len(response.parsed_data) < per_page:
                break

            # 최대 코멘트 수 제한
            if len(comments) >= settings.GITHUB_SYNC_COMMENTS_LIMIT:
                break

            page += 1

        return comments[:settings.GITHUB_SYNC_COMMENTS_LIMIT]

    # ============================================================
    # Commit APIs
    # ============================================================

    async def list_commits(
        self,
        owner: str,
        repo: str,
        sha: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        per_page: int = 100,
        page: int = 1,
    ) -> list[dict[str, Any]]:
        """
        Repository의 Commit 목록 조회

        Args:
            owner: Repository owner
            repo: Repository name
            sha: Branch 또는 시작 Commit SHA
            since: 이 시간 이후의 Commit만 조회
            until: 이 시간 이전의 Commit만 조회
            per_page: 페이지당 결과 수
            page: 페이지 번호

        Returns:
            Commit 정보 리스트
        """
        params = {
            "owner": owner,
            "repo": repo,
            "per_page": per_page,
            "page": page,
        }

        if sha:
            params["sha"] = sha
        if since:
            params["since"] = since.isoformat()
        if until:
            params["until"] = until.isoformat()

        response = await self._with_rate_limit(
            self._github.rest.repos.async_list_commits(**params)
        )

        if not response:
            return []

        return [commit.model_dump() for commit in response.parsed_data]

    async def list_all_commits(
        self,
        owner: str,
        repo: str,
        sha: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """
        Repository의 모든 Commit 조회 (페이지네이션 자동 처리)

        Args:
            owner: Repository owner
            repo: Repository name
            sha: Branch 또는 시작 Commit SHA
            since: 이 시간 이후의 Commit만 조회
            until: 이 시간 이전의 Commit만 조회

        Returns:
            모든 Commit 정보 리스트
        """
        all_commits = []
        page = 1
        per_page = settings.GITHUB_SYNC_BATCH_SIZE

        while True:
            commits = await self.list_commits(
                owner=owner,
                repo=repo,
                sha=sha,
                since=since,
                until=until,
                per_page=per_page,
                page=page,
            )

            if not commits:
                break

            all_commits.extend(commits)

            if len(commits) < per_page:
                break

            page += 1

        return all_commits

    async def get_commit(
        self,
        owner: str,
        repo: str,
        ref: str,
    ) -> dict[str, Any]:
        """
        Commit 상세 정보 조회

        Args:
            owner: Repository owner
            repo: Repository name
            ref: Commit SHA

        Returns:
            Commit 상세 정보 (파일 변경 포함)
        """
        response = await self._with_rate_limit(
            self._github.rest.repos.async_get_commit(
                owner=owner,
                repo=repo,
                ref=ref,
            )
        )
        return response.parsed_data.model_dump() if response else {}

    # ============================================================
    # PR-Commit 연결 API
    # ============================================================

    async def list_pr_commits(
        self,
        owner: str,
        repo: str,
        pull_number: int,
        per_page: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Pull Request에 포함된 Commit 목록 조회

        Args:
            owner: Repository owner
            repo: Repository name
            pull_number: PR 번호
            per_page: 페이지당 결과 수

        Returns:
            PR에 포함된 Commit 리스트
        """
        commits = []
        page = 1

        while True:
            response = await self._with_rate_limit(
                self._github.rest.pulls.async_list_commits(
                    owner=owner,
                    repo=repo,
                    pull_number=pull_number,
                    per_page=per_page,
                    page=page,
                )
            )

            if not response or not response.parsed_data:
                break

            for commit in response.parsed_data:
                commits.append(commit.model_dump())

            if len(response.parsed_data) < per_page:
                break

            page += 1

        return commits

    # ============================================================
    # User APIs
    # ============================================================

    async def get_user(self, username: str) -> dict[str, Any]:
        """
        사용자 정보 조회

        Args:
            username: GitHub username

        Returns:
            사용자 정보
        """
        response = await self._with_rate_limit(
            self._github.rest.users.async_get_by_username(username=username)
        )
        return response.parsed_data.model_dump() if response else {}

    async def list_org_members(
        self,
        org: str,
        per_page: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Organization 멤버 목록 조회

        Args:
            org: Organization name
            per_page: 페이지당 결과 수

        Returns:
            멤버 리스트
        """
        members = []
        page = 1

        while True:
            response = await self._with_rate_limit(
                self._github.rest.orgs.async_list_members(
                    org=org,
                    per_page=per_page,
                    page=page,
                )
            )

            if not response or not response.parsed_data:
                break

            for member in response.parsed_data:
                members.append(member.model_dump())

            if len(response.parsed_data) < per_page:
                break

            page += 1

        return members

    # ============================================================
    # GraphQL APIs
    # ============================================================

    async def list_pull_requests_graphql(
        self,
        owner: str,
        repo: str,
        states: list[str] | None = None,
        since: datetime | None = None,
        reviews_limit: int = 10,
        commits_limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        GraphQL로 PR 목록과 상세 정보를 한 번에 조회

        REST API 1회 + N회 GraphQL 대신, 페이지네이션된 GraphQL 쿼리로 모든 PR을 조회.

        Args:
            owner: Repository owner
            repo: Repository name
            states: PR 상태 필터 (OPEN, CLOSED, MERGED). None이면 모두
            since: 이 시간 이후 업데이트된 PR만 필터링 (클라이언트 측)
            reviews_limit: PR당 조회할 리뷰 수
            commits_limit: PR당 조회할 커밋 수

        Returns:
            PR 목록 (각 PR은 기본 정보 + reviews, comments, commits 포함)
        """
        query = """
        query($owner: String!, $repo: String!, $first: Int!, $after: String, $states: [PullRequestState!]) {
          repository(owner: $owner, name: $repo) {
            pullRequests(first: $first, after: $after, states: $states, orderBy: {field: UPDATED_AT, direction: DESC}) {
              pageInfo {
                hasNextPage
                endCursor
              }
              nodes {
                databaseId
                number
                title
                body
                state
                isDraft
                merged
                additions
                deletions
                changedFiles
                url
                createdAt
                updatedAt
                mergedAt
                closedAt
                baseRefName
                headRefName
                author { login avatarUrl }
                assignees(first: 10) { nodes { login avatarUrl } }
                labels(first: 20) { nodes { name color description } }
                milestone { number title state dueOn }
                reviewRequests(first: 10) {
                  nodes {
                    requestedReviewer {
                      ... on User { login avatarUrl }
                    }
                  }
                }
                reviews(first: 10) {
                  nodes {
                    databaseId
                    author { login avatarUrl }
                    state
                    body
                    submittedAt
                  }
                }
                reviewThreads(first: 50) {
                  nodes {
                    comments(first: 10) {
                      nodes {
                        databaseId
                        author { login avatarUrl }
                        body
                        path
                        line
                        originalLine
                        diffHunk
                        createdAt
                        updatedAt
                      }
                    }
                  }
                }
                commits(first: 100) {
                  nodes {
                    commit {
                      oid
                      message
                      author {
                        name
                        email
                        user { login }
                      }
                      committedDate
                    }
                  }
                }
              }
            }
          }
        }
        """

        # 상태 매핑 (all -> 모든 상태)
        gql_states = None
        if states and states != ["all"]:
            state_map = {"open": "OPEN", "closed": "CLOSED", "merged": "MERGED"}
            gql_states = [state_map.get(s.lower(), s.upper()) for s in states]

        all_prs = []
        after_cursor = None
        per_page = 25  # GraphQL 복잡도 제한으로 인해 한 번에 25개씩

        while True:
            variables = {
                "owner": owner,
                "repo": repo,
                "first": per_page,
                "after": after_cursor,
                "states": gql_states,
            }

            response = await self._with_rate_limit(
                self._github.async_graphql(query, variables)
            )

            if not response:
                break

            pr_connection = response.get("repository", {}).get("pullRequests", {})
            if not pr_connection:
                break

            nodes = pr_connection.get("nodes") or []

            for node in nodes:
                if not node:
                    continue

                # since 필터링 (클라이언트 측)
                if since:
                    updated_at_str = node.get("updatedAt")
                    if updated_at_str:
                        updated_at = datetime.fromisoformat(updated_at_str.replace("Z", "+00:00"))
                        if updated_at < since:
                            # 정렬이 updatedAt DESC이므로 여기서 종료
                            return all_prs

                # PR 데이터 변환 (REST API 형식과 호환)
                pr_data = self._convert_graphql_pr_to_rest_format(node)
                all_prs.append(pr_data)

            # 페이지네이션
            page_info = pr_connection.get("pageInfo", {})
            if not page_info.get("hasNextPage"):
                break

            after_cursor = page_info.get("endCursor")

        return all_prs

    def _convert_graphql_pr_to_rest_format(self, node: dict[str, Any]) -> dict[str, Any]:
        """
        GraphQL PR 노드를 REST API 응답 형식으로 변환

        transformer.parse_pull_request()와 호환되는 형식으로 변환합니다.
        """
        # 작성자
        author = node.get("author") or {}
        user = {
            "id": 0,
            "login": author.get("login", ""),
            "avatar_url": author.get("avatarUrl"),
        } if author.get("login") else None

        # Assignees
        assignees = []
        for a in (node.get("assignees", {}).get("nodes") or []):
            if a:
                assignees.append({
                    "id": 0,
                    "login": a.get("login", ""),
                    "avatar_url": a.get("avatarUrl"),
                })

        # Labels
        labels = []
        for l in (node.get("labels", {}).get("nodes") or []):
            if l:
                labels.append({
                    "id": 0,
                    "name": l.get("name", ""),
                    "color": l.get("color"),
                    "description": l.get("description"),
                })

        # Milestone
        milestone = None
        if node.get("milestone"):
            m = node["milestone"]
            milestone = {
                "id": 0,
                "number": m.get("number"),
                "title": m.get("title"),
                "state": m.get("state", "").lower(),
                "due_on": m.get("dueOn"),
            }

        # Requested reviewers
        requested_reviewers = []
        for rr in (node.get("reviewRequests", {}).get("nodes") or []):
            if rr and rr.get("requestedReviewer"):
                reviewer = rr["requestedReviewer"]
                requested_reviewers.append({
                    "id": 0,
                    "login": reviewer.get("login", ""),
                    "avatar_url": reviewer.get("avatarUrl"),
                })

        # Reviews
        reviews = []
        for review in (node.get("reviews", {}).get("nodes") or []):
            if review:
                review_author = review.get("author") or {}
                reviews.append({
                    "id": review.get("databaseId"),
                    "user": {
                        "id": 0,
                        "login": review_author.get("login", ""),
                        "avatar_url": review_author.get("avatarUrl"),
                    } if review_author.get("login") else None,
                    "state": review.get("state"),
                    "body": review.get("body"),
                    "submitted_at": review.get("submittedAt"),
                })

        # Review comments (from reviewThreads)
        comments = []
        for thread in (node.get("reviewThreads", {}).get("nodes") or []):
            if thread:
                for comment in (thread.get("comments", {}).get("nodes") or []):
                    if comment:
                        comment_author = comment.get("author") or {}
                        comments.append({
                            "id": comment.get("databaseId"),
                            "user": {
                                "id": 0,
                                "login": comment_author.get("login", ""),
                                "avatar_url": comment_author.get("avatarUrl"),
                            } if comment_author.get("login") else None,
                            "body": comment.get("body"),
                            "path": comment.get("path"),
                            "line": comment.get("line"),
                            "original_line": comment.get("originalLine"),
                            "diff_hunk": comment.get("diffHunk"),
                            "created_at": comment.get("createdAt"),
                            "updated_at": comment.get("updatedAt"),
                        })

        # Commits
        commits = []
        for commit_node in (node.get("commits", {}).get("nodes") or []):
            if commit_node and commit_node.get("commit"):
                commit = commit_node["commit"]
                commit_author = commit.get("author") or {}
                commits.append({
                    "sha": commit.get("oid"),
                    "commit": {
                        "message": commit.get("message"),
                        "author": {
                            "name": commit_author.get("name"),
                            "email": commit_author.get("email"),
                            "date": commit.get("committedDate"),
                        },
                        "committer": {
                            "date": commit.get("committedDate"),
                        },
                    },
                    "author": {
                        "login": commit_author.get("user", {}).get("login"),
                    } if commit_author.get("user") else None,
                })

        # State 매핑
        state = node.get("state", "").lower()
        if state == "merged":
            state = "closed"  # REST API는 merged PR도 state: closed

        return {
            # 기본 정보 (REST API 형식)
            "id": node.get("databaseId"),
            "number": node.get("number"),
            "title": node.get("title"),
            "body": node.get("body"),
            "state": state,
            "draft": node.get("isDraft", False),
            "merged": node.get("merged", False),
            "html_url": node.get("url"),
            "url": node.get("url"),
            "created_at": node.get("createdAt"),
            "updated_at": node.get("updatedAt"),
            "merged_at": node.get("mergedAt"),
            "closed_at": node.get("closedAt"),
            "additions": node.get("additions", 0),
            "deletions": node.get("deletions", 0),
            "changed_files": node.get("changedFiles", 0),
            "commits": len(commits),  # commits_count로 사용됨

            # 브랜치 정보
            "base": {"ref": node.get("baseRefName")},
            "head": {"ref": node.get("headRefName")},

            # 관계
            "user": user,
            "assignees": assignees,
            "labels": labels,
            "milestone": milestone,
            "requested_reviewers": requested_reviewers,

            # 상세 정보 (별도 API 호출 없이 포함)
            "_reviews": reviews,
            "_comments": comments,
            "_commits": commits,
        }
