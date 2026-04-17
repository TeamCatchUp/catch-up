import os
from urllib.parse import urlparse

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from catchup.components.vector_db.pgvector.constants import VectorDbProvider
from catchup.mcp.tools.search import run_search, serialize_results
from catchup.configs.config import auth_settings

_extra_host = urlparse(auth_settings.FRONTEND_BASE_URL, "").netloc or None
_allowed_hosts = ["127.0.0.1:*", "localhost:*", "localhost", "[::1]:*"]
_allowed_origins = [
    "http://127.0.0.1:*", "http://localhost:*", "http://localhost", "http://[::1]:*",
]
if _extra_host:
    _allowed_hosts.append(_extra_host)
    _allowed_origins.append(f"https://{_extra_host}")

mcp = FastMCP(
    "catchup-knowledge-base",
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=_allowed_hosts,
        allowed_origins=_allowed_origins,
    ),
)

@mcp.tool()
async def search_knowledge_base(
    query: str,
    k: int = 10,
    sources: list[str] | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> str:
    """
    Catch Up 지식베이스에서 관련 문서를 하이브리드 검색(벡터+키워드)으로 조회합니다.
    하이브리드 검색에 최적화된 쿼리를 생성하세요.

    Args:
        query: 검색 쿼리
        k: 반환할 문서 수 (기본값: 10)
        sources: 검색할 소스 목록 (slack, jira, confluence, github). 미지정 시 전체 검색.
        date_from: 검색 시작일 (ISO8601, UTC, 예: "2025-01-01")
        date_to: 검색 종료일 (ISO8601, UTC, 예: "2025-12-31")
    """
    from catchup.components.embedder.constants import EmbeddingProvider
    from catchup.components.embedder.factory import get_embedding_service
    from catchup.components.vector_db.factory import get_vector_db_service

    embeddings = get_embedding_service(EmbeddingProvider.AWS_BEDROCK).get_embedder()
    vector_db_service = get_vector_db_service(VectorDbProvider.PGVECTOR, embeddings)
    results = await run_search(query, k, sources, date_from, date_to, vector_db_service)
    return serialize_results(results)
