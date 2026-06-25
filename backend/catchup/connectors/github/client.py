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
from collections.abc import Awaitable
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from datetime import timezone
from typing import Any
from typing import AsyncIterator
from typing import Literal

from githubkit import GitHub
from githubkit.exception import RequestFailed
from githubkit.exception import RequestTimeout

from catchup.configs.config import settings
from catchup.connectors.base.retry import parse_reset_timestamp_header
from catchup.connectors.base.retry import parse_retry_after_header
from catchup.connectors.github.queries import ISSUE_BY_NUMBER_QUERY
from catchup.connectors.github.queries import ISSUE_NUMBERS_QUERY
from catchup.connectors.github.queries import ISSUES_QUERY
from catchup.connectors.github.queries import ORG_MEMBERS_QUERY
from catchup.connectors.github.queries import PULL_REQUEST_BY_NUMBER_QUERY
from catchup.connectors.github.queries import PULL_REQUEST_NUMBERS_QUERY
from catchup.connectors.github.queries import PULL_REQUESTS_QUERY
from catchup.connectors.github.queries import build_issues_by_numbers_query
from catchup.connectors.github.queries import build_pull_requests_by_numbers_query

logger = logging.getLogger(__name__)


# ============================================================
# 예외 클래스 정의
# ============================================================

from catchup.connectors.base import AuthenticationError
from catchup.connectors.base import ConnectorApiError
from catchup.connectors.base import NotFoundError
from catchup.connectors.base import RateLimitError


class GitHubApiError(ConnectorApiError):
    """
    GitHub API 에러 기본 클래스

    모든 GitHub API 관련 예외의 부모 클래스.
    status_code를 통해 HTTP 상태 코드 확인 가능.
    """

    service = "github"

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        retry_after: int | float | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        super().__init__(
            message,
            status_code=status_code,
            retry_after=retry_after,
            metadata=metadata,
        )


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

    def __init__(
        self,
        message: str | None = None,
        retry_after: int = 60,
        remaining: int = 0,
        metadata: dict[str, Any] | None = None,
    ):
        super().__init__(
            message=message,
            retry_after=retry_after,
            remaining=remaining,
            metadata=metadata,
        )


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


