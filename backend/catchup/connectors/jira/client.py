"""
Jira REST API Client

Jira Cloud REST API를 호출하는 비동기 클라이언트.

## Jira API 구조

Jira Cloud는 두 가지 API를 제공:

1. **REST API v3** (base_url)
   - 기본 Jira 기능: Issue, Project, Field, Comment 등
   - 모든 Jira 제품에서 사용 가능
   - URL 형식: https://api.atlassian.com/ex/jira/{cloud_id}/rest/api/3

2. **Agile API v1** (agile_url)
   - Jira Software 전용 기능: Sprint, Board, Epic 등
   - Scrum/Kanban 보드 관련 기능
   - URL 형식: https://api.atlassian.com/ex/jira/{cloud_id}/rest/agile/1.0
   - 주의: Jira Software 라이선스가 없으면 사용 불가

## Rate Limiting

- Jira Cloud는 테넌트 기반 throttling 사용
- X-RateLimit-Remaining 헤더로 잔여 횟수 확인 가능
- 429 응답 시 Retry-After 헤더 값만큼 대기 후 재시도

## 페이지네이션

- 대부분의 목록 API는 startAt, maxResults 파라미터 사용
- Search API는 최대 5,000개까지만 조회 가능 (그 이상은 시간 기반 분할 필요)
"""

import asyncio
import logging
from typing import Any

import httpx

from catchup.configs.config import settings
from catchup.connectors.atlassian.token_manager import AtlassianTokenProvider

logger = logging.getLogger(__name__)


# ============================================================
# 예외 클래스 정의
# ============================================================

from catchup.connectors.base import (
    AuthenticationError,
    ConnectorApiError,
    RateLimitError,
)


class JiraApiError(ConnectorApiError):
    """
    Jira API 에러 기본 클래스

    모든 Jira API 관련 예외의 부모 클래스.
    status_code를 통해 HTTP 상태 코드 확인 가능.
    """

    service = "jira"


class JiraRateLimitError(RateLimitError, JiraApiError):
    """
    Rate limit 초과 에러 (HTTP 429)

    retry_after 속성으로 재시도까지 대기해야 할 시간(초) 확인 가능.

    처리 방법:
        try:
            await client.search_issues(...)
        except JiraRateLimitError as e:
            await asyncio.sleep(e.retry_after)
            # 재시도
    """

    service = "jira"


class JiraAuthError(AuthenticationError, JiraApiError):
    """
    인증 에러 (HTTP 401)

    Access token이 만료되었거나 유효하지 않을 때 발생.

    처리 방법:
        try:
            await client.search_issues(...)
        except JiraAuthError:
            # AtlassianTokenManager.resolve_access_token()으로 토큰 갱신 후 재시도
    """

    service = "jira"


# ============================================================
# Jira API 클라이언트
# ============================================================

