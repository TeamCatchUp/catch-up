from urllib.parse import urlparse

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from catchup.audit.actions import McpAction
from catchup.audit.metadata import McpAuditMetadata
from catchup.audit.utils import audit_log
from catchup.components.embedder.constants import EmbeddingProvider
from catchup.components.embedder.factory import get_embedding_service
from catchup.components.vector_db.factory import get_vector_db_service
from catchup.components.vector_db.pgvector.constants import VectorDbProvider
from catchup.configs.config import auth_settings
from catchup.configs.config import settings
from catchup.mcp.tools.search import run_search
from catchup.mcp.tools.search import serialize_results
from catchup.observability.langfuse.configs import get_observe
from catchup.observability.logging.context import get_request_context

observe = get_observe()


def _build_transport_security() -> TransportSecuritySettings:
    """DNS rebinding 보호용 TransportSecuritySettings를 구성한다."""
    extra_host = urlparse(auth_settings.FRONTEND_BASE_URL, "").netloc or None
    allowed_hosts = ["127.0.0.1:*", "localhost:*", "localhost", "[::1]:*"]
    allowed_origins = [
        "http://127.0.0.1:*", "http://localhost:*", "http://localhost", "http://[::1]:*",
    ]
    if extra_host:
        allowed_hosts.append(extra_host)
        allowed_origins.append(f"https://{extra_host}")
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=allowed_hosts,
        allowed_origins=allowed_origins,
    )


mcp = FastMCP(
    "catchup-knowledge-base",
    streamable_http_path="/",
    stateless_http=True,
    transport_security=_build_transport_security(),
)

@mcp.tool()
@observe(name="mcp-search-knowledge-base")
@audit_log(
    McpAction.SEARCH_KNOWLEDGE_BASE,
    emit_attempt=True,
    metadata_factory=McpAuditMetadata.from_audit,
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


if settings.MCP_V2_SAMPLING_ENABLED:
    from catchup.mcp.tools.v2_sampling import get_v2_backfill_status
    from catchup.mcp.tools.v2_sampling import sample_v2_knowledge_rows
    from catchup.mcp.tools.v2_sampling import serialize_sampling_result

    @mcp.tool()
    async def sample_v2_knowledge_store(
        source: str,
        entity_type: str,
        sample_type: str = "latest",
        limit: int = 10,
        content_chars: int = 800,
    ) -> str:
        """
        v2 knowledge_store row를 source/entity_type 단위로 샘플링합니다.

        Raw SQL은 허용하지 않고 allowlist 파라미터만 받습니다. embedding 컬럼은
        반환하지 않으며 content/body는 preview 길이로 제한됩니다.

        Args:
            source: github, slack, jira, channel_talk, confluence
            entity_type: source별 entity type
            sample_type: latest, random, seed, failed_backfill
            limit: 반환할 row 수. 최대 30.
            content_chars: content/body preview 길이. 최대 4000.
        """
        result = await sample_v2_knowledge_rows(
            source=source,
            entity_type=entity_type,
            sample_type=sample_type,
            limit=limit,
            content_chars=content_chars,
        )
        result["enabled"] = True
        return serialize_sampling_result(result)

    @mcp.tool()
    async def get_v2_backfill_state(
        source: str | None = None,
        entity_type: str | None = None,
        limit: int = 50,
    ) -> str:
        """
        vector_store_v2_backfill_states 상태를 read-only로 조회합니다.

        Args:
            source: 선택 필터. github, slack, jira, channel_talk, confluence.
            entity_type: 선택 필터. source와 함께 주면 source별 allowlist 검증.
            limit: 반환할 state row 수. 최대 100.
        """
        result = await get_v2_backfill_status(
            source=source,
            entity_type=entity_type,
            limit=limit,
        )
        result["enabled"] = True
        return serialize_sampling_result(result)
