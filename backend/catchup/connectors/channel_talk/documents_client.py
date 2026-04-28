from __future__ import annotations

import base64
from collections.abc import Buffer
from collections.abc import Sequence
from typing import Any
from urllib.parse import quote

import httpx
import structlog

from catchup.configs.config import settings
from catchup.connectors.base.retry import parse_retry_after_header
from catchup.connectors.channel_talk.exceptions import ChannelTalkAuthenticationError
from catchup.connectors.channel_talk.exceptions import ChannelTalkRateLimitError
from catchup.connectors.channel_talk.exceptions import ChannelTalkTimeoutError
from catchup.connectors.channel_talk.exceptions import ChannelTalkUpstreamError
from catchup.connectors.channel_talk.exceptions import ChannelTalkValidationError
from catchup.connectors.channel_talk.http_helpers import build_since_limit_params
from catchup.connectors.channel_talk.http_helpers import decode_response_json
from catchup.connectors.channel_talk.http_helpers import extract_response_error_metadata
from catchup.connectors.channel_talk.http_helpers import is_success_response
from catchup.connectors.channel_talk.http_helpers import parse_channel_talk_payload
from catchup.connectors.channel_talk.schemas.document_article import (
    ChannelTalkDocumentArticleBatchResult,
)
from catchup.connectors.channel_talk.schemas.document_article import (
    ChannelTalkDocumentArticlePage,
)
from catchup.connectors.channel_talk.schemas.document_article import (
    ChannelTalkDocumentArticleState,
)
from catchup.connectors.channel_talk.schemas.document_article import (
    ChannelTalkDocumentArticleView,
)
from catchup.connectors.channel_talk.schemas.document_metadata import (
    ChannelTalkDocumentAuthorPage,
)
from catchup.connectors.channel_talk.schemas.document_metadata import (
    ChannelTalkDocumentNavNodePage,
)
from catchup.connectors.channel_talk.schemas.document_metadata import (
    ChannelTalkDocumentSpace,
)
from catchup.utils.client import get_global_async_client

logger = structlog.get_logger(__name__)
RequestParams = dict[str, Any] | list[tuple[str, str]]

ARTICLE_BATCH_MAX_SIZE = 25
DEFAULT_ARTICLE_LIST_LIMIT = 25
DEFAULT_ARTICLE_LIST_ORDER = "asc"


