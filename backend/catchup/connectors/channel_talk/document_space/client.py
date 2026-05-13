from __future__ import annotations

from collections.abc import Sequence
from typing import Any
from urllib.parse import quote

import structlog

from catchup.connectors.channel_talk.document_space.http_client import (
    ChannelTalkDocumentsHttpClient,
)
from catchup.connectors.channel_talk.exceptions import ChannelTalkValidationError
from catchup.connectors.channel_talk.http_helpers import build_since_limit_params
from catchup.connectors.channel_talk.http_helpers import parse_channel_talk_payload
from catchup.connectors.channel_talk.schemas.document_article import (
    ChannelTalkDocumentArticleBatchResult,
)
from catchup.connectors.channel_talk.schemas.document_article import (
    ChannelTalkDocumentArticlePage,
)
from catchup.connectors.channel_talk.schemas.document_article import (
    ChannelTalkDocumentArticleRevisionView,
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

logger = structlog.get_logger(__name__)

ARTICLE_BATCH_MAX_SIZE = 25
DEFAULT_ARTICLE_LIST_LIMIT = 25
DEFAULT_ARTICLE_LIST_ORDER = "asc"


class ChannelTalkDocumentsApiClient:
    def __init__(
        self,
        *,
        transport: ChannelTalkDocumentsHttpClient,
    ) -> None:
        self._transport = transport

    async def get_current_space(self) -> ChannelTalkDocumentSpace:
        payload = await self._transport.request_json(
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
        payload = await self._transport.request_json(
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
        payload = await self._transport.request_json(
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

    async def get_article_revision(
        self,
        *,
        article_id: str,
        revision_id: str,
    ) -> ChannelTalkDocumentArticleRevisionView:
        normalized_article_id = self._require_query_text(article_id, "article_id")
        normalized_revision_id = self._require_query_text(
            revision_id,
            "revision_id",
        )
        payload = await self._transport.request_json(
            method="GET",
            path=(
                f"/open/v1/spaces/$me/articles/"
                f"{quote(normalized_article_id, safe='')}/revisions/"
                f"{quote(normalized_revision_id, safe='')}"
            ),
        )
        return parse_channel_talk_payload(
            payload,
            parser=ChannelTalkDocumentArticleRevisionView.from_api_payload,
            log_event="channel_talk_documents_invalid_article_revision_payload",
            error_message=(
                "Channel Talk Documents returned an invalid article revision payload"
            ),
            logger=logger,
        )

    async def batch_get_articles(
        self,
        *,
        article_ids: Sequence[str],
        language: str,
    ) -> ChannelTalkDocumentArticleBatchResult:
        payload = await self._transport.request_json(
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
        payload = await self._transport.request_json(
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
        payload = await self._transport.request_json(
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