class JiraApiClient:
    """
    Jira REST API 비동기 클라이언트

    Jira Cloud API를 호출하기 위한 저수준 클라이언트.
    Rate limiting, 페이지네이션, 에러 핸들링을 자동으로 처리.

    - 초기화
    # cloud_id: Jira Cloud 인스턴스 ID (JiraOAuthToken 테이블에서 조회)
    # access_token: OAuth access token (AtlassianTokenManager.resolve_access_token()로 획득)
    client = JiraApiClient(
        cloud_id="abc123-def456",
        access_token="eyJhbGciOiJSUzI1NiIs..."
    )

    - Rate Limiting

    - 동시 요청 수: JIRA_SYNC_MAX_CONCURRENT_REQUESTS (기본값: 5)
    - 요청 간 딜레이: JIRA_API_RATE_LIMIT_DELAY (기본값: 0.1초)
    - 429 응답 시 자동으로 Retry-After만큼 대기 후 재시도

    Attributes:
        cloud_id: Jira Cloud 인스턴스 ID
        access_token: OAuth access token
        base_url: REST API v3 기본 URL (Issue, Project, Field 등)
        agile_url: Agile API v1 URL (Sprint, Board - Jira Software 전용)
    """

    def __init__(self, cloud_id: str, token_provider: AtlassianTokenProvider):
        self.cloud_id = cloud_id
        self.token_provider = token_provider
        self.base_url = f"{settings.ATLASSIAN_API_URL}/ex/jira/{cloud_id}/rest/api/3"

        # Agile API v1: Jira Software 전용 기능
        # - Board: Scrum/Kanban 보드 관리
        # - Sprint: 스프린트 CRUD 및 이슈 관리
        # - Epic: Epic 관련 Agile 기능 (REST API로도 Epic 조회 가능하지만 Agile API가 더 편리)
        # 주의: Jira Software 라이선스가 없으면 403 Forbidden 발생
        self.agile_url = f"{settings.ATLASSIAN_API_URL}/ex/jira/{cloud_id}/rest/agile/1.0"

        # Rate limiting을 위한 세마포어
        # 동시에 실행할 수 있는 최대 요청 수 제한
        self._semaphore = asyncio.Semaphore(settings.JIRA_SYNC_MAX_CONCURRENT_REQUESTS)

        # 요청 간 딜레이 (초)
        # Rate limit에 걸리지 않도록 요청 사이에 약간의 간격을 둠
        self._rate_limit_delay = settings.JIRA_API_RATE_LIMIT_DELAY

        # Agile API 사용 가능 여부 캐시
        # None: 아직 확인 안 함, True/False: 확인 완료
        self._agile_available: bool | None = None

    async def is_agile_available(self) -> bool:
        """
        Agile API (Jira Software) 사용 가능 여부 확인

        Jira Software 라이선스가 있어야 Agile API 사용 가능.
        첫 호출 시 실제 API를 호출하여 확인하고, 결과를 캐싱.

        Returns:
            True: Agile API 사용 가능 (Sprint, Board 조회 가능)
            False: Agile API 사용 불가 (403 Forbidden 또는 401 Unauthorized)
        """
        if self._agile_available is None:
            try:
                # 보드 목록을 1개만 조회하여 확인
                await self._request(
                    "GET",
                    f"{self.agile_url}/board",
                    params={"maxResults": 1}
                )
                self._agile_available = True
                logger.info(f"Agile API available for cloud_id={self.cloud_id}")
            except JiraApiError as e:
                if e.status_code in (401, 403):
                    # 401 Unauthorized = Agile API 스코프 없음
                    # 403 Forbidden = Jira Software 라이선스 없음
                    self._agile_available = False
                    reason = (
                        "missing OAuth scopes" if e.status_code == 401
                        else "Jira Software license required"
                    )
                    logger.info(
                        f"Agile API not available for cloud_id={self.cloud_id} "
                        f"({reason})"
                    )
                else:
                    # 다른 에러는 다시 발생시킴
                    raise

        return self._agile_available

    def _get_headers(self, access_token: str) -> dict[str, str]:
        """
        API 요청에 사용할 HTTP 헤더 생성

        Returns:
            Authorization, Content-Type, Accept 헤더가 포함된 딕셔너리
        """
        return {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def _request(
        self,
        method: str,
        url: str,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        max_retries: int = 3,
    ) -> dict[str, Any]:
        """
        Args:
            method: HTTP 메서드 (GET, POST, PUT, DELETE)
            url: 전체 요청 URL
            params: 쿼리 파라미터 딕셔너리
            json_body: JSON 요청 본문
            max_retries: 최대 재시도 횟수 (기본: 3)
                         429, 5xx, 타임아웃 시 재시도

        Returns:
            JSON 파싱된 응답 데이터 (dict 또는 list)

        Raises:
            JiraRateLimitError: 429 응답 후 재시도 횟수 초과
            JiraAuthError: 401 응답 (토큰 만료/무효)
            JiraApiError: 기타 4xx/5xx 에러 또는 타임아웃

        내부 동작:
            1. 세마포어 획득 (동시 요청 수 제한)
            2. HTTP 요청 실행
            3. 429 응답 시 Retry-After 대기 후 재시도
            4. 401 응답 시 JiraAuthError 발생 (재시도 없음)
            5. 기타 4xx/5xx 시 JiraApiError 발생
            6. 타임아웃 시 exponential backoff로 재시도
            7. 성공 시 rate limit 방지를 위한 딜레이 후 응답 반환
        """
        async with self._semaphore:
            auth_retried = False
            for attempt in range(max_retries):
                try:
                    force_refresh = False
                    while True:
                        access_token = await self.token_provider.get_access_token(
                            self.cloud_id,
                            force_refresh=force_refresh,
                        )
                        async with httpx.AsyncClient(
                            headers=self._get_headers(access_token), timeout=30.0
                        ) as client:
                            response = await client.request(
                                method, url, params=params, json=json_body
                            )

                            # Rate limit 초과 (429 Too Many Requests)
                            # Retry-After 헤더 값만큼 대기 후 재시도
                            if response.status_code == 429:
                                retry_after = int(
                                    response.headers.get("Retry-After", 60)
                                )
                                if attempt < max_retries - 1:
                                    logger.warning(
                                        f"Rate limited. Waiting {retry_after}s before retry..."
                                    )
                                    await asyncio.sleep(retry_after)
                                    break
                                raise JiraRateLimitError(retry_after)

                            # 인증 실패 (401 Unauthorized)
                            # 1회에 한해 강제 refresh 후 동일 요청 재시도
                            if response.status_code == 401:
                                if auth_retried:
                                    raise JiraAuthError()
                                auth_retried = True
                                force_refresh = True
                                continue

                            # 기타 클라이언트/서버 에러
                            if response.status_code >= 400:
                                raise JiraApiError(
                                    f"API error: {response.text}",
                                    response.status_code,
                                )

                            # Rate limit 방지를 위한 요청 간 딜레이
                            await asyncio.sleep(self._rate_limit_delay)
                            return response.json()

                except httpx.TimeoutException:
                    # 타임아웃 시 exponential backoff (1초, 2초, 4초...)
                    if attempt < max_retries - 1:
                        wait_time = 2 ** attempt
                        logger.warning(
                            f"Request timeout. Retrying in {wait_time}s... "
                            f"({attempt + 1}/{max_retries})"
                        )
                        await asyncio.sleep(wait_time)
                        continue
                    raise JiraApiError("Request timeout after retries")

        # 이 코드에 도달하면 안 됨 (위에서 항상 return 또는 raise)
        raise JiraApiError("Max retries exceeded")

    # ============================================================
    # Dynamic Webhook APIs (REST API v3)
    # ============================================================

    async def get_dynamic_webhooks(
        self,
        start_at: int = 0,
        max_results: int = 100,
    ) -> Any:
        """
        등록된 Dynamic Webhook 목록 조회
        """
        params = {
            "startAt": start_at,
            "maxResults": max_results,
        }
        return await self._request("GET", f"{self.base_url}/webhook", params=params)

    async def register_dynamic_webhook(
        self,
        callback_url: str,
        jql_filter: str,
        events: list[str],
    ) -> Any:
        """
        Dynamic Webhook 등록
        """
        body = {
            "url": callback_url,
            "webhooks": [
                {
                    "jqlFilter": jql_filter,
                    "events": events,
                }
            ],
        }
        return await self._request(
            "POST",
            f"{self.base_url}/webhook",
            json_body=body,
        )

    async def refresh_dynamic_webhook_life(
        self,
        webhook_ids: list[int],
    ) -> Any:
        """
        Dynamic Webhook 만료 기간 연장 (30일)
        """
        body = {"webhookIds": webhook_ids}
        return await self._request(
            "PUT",
            f"{self.base_url}/webhook/refresh",
            json_body=body,
        )

    async def list_all_dynamic_webhooks(
        self,
        max_results: int = 100,
    ) -> list[dict]:
        """
        Dynamic webhook 전체 목록을 페이지네이션 따라 모두 반환.
        """
        all_values: list[dict] = []
        start_at = 0

        while True:
            page = await self.get_dynamic_webhooks(start_at=start_at, max_results=max_results)
            values = page.get("values", [])
            all_values.extend(values)

            if page.get("isLast", True) or not values:
                break

            next_offset = page.get("maxResults", max_results) or 0
            if next_offset <= 0:
                break
            start_at += next_offset

        return all_values

    # ============================================================
    # Issue APIs (REST API v3)
    #
    # 이슈 검색, 조회, 코멘트, 변경 이력 관련 API.
    # 모든 Jira 제품에서 사용 가능.
    # ============================================================

    async def search_issues(
        self,
        jql: str,
        fields: list[str] | None = None,
        expand: str = "",
        max_results: int | None = None,
        next_page_token: str | None = None,
    ) -> dict[str, Any]:
        """
        JQL(Jira Query Language)로 이슈 검색 (새 API: /search/jql)

        Args:
            jql: JQL 쿼리 문자열
                 예시:
                 - "project = CATCH" (프로젝트의 모든 이슈)
                 - "project = CATCH AND status = 'In Progress'" (진행 중인 이슈)
                 - "project = CATCH AND updated >= -7d" (최근 7일 내 수정된 이슈)
                 - "project = CATCH AND issuetype = Epic" (Epic만)
                 - "project = CATCH AND sprint = 42" (특정 스프린트의 이슈)

            fields: 반환할 필드 배열
                    - None: 모든 필드 반환 (fields 파라미터 생략)
                    - ["summary", "status", "assignee"]: 특정 필드만

            expand: 추가 정보 확장 (쉼표로 구분된 문자열)
                    - "changelog": 필드 변경 이력 포함
                    - "names": 커스텀 필드 이름 매핑 포함
                    - "renderedFields": HTML 렌더링된 필드 포함
                    - 복수 지정: "changelog,names"

            max_results: 페이지 크기 (최대 100, 기본값: config의 JIRA_SYNC_BATCH_SIZE)

            next_page_token: 다음 페이지 토큰 (2024년부터 startAt 대체)
                             첫 요청에는 None, 이후 응답의 nextPageToken 사용

        Returns:
            {
                "issues": [...],           # 이슈 배열
                "nextPageToken": "...",    # 다음 페이지 토큰 (마지막이면 없음)
                "isLast": true/false,      # 마지막 페이지 여부
                "maxResults": 100          # 페이지 크기
            }

        Note:
            - startAt은 deprecated되어 nextPageToken으로 대체됨
            - Random page access 불가능 (순차적 페이지 접근만 가능)
            - 한 번에 최대 5,000개까지만 조회 가능
            - 그 이상은 시간 기반 분할 필요 (예: updated >= "2024-01-01" AND updated < "2024-02-01")
        """
        body: dict[str, Any] = {
            "jql": jql,
            "maxResults": max_results or settings.JIRA_SYNC_BATCH_SIZE,
            # 새 API는 기본으로 ID만 반환하므로, *all로 모든 필드 요청
            "fields": fields if fields is not None else ["*all"],
        }

        if expand:
            body["expand"] = expand

        if next_page_token:
            body["nextPageToken"] = next_page_token

        logger.debug(f"Search issues request: URL={self.base_url}/search/jql, body={body}")
        return await self._request(
            "POST",
            f"{self.base_url}/search/jql",
            json_body=body,
        )

    async def get_issue(
        self,
        issue_key: str,
        fields: str = "*all",
        expand: str = "",
    ) -> dict[str, Any]:
        """
        단일 이슈 상세 조회

        Args:
            issue_key: 이슈 키 (예: "CATCH-145") 또는 이슈 ID
            fields: 반환할 필드 (search_issues와 동일)
            expand: 추가 정보 확장 (search_issues와 동일)

        Returns:
            이슈 객체
            {
                "id": "10145",
                "key": "CATCH-145",
                "fields": {
                    "summary": "이슈 제목",
                    "status": {...},
                    "assignee": {...},
                    ...
                }
            }
        """
        params = {"fields": fields}
        if expand:
            params["expand"] = expand

        return await self._request(
            "GET", f"{self.base_url}/issue/{issue_key}", params=params
        )

    async def get_issue_comments(
        self,
        issue_key: str,
        max_results: int | None = None,
        order_by: str = "-created",
    ) -> list[dict[str, Any]]:
        """
        이슈 코멘트 목록 조회

        Args:
            issue_key: 이슈 키
            max_results: 최대 개수 (기본: config의 JIRA_SYNC_COMMENTS_LIMIT, 보통 5)
            order_by: 정렬 순서
                      - "-created": 최신순 (기본값)
                      - "+created" 또는 "created": 오래된 순

        Returns:
            코멘트 배열
            [
                {
                    "id": "10001",
                    "body": {...},  # Atlassian Document Format (ADF)
                    "author": {"displayName": "member", ...},
                    "created": "2024-02-01T09:00:00.000+0000",
                    "updated": "2024-02-01T09:00:00.000+0000"
                },
                ...
            ]

        Note:
            - body 필드는 ADF(Atlassian Document Format) 형식
            - 일반 텍스트 변환 필요 시 별도 파싱 로직 필요
        """
        params = {
            "maxResults": max_results or settings.JIRA_SYNC_COMMENTS_LIMIT,
            "orderBy": order_by,
        }

        result = await self._request(
            "GET", f"{self.base_url}/issue/{issue_key}/comment", params=params
        )
        return result.get("comments", [])

    # ============================================================
    # Field APIs (REST API v3)
    #
    # 커스텀 필드 매핑에 사용.
    # Epic Link, Sprint, Story Points 등 커스텀 필드의 ID는 인스턴스마다 다름.
    # ============================================================

    async def get_fields(self) -> list[dict[str, Any]]:
        """
        모든 필드 정의 조회

        커스텀 필드 ID 매핑에 사용.
        Jira 인스턴스마다 커스텀 필드 ID가 다르므로 동기화 시작 시 한 번 호출하여 캐싱.

        Returns:
            필드 배열
            [
                {
                    "id": "summary",           # 시스템 필드
                    "name": "Summary",
                    "custom": false
                },
                {
                    "id": "customfield_10014", # 커스텀 필드
                    "name": "Epic Link",
                    "custom": true
                },
                ...
            ]

        주요 커스텀 필드 예시:
            - Epic Link: customfield_10014 (인스턴스마다 다름)
            - Epic Name: customfield_10011
            - Sprint: customfield_10020
            - Story Points: customfield_10028
        """
        return await self._request("GET", f"{self.base_url}/field")

    # ============================================================
    # Project APIs (REST API v3)
    #
    # 프로젝트 메타데이터, 컴포넌트, 버전 조회.
    # ============================================================

    async def get_all_projects(
        self,
        expand: str = "description,lead",
        max_results: int = 50,
    ) -> list[dict[str, Any]]:
        """
        접근 가능한 모든 프로젝트 조회

        Args:
            expand: 추가 정보 확장 (description, lead, issueTypes, url)
            max_results: 페이지 크기 (최대 50)

        Returns:
            프로젝트 목록
            [
                {"id": "10000", "key": "CATCH", "name": "CatchUp", ...},
                {"id": "10001", "key": "PROJ", "name": "Project", ...},
            ]
        """
        all_projects: list[dict[str, Any]] = []
        start_at = 0

        while True:
            params = {
                "expand": expand,
                "startAt": start_at,
                "maxResults": max_results,
            }
            response = await self._request(
                "GET", f"{self.base_url}/project/search", params=params
            )

            projects = response.get("values", [])
            if not projects:
                break

            all_projects.extend(projects)

            # 다음 페이지 확인
            if response.get("isLast", True):
                break

            start_at += len(projects)

        logger.info(f"Retrieved {len(all_projects)} projects")
        return all_projects

    async def get_project(
        self,
        project_key: str,
        expand: str = "description,lead",
    ) -> dict[str, Any]:
        """
        프로젝트 상세 조회

        Args:
            project_key: 프로젝트 키 (예: "CATCH")
            expand: 추가 정보 확장
                    - "description": 프로젝트 설명
                    - "lead": 프로젝트 리드 정보
                    - "issueTypes": 사용 가능한 이슈 타입
                    - "url": 프로젝트 URL

        Returns:
            프로젝트 객체
            {
                "id": "10000",
                "key": "CATCH",
                "name": "CatchUp",
                "projectTypeKey": "software",
                "description": "...",
                "lead": {"displayName": "tech-lead", ...},
                ...
            }
        """
        params = {"expand": expand}
        return await self._request(
            "GET", f"{self.base_url}/project/{project_key}", params=params
        )

    async def get_project_components(
        self, project_key: str
    ) -> list[dict[str, Any]]:
        """
        프로젝트 컴포넌트 목록 조회

        컴포넌트는 프로젝트 내 기능/모듈 분류 단위.
        예: Backend, Frontend, Mobile, Infrastructure

        Args:
            project_key: 프로젝트 키

        Returns:
            컴포넌트 배열
            [
                {
                    "id": "10001",
                    "name": "Backend",
                    "description": "Backend API services",
                    "lead": {"displayName": "member", ...},
                    "assigneeType": "COMPONENT_LEAD"
                },
                ...
            ]
        """
        return await self._request(
            "GET", f"{self.base_url}/project/{project_key}/components"
        )

    async def get_project_versions(
        self, project_key: str
    ) -> list[dict[str, Any]]:
        """
        프로젝트 버전 목록 조회

        버전은 릴리즈 관리 단위.
        이슈의 fixVersion, affectsVersion 필드에서 참조.

        Args:
            project_key: 프로젝트 키

        Returns:
            버전 배열
            [
                {
                    "id": "10001",
                    "name": "v2.1.0",
                    "released": false,
                    "releaseDate": "2024-03-01"
                },
                ...
            ]
        """
        return await self._request(
            "GET", f"{self.base_url}/project/{project_key}/versions"
        )

    # ============================================================
    # Agile APIs (Agile API v1) - Jira Software 전용
    #
    # Sprint, Board 관련 기능.
    # Jira Software 라이선스가 없으면 403 Forbidden 발생.
    # ============================================================

    async def get_boards(self) -> list[dict[str, Any]]:
        """
        모든 보드 목록 조회

        Scrum/Kanban 보드 목록 조회.
        스프린트 조회를 위해 먼저 보드 ID를 알아야 함.

        Returns:
            보드 배열
            [
                {
                    "id": 1,
                    "name": "CatchUp Scrum Board",
                    "type": "scrum",  # scrum, kanban
                    "location": {"projectKey": "CATCH", ...}
                },
                ...
            ]

        Note:
            Jira Software 라이선스 필요. 없으면 403 에러.
        """
        result = await self._request("GET", f"{self.agile_url}/board")
        return result.get("values", [])

    async def get_board_sprints(
        self,
        board_id: int,
        state: str | None = None,
        start_at: int = 0,
        max_results: int = 50,
    ) -> dict[str, Any]:
        """
        보드의 스프린트 목록 조회

        Args:
            board_id: 보드 ID (get_boards()로 조회)
            state: 스프린트 상태 필터
                   - "future": 예정된 스프린트
                   - "active": 현재 진행 중인 스프린트
                   - "closed": 완료된 스프린트
                   - None: 모든 스프린트
            start_at: 페이지네이션 오프셋
            max_results: 페이지 크기

        Returns:
            {
                "values": [
                    {
                        "id": 42,
                        "name": "Sprint 42",
                        "state": "active",
                        "startDate": "2024-01-22T00:00:00.000Z",
                        "endDate": "2024-02-05T00:00:00.000Z",
                        "goal": "Complete authentication revamp"
                    },
                    ...
                ],
                "startAt": 0,
                "maxResults": 50,
                "isLast": true
            }

        Note:
            Jira Software 라이선스 필요. 없으면 403 에러.
        """
        params = {
            "startAt": start_at,
            "maxResults": max_results,
        }
        if state:
            params["state"] = state

        return await self._request(
            "GET", f"{self.agile_url}/board/{board_id}/sprint", params=params
        )

    async def get_sprint(self, sprint_id: int) -> dict[str, Any]:
        """
        스프린트 상세 조회

        Args:
            sprint_id: 스프린트 ID

        Returns:
            스프린트 객체
            {
                "id": 42,
                "name": "Sprint 42",
                "state": "active",
                "startDate": "2024-01-22T00:00:00.000Z",
                "endDate": "2024-02-05T00:00:00.000Z",
                "completeDate": null,
                "goal": "Complete authentication revamp"
            }

        Note:
            Jira Software 라이선스 필요.
        """
        return await self._request("GET", f"{self.agile_url}/sprint/{sprint_id}")

    async def get_sprint_issues(
        self,
        sprint_id: int,
        fields: str = "*all",
        start_at: int = 0,
        max_results: int = 100,
    ) -> dict[str, Any]:
        """
        스프린트에 포함된 이슈 목록 조회

        search_issues()에서 JQL로 조회하는 것과 동일하지만,
        이 API는 스프린트 ID로 직접 조회하므로 더 정확.

        Args:
            sprint_id: 스프린트 ID
            fields: 반환할 필드 (search_issues와 동일)
            start_at: 페이지네이션 오프셋
            max_results: 페이지 크

        Returns:
            {
                "issues": [...],
                "startAt": 0,
                "maxResults": 100,
                "total": 23
            }

        Note:
            Jira Software 라이선스 필요.
        """
        params = {
            "fields": fields,
            "startAt": start_at,
            "maxResults": max_results,
        }

        return await self._request(
            "GET", f"{self.agile_url}/sprint/{sprint_id}/issue", params=params
        )

    # ============================================================
    # User APIs (REST API v3)
    #
    # 사용자 검색 및 조회.
    # ============================================================

    async def get_all_users(
        self,
        max_results: int = 50,
    ) -> list[dict[str, Any]]:
        """
        접근 가능한 모든 사용자 조회

        Jira Cloud의 모든 사용자를 조회 (Bot, 비활성 사용자 포함).
        페이지네이션을 자동으로 처리하여 전체 사용자 목록 반환.

        Args:
            max_results: 페이지 크기 (최대 50)

        Returns:
            사용자 목록
            [
                {
                    "accountId": "5b10ac8d82e05b22cc7d4ef5",
                    "accountType": "atlassian",
                    "displayName": "홍길동",
                    "emailAddress": "hong@example.com",  # 권한에 따라 없을 수 있음
                    "avatarUrls": {"48x48": "https://..."},
                    "active": true,
                    "self": "https://..."
                },
                ...
            ]

        Note:
            - read:jira-user 스코프 필요
            - emailAddress는 사이트 설정에 따라 반환되지 않을 수 있음
        """
        all_users: list[dict[str, Any]] = []
        start_at = 0

        while True:
            params = {
                "startAt": start_at,
                "maxResults": max_results,
            }
            response = await self._request(
                "GET", f"{self.base_url}/users/search", params=params
            )

            # users/search는 배열을 직접 반환
            if not response:
                break

            all_users.extend(response)

            # 반환된 수가 max_results보다 적으면 마지막 페이지
            if len(response) < max_results:
                break

            start_at += len(response)

        logger.info(f"Retrieved {len(all_users)} users")
        return all_users
