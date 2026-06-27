import json
from datetime import datetime

from langchain_core.documents import Document

from catchup.audit.actions import McpAction
from catchup.components.embedder.constants import EmbeddingProvider
from catchup.components.embedder.factory import get_embedding_service
from catchup.components.vector_db.base import BaseVectorDbService
from catchup.components.vector_db.factory import get_vector_db_service
from catchup.components.vector_db.pgvector.constants import VectorDbProvider
from catchup.configs.config import settings
from catchup.db.models import SourceType
from catchup.mcp.tools.decorators import mcp_tool
from catchup.observability.logging.context import get_request_context
from catchup.rag.schemas.filters import build_temporal_filters

_VALID_SOURCES = {s.value for s in SourceType}


async def run_search(
    query: str,
    k: int,
    sources: list[str] | None,
    date_from: str | None,
    date_to: str | None,
    vector_db_service: BaseVectorDbService,
) -> list[dict]:
    tool_filters = _parse_sources(sources)
    temporal_filters = build_temporal_filters(
        tool_filters,
        _parse_date(date_from, "date_from"),
        _parse_date(date_to, "date_to"),
    )

    docs: list[Document] = await vector_db_service.hybrid_search(
        query=query,
        k=k,
        weights=[0.6, 0.4],  # [vector, contextual_content]
        tool_filters=tool_filters,
        temporal_filters=temporal_filters or None,
    )
    return _format_docs(docs)


def _parse_sources(sources: list[str] | None) -> list[SourceType] | None:
    if not sources:
        return None
    invalid = [s for s in sources if s not in _VALID_SOURCES]
    if invalid:
        raise ValueError(
            f"유효하지 않은 source: {invalid}. "
            f"허용값: {sorted(_VALID_SOURCES)}"
        )
    return [SourceType(s) for s in sources]


def _parse_date(value: str | None, field: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        raise ValueError(
            f"{field}은 ISO8601 형식이어야 합니다 (예: '2025-01-01'). "
            f"받은 값: {value!r}"
        )


def _format_docs(docs: list[Document]) -> list[dict]:
    results = []
    for doc in docs:
        meta = doc.metadata or {}
        results.append({
            "content": doc.page_content,
            "source": meta.get("source"),
            "url": meta.get("url"),
            "created_at": meta.get("created_at"),
            "author": meta.get("author_name") or meta.get("author"),
            "summary": meta.get("summary"),
        })
    return results


def serialize_results(results: list[dict]) -> str:
    return json.dumps(results, ensure_ascii=False, indent=2)


@mcp_tool(
    action=McpAction.SEARCH_KNOWLEDGE_BASE,
    observe_name="mcp-search-knowledge-base",
    emit_attempt=True,
)
async def search_knowledge_base(
    query: str,
    k: int = 10,
    sources: list[str] | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> str:
    """
    Search the company knowledge base using hybrid search (vector + keyword).

    Indexes content from Slack, Jira, Confluence, GitHub, and ChannelTalk — all in one
    query. Useful for questions about decisions, ongoing projects, team discussions,
    issue history, or any company-specific context that spans multiple platforms.

    Craft a descriptive, natural-language query that captures the user's intent.
    Richer queries yield better results than short keyword strings.

    Args:
        query: Natural-language search query describing what you are looking for.
        k: Number of documents to return (default: 10).
        sources: Restrict search to specific sources. Omit or leave empty to search
            across all sources. Valid values:
            slack, jira, confluence, github, channel_talk.
        date_from: Start date filter in ISO8601 format (e.g. "2025-01-01"). Optional.
        date_to: End date filter in ISO8601 format (e.g. "2025-12-31"). Optional.
    """
    embeddings = get_embedding_service(EmbeddingProvider.AWS_BEDROCK).get_embedder()
    vector_db_service = get_vector_db_service(VectorDbProvider.PGVECTOR, embeddings)

    if settings.ENABLE_LANGFUSE:
        from langfuse import get_client
        from langfuse import propagate_attributes

        actor: dict = get_request_context().get("actor") or {}
        user_id = str(actor["user_id"]) if actor.get("user_id") else None
        lf_metadata = {
            k: str(v)
            for k, v in {
                "email": actor.get("email"),
                "name": actor.get("name"),
                "department": actor.get("department"),
            }.items()
            if v is not None
        }
        with propagate_attributes(user_id=user_id, metadata=lf_metadata):
            results = await run_search(
                query, k, sources, date_from, date_to, vector_db_service
            )
        get_client().update_current_span(
            input={
                "query": query,
                "k": k,
                "sources": sources,
                "date_from": date_from,
                "date_to": date_to,
            },
            output=results,
        )
    else:
        results = await run_search(
            query, k, sources, date_from, date_to, vector_db_service
        )

    return serialize_results(results)
