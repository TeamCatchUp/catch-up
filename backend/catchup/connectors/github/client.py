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
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any, AsyncIterator

from githubkit import GitHub
from githubkit.exception import RequestFailed, RequestTimeout
from catchup.connectors.github.queries import (
    ISSUE_BY_NUMBER_QUERY,
    ISSUE_NUMBERS_QUERY,
    ISSUES_QUERY,
    ORG_MEMBERS_QUERY,
    PULL_REQUEST_BY_NUMBER_QUERY,
    PULL_REQUEST_NUMBERS_QUERY,
    PULL_REQUESTS_QUERY,
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
        self._max_rate_limit_retries = 3

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

    async def _with_rate_limit(
        self,
        request_factory: Callable[[], Awaitable[Any]],
    ) -> Any:
        """
        Rate limiting을 적용하여 코루틴 실행
        """
        async with self._semaphore:
            retry_count = 0

            while True:
                try:
                    result = await request_factory()
                    await asyncio.sleep(self._rate_limit_delay)
                    return result
                except RequestFailed as e:
                    try:
                        self._handle_error(e)
                    except GitHubRateLimitError as rate_limit_error:
                        if retry_count >= self._max_rate_limit_retries:
                            raise

                        retry_count += 1
                        logger.warning(
                            "[GITHUB][API] Rate limited. Waiting %ss before retry "
                            "(attempt %s/%s)",
                            rate_limit_error.retry_after,
                            retry_count,
                            self._max_rate_limit_retries,
                        )
                        await asyncio.sleep(rate_limit_error.retry_after)
                        continue
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
            lambda: self._github.rest.repos.async_get(owner=owner, repo=repo)
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
                lambda: self._github.rest.apps.async_list_repos_accessible_to_installation(
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
            lambda: self._github.rest.repos.async_list_commits(**params)
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
            lambda: self._github.rest.repos.async_get_commit(
                owner=owner,
                repo=repo,
                ref=ref,
            )
        )
        return response.parsed_data.model_dump() if response else {}

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
            lambda: self._github.rest.users.async_get_by_username(username=username)
        )
        return response.parsed_data.model_dump() if response else {}

    async def list_org_members(
        self,
        org: str,
        per_page: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Organization 멤버 목록 조회 (REST API)

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
                lambda: self._github.rest.orgs.async_list_members(
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

    async def list_org_members_graphql(
        self,
        org: str,
    ) -> list[dict[str, Any]]:
        """
        GraphQL로 Organization 멤버 목록 조회 (상세 정보 포함)
        """
        all_members = []
        after_cursor = None
        per_page = 100

        while True:
            variables = {
                "org": org,
                "first": per_page,
                "after": after_cursor,
            }

            response = await self._graphql(ORG_MEMBERS_QUERY, variables)

            if not response:
                break

            org_data = response.get("organization")
            if not org_data:
                break

            members_data = org_data.get("membersWithRole", {})
            edges = members_data.get("edges") or []

            for edge in edges:
                if not edge:
                    continue

                node = edge.get("node") or {}
                role = edge.get("role")

                all_members.append({
                    "database_id": node.get("databaseId"),
                    "login": node.get("login"),
                    "name": node.get("name"),
                    "email": node.get("email"),
                    "avatar_url": node.get("avatarUrl"),
                    "org_role": role,
                })

            page_info = members_data.get("pageInfo", {})
            if not page_info.get("hasNextPage"):
                break

            after_cursor = page_info.get("endCursor")

        return all_members
    
    async def _graphql(
        self,
        query: str,
        variables: dict[str, Any],
    ) -> dict[str, Any]:
        response = await self._with_rate_limit(
            lambda: self._github.async_graphql(query, variables)
        )
        if not response:
            return {}

        if isinstance(response, dict):
            errors = response.get("errors")
            if errors:
                logger.error(
                    "[GITHUB][GRAPHQL] Query returned errors: variables=%s, errors=%s",
                    variables,
                    errors,
                )
            data = response.get("data")
            if isinstance(data, dict):
                return data

        return response
    
    @staticmethod
    def _parse_graphql_datetime(value: str | None) -> datetime | None:
        if not value:
            return None
        return datetime.fromisoformat(value.replace("Z", "+00:00"))

    async def _iterate_connection_nodes_graphql(
        self,
        *,
        query: str,
        owner: str,
        repo: str,
        connection_name: str,
        since: datetime | None = None,
        per_page: int = 100,
    ) -> AsyncIterator[list[dict[str, Any]]]:
        after_cursor = None

        while True:
            response = await self._graphql(
                query,
                {
                    "owner": owner,
                    "repo": repo,
                    "first": per_page,
                    "after": after_cursor,
                },
            )

            if not response:
                break

            connection = response.get("repository", {}).get(connection_name, {})
            if not connection:
                break

            nodes = connection.get("nodes") or []
            batch: list[dict[str, Any]] = []

            for node in nodes:
                if not node:
                    continue

                updated_at = self._parse_graphql_datetime(node.get("updatedAt"))
                if since and updated_at and updated_at < since:
                    if batch:
                        yield batch
                    return

                batch.append(node)

            if batch:
                yield batch

            page_info = connection.get("pageInfo", {})
            if not page_info.get("hasNextPage"):
                break

            after_cursor = page_info.get("endCursor")

    async def _list_entity_numbers_graphql(
        self,
        *,
        query: str,
        owner: str,
        repo: str,
        connection_name: str,
        since: datetime | None = None,
        per_page: int = 100,
    ) -> list[str]:
        numbers: list[str] = []

        async for batch in self._iterate_connection_nodes_graphql(
            query=query,
            owner=owner,
            repo=repo,
            connection_name=connection_name,
            since=since,
            per_page=per_page,
        ):
            for node in batch:
                number = node.get("number")
                if number is None:
                    continue
                numbers.append(str(number))

        return numbers

    # ============================================================
    # GraphQL APIs
    # ============================================================

    async def list_pull_requests_graphql(
        self,
        owner: str,
        repo: str,
        since: datetime | None = None,
    ) -> AsyncIterator[list[dict[str, Any]]]:
        """
        GraphQL로 PR 목록과 상세 정보를 페이지 단위로 스트리밍 조회

        - per_page 50 통일 (GraphQL 복잡도 제한 고려 시 안전선)
        - updatedAt이 since 이전인 항목을 만나면 즉시 종료해 불필요 호출 차단
        - 각 페이지의 노드 리스트를 yield 하여 호출 위치에서 배치 처리
        """
        async for batch in self._iterate_connection_nodes_graphql(
            query=PULL_REQUESTS_QUERY,
            owner=owner,
            repo=repo,
            connection_name="pullRequests",
            since=since,
            per_page=50,
        ):
            yield batch

    async def list_issues_graphql(
        self,
        owner: str,
        repo: str,
        since: datetime | None = None,
    ) -> AsyncIterator[list[dict[str, Any]]]:
        """
        GraphQL로 Issue 목록과 코멘트를 페이지 단위로 스트리밍 조회

        - per_page 50 고정
        - updatedAt이 since 이전이면 즉시 종료
        - 각 페이지 노드 리스트를 yield
        """
        async for batch in self._iterate_connection_nodes_graphql(
            query=ISSUES_QUERY,
            owner=owner,
            repo=repo,
            connection_name="issues",
            since=since,
            per_page=50,
        ):
            yield batch

    async def list_issue_numbers_graphql(
        self,
        owner: str,
        repo: str,
        since: datetime | None = None,
    ) -> list[str]:
        return await self._list_entity_numbers_graphql(
            query=ISSUE_NUMBERS_QUERY,
            owner=owner,
            repo=repo,
            connection_name="issues",
            since=since,
            per_page=100,
        )

    async def list_pull_request_numbers_graphql(
        self,
        owner: str,
        repo: str,
        since: datetime | None = None,
    ) -> list[str]:
        return await self._list_entity_numbers_graphql(
            query=PULL_REQUEST_NUMBERS_QUERY,
            owner=owner,
            repo=repo,
            connection_name="pullRequests",
            since=since,
            per_page=100,
        )

    async def get_issue_graphql(
        self,
        owner: str,
        repo: str,
        number: int,
    ) -> dict[str, Any] | None:
        response = await self._graphql(
            ISSUE_BY_NUMBER_QUERY,
            {
                "owner": owner,
                "repo": repo,
                "number": number,
            },
        )
        return response.get("repository", {}).get("issue")

    async def get_pull_request_graphql(
        self,
        owner: str,
        repo: str,
        number: int,
    ) -> dict[str, Any] | None:
        response = await self._graphql(
            PULL_REQUEST_BY_NUMBER_QUERY,
            {
                "owner": owner,
                "repo": repo,
                "number": number,
            },
        )
        return response.get("repository", {}).get("pullRequest")
