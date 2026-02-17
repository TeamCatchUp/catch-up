"""
Confluence REST API v2 비동기 클라이언트
"""
import asyncio
import logging
from typing import Any
from urllib.parse import urlparse, parse_qs

import httpx

from catchup.configs.config import settings
from catchup.connectors.base import (
    AuthenticationError,
    ConnectorApiError,
    RateLimitError,
)

logger = logging.getLogger(__name__)

class ConfluenceApiError(ConnectorApiError):
    service = "confluence"

class ConfluenceRateLimitError(RateLimitError, ConfluenceApiError):
    service = "confluence"

class ConfluenceAuthError(AuthenticationError, ConfluenceApiError):
    service = "confluence"

class ConfluenceApiClient:
    def __init__(self, cloud_id: str, access_token:str):
        self.cloud_id = cloud_id
        self.access_token = access_token
        # v2 API (spaces, role-assignments 등)
        self.base_url = f"{settings.ATLASSIAN_API_URL}/ex/confluence/{cloud_id}/wiki/api/v2"
        # v1 API (user search 등)
        self.base_url_v1 = f"{settings.ATLASSIAN_API_URL}/ex/confluence/{cloud_id}/wiki/rest/api"

        self._semaphore = asyncio.Semaphore(settings.CONFLUENCE_SYNC_MAX_CONCURRENT_REQUEST)
        self._rate_limit_delay = settings.CONFLUENCE_SYNC_RATE_LIMIT_DELAY
    
    def _get_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
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
        async with self._semaphore:
            for attempt in range(max_retries):
                try:
                    async with httpx.AsyncClient(
                        headers=self._get_headers(), timeout=30.0
                    ) as client:
                        response = await client.request(
                            method, url, params=params, json=json_body
                        )

                        if response.status_code == 429:
                            retry_after = int(response.headers.get("Retry-After", 5))
                            logger.warning(
                                f"[CONFLUENCE][API] Rate limited, retry after {retry_after}s"
                            )
                            if attempt < max_retries - 1:
                                await asyncio.sleep(retry_after)
                                continue
                            raise ConfluenceRateLimitError(
                                "Rate limit exceeded",
                                retry_after=retry_after,
                            )

                        if response.status_code == 401:
                            body = (response.text or "").strip()
                            raise ConfluenceAuthError(
                                f"Authentication failed for Confluence API. body={body[:300]}"
                            )

                        if response.status_code == 403:
                            body = (response.text or "").strip()
                            raise ConfluenceApiError(
                                "Confluence API access forbidden. "
                                f"Confluence scope or admin permission may be missing. body={body[:300]}",
                                status_code=403,
                            )

                        if response.status_code >= 400:
                            error_body = (response.text or "").strip()
                            raise ConfluenceApiError(
                                f"API error [{response.status_code}]: {error_body[:300]}",
                                status_code=response.status_code,
                            )

                        await asyncio.sleep(self._rate_limit_delay)
                        return response.json()

                except httpx.TimeoutException:
                    if attempt < max_retries - 1:
                        wait = 2 ** attempt
                        logger.warning(
                            f"[CONFLUENCE][API] Timeout, retry in {wait}s "
                            f"(attempt {attempt + 1}/{max_retries})"
                        )
                        await asyncio.sleep(wait)
                        continue
                    raise ConfluenceApiError(
                        "Request timeout after retries", status_code=408
                    )

        raise ConfluenceApiError("Max retries exceeded", status_code=500)
    
    def _extract_cursor_from_link(self, link: str) -> str | None:
        parsed = urlparse(link)
        query_params = parse_qs(parsed.query)
        return query_params.get("cursor", [None])[0]

    async def _paginate_cursor(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        result_key: str = "results",
        limit: int = 250,
    ) -> list[dict[str, Any]]:
        """커서 기반 페이지네이션으로 모든 결과 수집"""
        all_results: list[dict[str, Any]] = []
        current_params = dict(params or {})
        current_params["limit"] = limit

        while True:
            response = await self._request("GET", url, params=current_params)

            results = response.get(result_key, [])
            if not results:
                break

            all_results.extend(results)

            next_link = response.get("_links", {}).get("next")
            if not next_link:
                break

            cursor = self._extract_cursor_from_link(next_link)
            if not cursor:
                break

            current_params["cursor"] = cursor

        logger.info(f"[CONFLUENCE][API] Paginated {len(all_results)} results from {url}")
        return all_results
    
    async def get_users(
        self,
        cql: str = "type=user",
        limit: int = 250,
    ) -> list[dict[str, Any]]:
        """
        Confluence 사용자 전체 조회 (v1 search API)
        - default cql: type=user (모든 사용자)
        - start/limit 기반 페이지네이션 자동 처리
        """
        all_results: list[dict[str, Any]] = []
        start = 0
        while True:
            params = {"cql": cql, "limit": limit, "start": start}
            response = await self._request(
                "GET",
                url=f"{self.base_url_v1}/search/user",
                params=params,
            )
            results = response.get("results", [])
            if results:
                all_results.extend(results)

            next_link = response.get("_links", {}).get("next")
            if not next_link:
                break

            parsed = urlparse(next_link)
            query_params = parse_qs(parsed.query)
            next_start = query_params.get("start", [None])[0]
            if next_start is None:
                break
            try:
                start = int(next_start)
            except ValueError:
                break

        logger.info(f"[CONFLUENCE][API] Paginated {len(all_results)} users via v1 search")
        return all_results

    async def get_space_role_assignments(
        self,
        space_id: str,
        principal_type: str = "user",
        limit: int = 250,
    ) -> list[dict[str, Any]]:
        """특정 Space의 Role Assignments 조회 (principal_type=user)."""
        params = {"principalType": principal_type, "limit": limit}
        return await self._paginate_cursor(
            url=f"{self.base_url}/spaces/{space_id}/role-assignments",
            params=params,
            limit=limit,
        )
    
    async def get_space_permissions(
        self,
        space_id: str,
        limit: int = 250,
    ) -> list[dict[str, Any]]:
        """
        Space 권한 목록 조회 (v2 permissions)
        - RBAC 미적용 사이트에서도 사용 가능
        """
        params = {"limit": limit}
        return await self._paginate_cursor(
            url=f"{self.base_url}/spaces/{space_id}/permissions",
            params=params,
            limit=limit,
        )
    
    async def get_spaces(
        self,
        space_type: str | None = None,
        status: str | None = "current",
        limit: int = 250,
    ) -> list[dict[str, Any]]:
        """
        Space 목록 조회
        - space_type가 None이면 필터를 제거하여 knowledge_base 등 모든 타입을 가져온다.
        """

        params: dict[str, Any] = {"limit": limit}
        if space_type:
            params["type"] = space_type
        if status:
            params["status"] = status

        return await self._paginate_cursor(
            url=f"{self.base_url}/spaces",
            params=params,
            limit=limit,
        )