@dataclass(frozen=True, slots=True)
class GitHubGraphQLPage:
    nodes: tuple[dict[str, Any], ...]
    next_cursor: str | None
    is_last: bool
    stopped_by_since: bool = False


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

    def __init__(
        self,
        access_token: str,
        refresh_access_token: Callable[[], Awaitable[str]] | None = None,
    ):
        self.access_token = access_token
        self._github = GitHub(access_token)
        self._refresh_access_token = refresh_access_token

        # Rate limiting을 위한 세마포어
        self._semaphore = asyncio.Semaphore(int(settings.GITHUB_SYNC_MAX_CONCURRENT_REQUESTS))

        # 요청 간 딜레이 (초)
        self._rate_limit_delay = float(settings.GITHUB_API_RATE_LIMIT_DELAY)
        self._max_rate_limit_retries = 3
        self._max_client_retry_after_seconds = 30
        self._max_auth_retries = 1
        self._auth_refresh_lock = asyncio.Lock()

    def _set_access_token(self, access_token: str) -> None:
        self.access_token = access_token
        self._github = GitHub(access_token)

    async def _refresh_auth_token(
        self,
        failed_token: str,
    ) -> Literal["refreshed", "reused"] | None:
        if self._refresh_access_token is None:
            return None

        async with self._auth_refresh_lock:
            if self.access_token != failed_token:
                return "reused"

            refreshed_token = await self._refresh_access_token()
            if not refreshed_token:
                return None

            self._set_access_token(refreshed_token)
            return "refreshed"

    @staticmethod
    def _extract_header_subset(headers: Any) -> dict[str, str]:
        if not headers:
            return {}

        keys = (
            "retry-after",
            "x-ratelimit-limit",
            "x-ratelimit-remaining",
            "x-ratelimit-reset",
            "x-ratelimit-resource",
        )
        return {
            key: str(headers.get(key))
            for key in keys
            if headers.get(key) is not None
        }

    @staticmethod
    def _extract_error_message(payload: Any) -> str | None:
        if isinstance(payload, dict):
            message = payload.get("message")
            if isinstance(message, str) and message.strip():
                return message.strip()

        if isinstance(payload, str) and payload.strip():
            return payload.strip()

        return None

    @staticmethod
    def _extract_graphql_error_messages(errors: Any) -> list[str]:
        if not isinstance(errors, list):
            return []

        messages: list[str] = []
        for error in errors:
            if not isinstance(error, dict):
                continue

            message = error.get("message")
            if isinstance(message, str) and message.strip():
                messages.append(message.strip())

        return messages

    @staticmethod
    def _is_secondary_rate_limit_message(message: str | None) -> bool:
        if not message:
            return False

        normalized = message.lower()
        return any(
            phrase in normalized
            for phrase in (
                "secondary rate limit",
                "secondary rate limits",
                "abuse detection",
                "temporarily blocked from content creation",
            )
        )

    def _build_rate_limit_metadata(
        self,
        *,
        source: str,
        reason: str,
        status_code: int | None,
        headers: Any,
        retry_after: int,
        reset_timestamp: int | None = None,
        body_message: str | None = None,
        graphql_errors: list[str] | None = None,
    ) -> dict[str, Any]:
        metadata: dict[str, Any] = {
            "source": source,
            "reason": reason,
            "status_code": status_code,
            "retry_after": retry_after,
            "headers": self._extract_header_subset(headers),
        }

        if reset_timestamp is not None:
            metadata["reset_timestamp"] = reset_timestamp
        if body_message:
            metadata["body_message"] = body_message
        if graphql_errors:
            metadata["graphql_errors"] = graphql_errors

        return metadata

    def _build_rate_limit_error(
        self,
        *,
        source: str,
        reason: str,
        status_code: int | None,
        headers: Any,
        retry_after: int,
        remaining: int = 0,
        reset_timestamp: int | None = None,
        body_message: str | None = None,
        graphql_errors: list[str] | None = None,
    ) -> GitHubRateLimitError:
        metadata = self._build_rate_limit_metadata(
            source=source,
            reason=reason,
            status_code=status_code,
            headers=headers,
            retry_after=retry_after,
            reset_timestamp=reset_timestamp,
            body_message=body_message,
            graphql_errors=graphql_errors,
        )

        return GitHubRateLimitError(
            retry_after=retry_after,
            remaining=remaining,
            metadata=metadata,
        )

    def _raise_graphql_rate_limit_error(
        self,
        errors: list[str],
    ) -> None:
        joined = " | ".join(errors)
        raise self._build_rate_limit_error(
            source="graphql",
            reason="graphql_errors",
            status_code=200,
            headers={},
            retry_after=60,
            body_message=joined,
            graphql_errors=errors,
        )

    def _handle_error(self, e: RequestFailed) -> None:
        """
        GitHub API 에러를 적절한 예외로 변환
        """
        status_code = e.response.status_code if e.response else None
        headers = e.response.headers if e.response else {}
        body_message = self._extract_error_message(str(e))

        if e.response is not None:
            try:
                payload = e.response.json()
            except ValueError:
                payload = None
            extracted_message = self._extract_error_message(payload)
            if extracted_message:
                body_message = extracted_message

        if status_code == 401:
            raise GitHubAuthError("Invalid or expired access token")

        if status_code == 404:
            raise GitHubNotFoundError("Resource not found")

        if status_code == 403:
            remaining = int(headers.get("x-ratelimit-remaining", 1))
            retry_after_header = headers.get("retry-after")

            if retry_after_header is not None:
                retry_after = parse_retry_after_header(
                    retry_after_header,
                    default=60,
                )
                reason = (
                    "secondary_rate_limit"
                    if self._is_secondary_rate_limit_message(body_message)
                    else "retry_after_header"
                )
                raise self._build_rate_limit_error(
                    source="rest",
                    reason=reason,
                    status_code=status_code,
                    headers=headers,
                    retry_after=retry_after,
                    remaining=remaining,
                    body_message=body_message,
                )

            if remaining == 0:
                reset_timestamp = int(float(headers.get("x-ratelimit-reset", 0) or 0))
                now = int(datetime.now(timezone.utc).timestamp())
                retry_after = parse_reset_timestamp_header(
                    headers.get("x-ratelimit-reset"),
                    now_ts=now,
                    default=60,
                )
                raise self._build_rate_limit_error(
                    source="rest",
                    reason="primary_rate_limit_reset",
                    status_code=status_code,
                    headers=headers,
                    retry_after=retry_after,
                    remaining=0,
                    reset_timestamp=reset_timestamp,
                    body_message=body_message,
                )

            if self._is_secondary_rate_limit_message(body_message):
                raise self._build_rate_limit_error(
                    source="rest",
                    reason="secondary_rate_limit",
                    status_code=status_code,
                    headers=headers,
                    retry_after=60,
                    remaining=remaining,
                    body_message=body_message,
                )

        if status_code == 429:
            retry_after = parse_retry_after_header(
                headers.get("retry-after"),
                default=60,
            )
            raise self._build_rate_limit_error(
                source="rest",
                reason="http_429",
                status_code=status_code,
                headers=headers,
                retry_after=retry_after,
                body_message=body_message,
            )

        raise GitHubApiError(str(e), status_code, metadata={"body_message": body_message})

    async def _with_rate_limit(
        self,
        request_factory: Callable[[], Awaitable[Any]],
    ) -> Any:
        """
        Rate limiting을 적용하여 코루틴 실행
        """
        async with self._semaphore:
            retry_count = 0
            auth_retry_count = 0

            while True:
                try:
                    request_token = self.access_token
                    result = await request_factory()
                    await asyncio.sleep(self._rate_limit_delay)
                    return result
                except RequestFailed as e:
                    status_code = e.response.status_code if e.response else None
                    if status_code == 401 and auth_retry_count < self._max_auth_retries:
                        refresh_result = await self._refresh_auth_token(request_token)
                        if refresh_result is not None:
                            auth_retry_count += 1
                            logger.info(
                                "[GITHUB][API] Installation token %s after 401 response",
                                "refreshed"
                                if refresh_result == "refreshed"
                                else "reused from concurrent refresh",
                            )
                            continue

                    try:
                        self._handle_error(e)
                    except GitHubRateLimitError as rate_limit_error:
                        if retry_count >= self._max_rate_limit_retries:
                            raise

                        if (
                            rate_limit_error.retry_after is not None
                            and rate_limit_error.retry_after > self._max_client_retry_after_seconds
                        ):
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
                error_messages = self._extract_graphql_error_messages(errors)
                if any(
                    self._is_secondary_rate_limit_message(message)
                    or "rate limit" in message.lower()
                    for message in error_messages
                ):
                    self._raise_graphql_rate_limit_error(error_messages)

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

    async def _fetch_connection_nodes_graphql_page(
        self,
        *,
        query: str,
        owner: str,
        repo: str,
        connection_name: str,
        after_cursor: str | None = None,
        since: datetime | None = None,
        per_page: int = 100,
    ) -> GitHubGraphQLPage:
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
            return GitHubGraphQLPage(nodes=(), next_cursor=None, is_last=True)

        connection = response.get("repository", {}).get(connection_name, {})
        if not connection:
            return GitHubGraphQLPage(nodes=(), next_cursor=None, is_last=True)

        nodes = connection.get("nodes") or []
        batch: list[dict[str, Any]] = []

        for node in nodes:
            if not node:
                continue

            updated_at = self._parse_graphql_datetime(node.get("updatedAt"))
            if since and updated_at and updated_at < since:
                return GitHubGraphQLPage(
                    nodes=tuple(batch),
                    next_cursor=None,
                    is_last=True,
                    stopped_by_since=True,
                )

            batch.append(node)

        page_info = connection.get("pageInfo", {})
        end_cursor = page_info.get("endCursor")
        next_cursor = end_cursor if page_info.get("hasNextPage") else None
        if not isinstance(next_cursor, str) or not next_cursor:
            next_cursor = None

        return GitHubGraphQLPage(
            nodes=tuple(batch),
            next_cursor=next_cursor,
            is_last=next_cursor is None,
        )

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
            page = await self._fetch_connection_nodes_graphql_page(
                query=query,
                owner=owner,
                repo=repo,
                connection_name=connection_name,
                after_cursor=after_cursor,
                since=since,
                per_page=per_page,
            )
            if page.nodes:
                yield list(page.nodes)

            if page.is_last:
                break

            after_cursor = page.next_cursor

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

    async def fetch_pull_requests_graphql_page(
        self,
        owner: str,
        repo: str,
        *,
        after_cursor: str | None = None,
        since: datetime | None = None,
    ) -> GitHubGraphQLPage:
        return await self._fetch_connection_nodes_graphql_page(
            query=PULL_REQUESTS_QUERY,
            owner=owner,
            repo=repo,
            connection_name="pullRequests",
            after_cursor=after_cursor,
            since=since,
            per_page=50,
        )

    async def fetch_issues_graphql_page(
        self,
        owner: str,
        repo: str,
        *,
        after_cursor: str | None = None,
        since: datetime | None = None,
    ) -> GitHubGraphQLPage:
        return await self._fetch_connection_nodes_graphql_page(
            query=ISSUES_QUERY,
            owner=owner,
            repo=repo,
            connection_name="issues",
            after_cursor=after_cursor,
            since=since,
            per_page=50,
        )

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

    async def get_issues_graphql(
        self,
        owner: str,
        repo: str,
        numbers: list[int],
    ) -> dict[str, dict[str, Any]]:
        unique_numbers = list(dict.fromkeys(numbers))
        if not unique_numbers:
            return {}

        response = await self._graphql(
            build_issues_by_numbers_query(unique_numbers),
            {
                "owner": owner,
                "repo": repo,
            },
        )
        repository = response.get("repository", {}) or {}
        return {
            str(number): node
            for number in unique_numbers
            if (node := repository.get(f"issue_{number}")) is not None
        }

    async def get_pull_requests_graphql(
        self,
        owner: str,
        repo: str,
        numbers: list[int],
    ) -> dict[str, dict[str, Any]]:
        unique_numbers = list(dict.fromkeys(numbers))
        if not unique_numbers:
            return {}

        response = await self._graphql(
            build_pull_requests_by_numbers_query(unique_numbers),
            {
                "owner": owner,
                "repo": repo,
            },
        )
        repository = response.get("repository", {}) or {}
        return {
            str(number): node
            for number in unique_numbers
            if (node := repository.get(f"pr_{number}")) is not None
        }