class ChannelTalkDocumentsApiClient:
    def __init__(
        self,
        *,
        access_key: str,
        access_secret: str,
        base_url: str | None = None,
        timeout_seconds: float | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        default_base_url = getattr(
            settings,
            "CHANNEL_TALK_DOCUMENTS_API_URL",
            "https://document-api.channel.io",
        )
        default_timeout = getattr(settings, "CHANNEL_TALK_API_TIMEOUT_SECONDS", 10.0)

        self.base_url = str(base_url or default_base_url).rstrip("/")
        self.timeout_seconds = float(timeout_seconds or default_timeout)
        self._http_client = http_client or get_global_async_client()
        self._headers = self._build_headers(
            access_key=access_key,
            access_secret=access_secret,
        )

    async def get_current_space(self) -> ChannelTalkDocumentSpace:
        payload = await self._request(
            method="GET",
            path="/open/v1/spaces/$me",
        )
        return parse_channel_talk_payload(
            payload,
            parser=ChannelTalkDocumentSpace.from_api_payload,
            log_event="channel_talk_documents_invalid_space_payload",
            error_message="Channel Talk Documents returned an invalid space payload",
            logger=logger,
        )

    async def list_articles(
        self,
        *,
        language: str,
        state: ChannelTalkDocumentArticleState | str | None = None,
        topic_id: str | None = None,
        since: str | None = None,
        limit: int = DEFAULT_ARTICLE_LIST_LIMIT,
        order: str | None = DEFAULT_ARTICLE_LIST_ORDER,
    ) -> ChannelTalkDocumentArticlePage:
        payload = await self._request(
            method="GET",
            path="/open/v1/spaces/$me/articles",
            params=self._build_article_list_params(
                language=language,
                state=state,
                topic_id=topic_id,
                since=since,
                limit=limit,
                order=order,
            ),
        )
        return parse_channel_talk_payload(
            payload,
            parser=ChannelTalkDocumentArticlePage.from_api_payload,
            log_event="channel_talk_documents_invalid_article_list_payload",
            error_message="Channel Talk Documents returned an invalid article list payload",
            logger=logger,
        )

    async def get_article(
        self,
        *,
        article_id: str,
        language: str,
    ) -> ChannelTalkDocumentArticleView:
        normalized_article_id = self._require_query_text(article_id, "article_id")
        payload = await self._request(
            method="GET",
            path=f"/open/v1/spaces/$me/articles/{quote(normalized_article_id, safe='')}",
            params={"language": self._require_query_text(language, "language")},
        )
        return parse_channel_talk_payload(
            payload,
            parser=ChannelTalkDocumentArticleView.from_api_payload,
            log_event="channel_talk_documents_invalid_article_payload",
            error_message="Channel Talk Documents returned an invalid article payload",
            logger=logger,
        )

    async def batch_get_articles(
        self,
        *,
        article_ids: Sequence[str],
        language: str,
    ) -> ChannelTalkDocumentArticleBatchResult:
        payload = await self._request(
            method="GET",
            path="/open/v1/spaces/$me/articles/batch",
            params=self._build_article_batch_params(
                article_ids=article_ids,
                language=language,
            ),
        )
        return parse_channel_talk_payload(
            payload,
            parser=ChannelTalkDocumentArticleBatchResult.from_api_payload,
            log_event="channel_talk_documents_invalid_article_batch_payload",
            error_message="Channel Talk Documents returned an invalid article batch payload",
            logger=logger,
        )

    async def list_authors(
        self,
        *,
        since: str | None = None,
        limit: int = 100,
    ) -> ChannelTalkDocumentAuthorPage:
        payload = await self._request(
            method="GET",
            path="/open/v1/spaces/$me/authors",
            params=build_since_limit_params(since=since, limit=limit),
        )
        return parse_channel_talk_payload(
            payload,
            parser=ChannelTalkDocumentAuthorPage.from_api_payload,
            log_event="channel_talk_documents_invalid_author_list_payload",
            error_message="Channel Talk Documents returned an invalid author list payload",
            logger=logger,
        )

    async def list_nav_nodes(self) -> ChannelTalkDocumentNavNodePage:
        payload = await self._request(
            method="GET",
            path="/open/v1/spaces/$me/nav-nodes/$all",
        )
        return parse_channel_talk_payload(
            payload,
            parser=ChannelTalkDocumentNavNodePage.from_api_payload,
            log_event="channel_talk_documents_invalid_nav_node_payload",
            error_message="Channel Talk Documents returned an invalid navigation payload",
            logger=logger,
        )

    @staticmethod
    def _build_headers(
        *,
        access_key: str,
        access_secret: str,
    ) -> dict[str, str]:
        normalized_access_key = str(access_key or "").strip()
        normalized_access_secret = str(access_secret or "").strip()
        if not normalized_access_key or not normalized_access_secret:
            raise ChannelTalkValidationError(
                "Channel Talk Documents credentials are required"
            )
        credentials: Buffer = (
            f"{normalized_access_key}:{normalized_access_secret}".encode("utf-8")
        )
        token = base64.b64encode(credentials).decode("ascii")
        return {
            "Accept": "application/json",
            "Authorization": f"Basic {token}",
        }

    @classmethod
    def _build_article_list_params(
        cls,
        *,
        language: str,
        state: ChannelTalkDocumentArticleState | str | None,
        topic_id: str | None,
        since: str | None,
        limit: int,
        order: str | None,
    ) -> dict[str, Any]:
        try:
            normalized_limit = int(limit)
        except (TypeError, ValueError) as exc:
            raise ChannelTalkValidationError(
                "Channel Talk Documents limit must be a positive integer"
            ) from exc
        if normalized_limit < 1:
            raise ChannelTalkValidationError(
                "Channel Talk Documents limit must be a positive integer"
            )
        params: dict[str, Any] = {
            "language": cls._require_query_text(language, "language"),
            "limit": normalized_limit,
        }
        if state is not None:
            normalized_state = str(
                state.value
                if isinstance(state, ChannelTalkDocumentArticleState)
                else state
            ).strip()
            if normalized_state:
                allowed_states = {
                    article_state.value
                    for article_state in ChannelTalkDocumentArticleState
                }
                if normalized_state not in allowed_states:
                    raise ChannelTalkValidationError(
                        "Channel Talk Documents article list state must be "
                        "published, unpublished, or draft"
                    )
                params["state"] = normalized_state
        if topic_id is not None and str(topic_id).strip():
            params["topicId"] = str(topic_id).strip()
        if since is not None and str(since).strip():
            params["since"] = str(since).strip()
        if order is not None:
            normalized_order = str(order).strip()
            if normalized_order:
                if normalized_order not in {"asc", "desc"}:
                    raise ChannelTalkValidationError(
                        "Channel Talk Documents article list order must be asc or desc"
                    )
                params["order"] = normalized_order
        return params

    @classmethod
    def _build_article_batch_params(
        cls,
        *,
        article_ids: Sequence[str],
        language: str,
    ) -> list[tuple[str, str]]:
        if isinstance(article_ids, str | bytes):
            raise ChannelTalkValidationError(
                "Channel Talk Documents article ids must be a sequence of strings"
            )
        normalized_ids = [
            str(article_id).strip()
            for article_id in article_ids
            if str(article_id).strip()
        ]
        if not normalized_ids:
            raise ChannelTalkValidationError(
                "At least one Channel Talk Documents article id is required"
            )
        if len(normalized_ids) > ARTICLE_BATCH_MAX_SIZE:
            raise ChannelTalkValidationError(
                "Channel Talk Documents article batch can fetch up to "
                f"{ARTICLE_BATCH_MAX_SIZE} articles"
            )
        params = cls._build_language_params(language)
        params.extend(("ids[]", article_id) for article_id in normalized_ids)
        return params

    @classmethod
    def _build_language_params(cls, language: str) -> list[tuple[str, str]]:
        return [("language", cls._require_query_text(language, "language"))]

    @staticmethod
    def _require_query_text(value: str, field_name: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ChannelTalkValidationError(
                f"Channel Talk Documents {field_name} is required"
            )
        return normalized

    async def _request(
        self,
        *,
        method: str,
        path: str,
        params: RequestParams | None = None,
    ) -> Any:
        response = await self._send_request(
            method=method,
            path=path,
            params=params,
        )
        return self._decode_response(response)

    async def _send_request(
        self,
        *,
        method: str,
        path: str,
        params: RequestParams | None = None,
    ) -> httpx.Response:
        url = f"{self.base_url}{path}"
        try:
            return await self._http_client.request(
                method,
                url,
                headers=self._headers,
                params=params,
                timeout=self.timeout_seconds,
            )
        except httpx.TimeoutException as exc:
            logger.warning("channel_talk_documents_request_timed_out", url=url)
            raise ChannelTalkTimeoutError(
                "Channel Talk Documents API request timed out"
            ) from exc
        except httpx.HTTPError as exc:
            logger.exception("channel_talk_documents_request_failed", url=url)
            raise ChannelTalkUpstreamError(
                "Failed to reach Channel Talk Documents API",
                metadata={"reason": str(exc)},
            ) from exc

    def _decode_response(self, response: httpx.Response) -> Any:
        if is_success_response(response):
            return decode_response_json(
                response,
                error_message="Channel Talk Documents returned a non-JSON response",
            )

        raise self._build_response_error(response)

    @staticmethod
    def _build_response_error(response: httpx.Response) -> Exception:
        metadata = extract_response_error_metadata(response)
        status_code = response.status_code
        if status_code in (401, 403):
            return ChannelTalkAuthenticationError(
                "Channel Talk Documents credentials are invalid or unauthorized",
                metadata=metadata,
            )
        if status_code == 429:
            return ChannelTalkRateLimitError(
                retry_after=parse_retry_after_header(
                    response.headers.get("Retry-After"),
                    default=60,
                ),
                metadata=metadata,
            )
        if status_code == 400:
            return ChannelTalkValidationError(
                "Channel Talk Documents rejected the request",
                metadata=metadata,
            )
        if status_code >= 500:
            return ChannelTalkUpstreamError(
                "Channel Talk Documents API is temporarily unavailable",
                status_code=status_code,
                metadata=metadata,
            )
        return ChannelTalkUpstreamError(
            "Channel Talk Documents API request failed",
            status_code=status_code,
            metadata=metadata,
        )
