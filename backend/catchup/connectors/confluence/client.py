"""
Confluence REST API v2 비동기 클라이언트
"""
import asyncio
import logging
from typing import Any
from urllib.parse import urlparse, parse_qs

import httpx

from catchup.configs.config import settings
from catchup.connectors.atlassian.token_manager import AtlassianTokenProvider
from catchup.connectors.base import (
    AuthenticationError,
    ConnectorApiError,
    RateLimitError,
)
from catchup.connectors.base.retry import parse_retry_after_header

logger = logging.getLogger(__name__)

class ConfluenceApiError(ConnectorApiError):
    service = "confluence"

class ConfluenceRateLimitError(RateLimitError, ConfluenceApiError):
    service = "confluence"

class ConfluenceAuthError(AuthenticationError, ConfluenceApiError):
    service = "confluence"

class ConfluenceApiClient:
    def __init__(self, cloud_id: str, token_provider: AtlassianTokenProvider):
        self.cloud_id = cloud_id
        self.token_provider = token_provider
        # v2 API (spaces, pages 등)
        self.base_url = f"{settings.ATLASSIAN_API_URL}/ex/confluence/{cloud_id}/wiki/api/v2"
        # v1 API (user search 등)
        self.base_url_v1 = f"{settings.ATLASSIAN_API_URL}/ex/confluence/{cloud_id}/wiki/rest/api"

        self._semaphore = asyncio.Semaphore(settings.CONFLUENCE_SYNC_MAX_CONCURRENT_REQUEST)
        self._rate_limit_delay = settings.CONFLUENCE_SYNC_RATE_LIMIT_DELAY
        self._attachment_max_retries = 3
    
    def _get_headers(self, access_token: str) -> dict[str, str]:
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

                            if response.status_code == 429:
                                retry_after, retry_after_source = self._resolve_retry_after(
                                    response,
                                    default=5,
                                )
                                logger.warning(
                                    f"[CONFLUENCE][API] Rate limited, retry after {retry_after}s"
                                )
                                if attempt < max_retries - 1:
                                    await asyncio.sleep(retry_after)
                                    break
                                raise self._build_retryable_error(
                                    response,
                                    retry_after=retry_after,
                                    retry_after_source=retry_after_source,
                                    default_message="Rate limit exceeded",
                                )

                            if (
                                response.status_code in {502, 503, 504}
                                and self._has_retry_after_header(response)
                            ):
                                retry_after, retry_after_source = self._resolve_retry_after(
                                    response,
                                    default=5,
                                )
                                logger.warning(
                                    "[CONFLUENCE][API] Retryable server error, retry after %ss: status=%s url=%s",
                                    retry_after,
                                    response.status_code,
                                    url,
                                )
                                if attempt < max_retries - 1:
                                    await asyncio.sleep(retry_after)
                                    break
                                raise self._build_retryable_error(
                                    response,
                                    retry_after=retry_after,
                                    retry_after_source=retry_after_source,
                                    default_message=(
                                        f"Confluence API temporary failure [{response.status_code}]"
                                    ),
                                )

                            if response.status_code == 401:
                                if auth_retried:
                                    body = (response.text or "").strip()
                                    raise ConfluenceAuthError(
                                        f"Authentication failed for Confluence API. body={body[:300]}"
                                    )
                                auth_retried = True
                                force_refresh = True
                                continue

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

    @staticmethod
    def _extract_rate_limit_headers(response: httpx.Response) -> dict[str, str]:
        allowed_exact = {"retry-after", "beta-retry-after"}
        allowed_prefixes = ("x-ratelimit-", "ratelimit-", "x-beta-ratelimit-")
        return {
            key: value
            for key, value in response.headers.items()
            if key.lower() in allowed_exact
            or key.lower().startswith(allowed_prefixes)
        }

    def _resolve_retry_after(
        self,
        response: httpx.Response,
        *,
        default: int = 5,
    ) -> tuple[int, str]:
        headers = {key.lower(): value for key, value in response.headers.items()}
        if "beta-retry-after" in headers:
            return (
                parse_retry_after_header(headers["beta-retry-after"], default=default),
                "beta-retry-after",
            )
        if "retry-after" in headers:
            return (
                parse_retry_after_header(headers["retry-after"], default=default),
                "retry-after",
            )
        return max(1, int(default)), "default"

    def _has_retry_after_header(self, response: httpx.Response) -> bool:
        headers = {key.lower(): value for key, value in response.headers.items()}
        return "beta-retry-after" in headers or "retry-after" in headers

    def _build_retry_metadata(
        self,
        response: httpx.Response,
        *,
        retry_after: int,
        retry_after_source: str,
    ) -> dict[str, Any]:
        return {
            "status_code": response.status_code,
            "retry_after": retry_after,
            "retry_after_source": retry_after_source,
            "headers": self._extract_rate_limit_headers(response),
        }

    def _build_retryable_error(
        self,
        response: httpx.Response,
        *,
        retry_after: int,
        retry_after_source: str,
        default_message: str,
    ) -> ConnectorApiError:
        body = (response.text or "").strip()
        metadata = self._build_retry_metadata(
            response,
            retry_after=retry_after,
            retry_after_source=retry_after_source,
        )
        if response.status_code == 429:
            return ConfluenceRateLimitError(
                default_message,
                retry_after=retry_after,
                metadata=metadata,
            )

        return ConfluenceApiError(
            f"{default_message}. body={body[:300]}",
            status_code=response.status_code,
            retry_after=retry_after,
            metadata=metadata,
        )

    def _get_retry_after(self, response: httpx.Response, default: int = 5) -> int:
        retry_after, _source = self._resolve_retry_after(
            response,
            default=default,
        )
        return retry_after

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

        log = logger.info if all_results else logger.debug
        log("[CONFLUENCE][API] Paginated %s results from %s", len(all_results), url)
        return all_results

    async def _paginate_cursor_iter(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        result_key: str = "results",
        limit: int = 250,
    ):
        """커서 기반 페이지네이션으로 배치 단위 yield (대량 데이터용)"""
        current_params = dict(params or {})
        current_params["limit"] = limit

        while True:
            response = await self._request("GET", url, params=current_params)

            results = response.get(result_key, [])
            if not results:
                break

            yield results

            next_link = response.get("_links", {}).get("next")
            if not next_link:
                break

            cursor = self._extract_cursor_from_link(next_link)
            if not cursor:
                break

            current_params["cursor"] = cursor

    async def get_users(
        self,
        limit: int = 250,
    ) -> list[dict[str, Any]]:
        """
        Confluence 사용자 전체 조회 (v1 search API)
        - cql은 내부에서 고정: type=user (모든 사용자)
        - start/limit 기반 페이지네이션 자동 처리
        """
        all_results: list[dict[str, Any]] = []
        start = 0
        while True:
            params = {"cql": "type=user", "limit": limit, "start": start}
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

    async def get_spaces(
        self,
        space_type: str | None = None,
        status: str | None = "current",
        limit: int = 250,
    ) -> list[dict[str, Any]]:
        """
        Space 목록 조회
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

    async def get_page_by_id(
        self,
        page_id: str,
        body_format: str = "atlas_doc_format",
    ) -> dict[str, Any]:
        """단일 Page 조회"""
        params: dict[str, Any] = {"body-format": body_format}
        return await self._request(
            "GET",
            url=f"{self.base_url}/pages/{page_id}",
            params=params,
        )

    async def get_blogpost_by_id(
        self,
        blogpost_id: str,
        body_format: str = "atlas_doc_format",
    ) -> dict[str, Any]:
        """단일 BlogPost 조회"""
        params: dict[str, Any] = {"body-format": body_format}
        return await self._request(
            "GET",
            url=f"{self.base_url}/blogposts/{blogpost_id}",
            params=params,
        )

    async def get_content_footer_comments(
        self,
        content_type: str,  # "pages" | "blogposts"
        content_id: str,
        body_format: str = "atlas_doc_format",
        limit: int = 250,
    ) -> list[dict[str, Any]]:
        """콘텐츠의 Footer 코멘트 조회"""
        params: dict[str, Any] = {"body-format": body_format}
        return await self._paginate_cursor(
            url=f"{self.base_url}/{content_type}/{content_id}/footer-comments",
            params=params,
            limit=limit,
        )

    async def get_content_inline_comments(
        self,
        content_type: str,
        content_id: str,
        body_format: str = "atlas_doc_format",
        limit: int = 250,
    ) -> list[dict[str, Any]]:
        """콘텐츠의 Inline 코멘트 조회 (Page 전용)"""
        params: dict[str, Any] = {"body-format": body_format}
        return await self._paginate_cursor(
            url=f"{self.base_url}/{content_type}/{content_id}/inline-comments",
            params=params,
            limit=limit,
        )

    async def get_content_attachments(
        self,
        content_type: str,
        content_id: str,
        limit: int = 250,
    ) -> list[dict[str, Any]]:
        """콘텐츠의 첨부파일 조회"""
        return await self._paginate_cursor(
            url=f"{self.base_url}/{content_type}/{content_id}/attachments",
            limit=limit,
        )

    async def get_content_labels(
        self,
        content_type: str,
        content_id: str,
        limit: int = 250,
    ) -> list[dict[str, Any]]:
        """콘텐츠의 라벨 조회"""
        return await self._paginate_cursor(
            url=f"{self.base_url}/{content_type}/{content_id}/labels",
            limit=limit,
        )

    async def download_attachment(
        self,
        content_id: str,
        attachment_id: str,
        max_size_bytes: int = 5 * 1024 * 1024,
    ) -> bytes | None:
        """
        첨부파일 바이너리 다운로드 (이미지 임베딩용)

        Confluence REST v1의 documented download endpoint를 사용한다.

        Args:
            content_id: Page 또는 BlogPost ID
            attachment_id: Confluence Attachment ID
            max_size_bytes: 최대 다운로드 크기 (기본 5MB, Embed v4 제한)

        Returns:
            파일 바이너리 데이터, 실패 시 None
        """
        url = (
            f"{self.base_url_v1}/content/{content_id}/child/attachment/"
            f"{attachment_id}/download"
        )

        async with self._semaphore:
            try:
                auth_retried = False
                force_refresh = False
                retry_count = 0

                while True:
                    access_token = await self.token_provider.get_access_token(
                        self.cloud_id,
                        force_refresh=force_refresh,
                    )
                    async with httpx.AsyncClient(
                        headers={"Authorization": f"Bearer {access_token}"},
                        timeout=60.0,
                        follow_redirects=True,
                    ) as client:
                        response = await client.get(url)

                        if response.status_code == 429 or (
                            response.status_code in {502, 503, 504}
                            and self._has_retry_after_header(response)
                        ):
                            retry_after, retry_after_source = self._resolve_retry_after(
                                response,
                                default=5,
                            )
                            if retry_count >= self._attachment_max_retries:
                                logger.warning(
                                    "[CONFLUENCE][ATTACHMENT] Retryable download exhausted: "
                                    "status=%s, content_id=%s, attachment_id=%s, retry_after=%ss",
                                    response.status_code,
                                    content_id,
                                    attachment_id,
                                    retry_after,
                                )
                                raise self._build_retryable_error(
                                    response,
                                    retry_after=retry_after,
                                    retry_after_source=retry_after_source,
                                    default_message=(
                                        "Confluence attachment download rate limited"
                                        if response.status_code == 429
                                        else (
                                            "Confluence attachment download temporary failure "
                                            f"[{response.status_code}]"
                                        )
                                    ),
                                )

                            retry_count += 1
                            logger.warning(
                                "[CONFLUENCE][ATTACHMENT] Waiting %ss before retry "
                                "(attempt %s/%s): status=%s, content_id=%s, attachment_id=%s",
                                retry_after,
                                retry_count,
                                self._attachment_max_retries,
                                response.status_code,
                                content_id,
                                attachment_id,
                            )
                            await asyncio.sleep(retry_after)
                            continue

                        if response.status_code == 401:
                            if auth_retried:
                                logger.warning(
                                    "[CONFLUENCE][ATTACHMENT] Download unauthorized after refresh: "
                                    "content_id=%s, attachment_id=%s",
                                    content_id,
                                    attachment_id,
                                )
                                return None
                            auth_retried = True
                            force_refresh = True
                            continue

                        if response.status_code != 200:
                            logger.warning(
                                f"[CONFLUENCE][ATTACHMENT] Download failed: "
                                f"status={response.status_code}, content_id={content_id}, "
                                f"attachment_id={attachment_id}"
                            )
                            return None

                        content = response.content

                        if len(content) > max_size_bytes:
                            logger.info(
                                f"[CONFLUENCE][ATTACHMENT] File too large "
                                f"({len(content)} bytes > {max_size_bytes}), skipping: "
                                f"attachment_id={attachment_id}"
                            )
                            return None

                        await asyncio.sleep(self._rate_limit_delay)
                        return content

            except httpx.TimeoutException:
                logger.warning(
                    f"[CONFLUENCE][ATTACHMENT] Download timeout: content_id={content_id}, "
                    f"attachment_id={attachment_id}"
                )
                return None
            except Exception as e:
                if isinstance(e, ConnectorApiError) and e.retry_after is not None:
                    raise
                logger.warning(
                    f"[CONFLUENCE][ATTACHMENT] Download error: {e}, content_id={content_id}, "
                    f"attachment_id={attachment_id}"
                )
                return None


    # ================================================================
    # Streaming Iterators (대량 데이터용 - 배치 단위 yield)
    # ================================================================

    async def iter_pages(
        self,
        space_id: str,
        status: str = "current",
        sort: str = "-modified-date",
        body_format: str = "atlas_doc_format",
        limit: int = 250,
    ):
        """Space 내 Page를 배치 단위로 yield"""
        params: dict[str, Any] = {
            "space-id": space_id,
            "status": status,
            "sort": sort,
            "body-format": body_format,
        }
        async for batch in self._paginate_cursor_iter(
            url=f"{self.base_url}/pages",
            params=params,
            limit=limit,
        ):
            yield batch

    async def iter_blogposts(
        self,
        space_id: str,
        status: str = "current",
        sort: str = "-modified-date",
        body_format: str = "atlas_doc_format",
        limit: int = 250,
    ):
        """Space 내 BlogPost를 배치 단위로 yield"""
        params: dict[str, Any] = {
            "space-id": space_id,
            "status": status,
            "sort": sort,
            "body-format": body_format,
        }
        async for batch in self._paginate_cursor_iter(
            url=f"{self.base_url}/blogposts",
            params=params,
            limit=limit,
        ):
            yield batch
