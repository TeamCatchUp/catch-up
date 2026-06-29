from urllib.parse import urlparse

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations

from catchup.configs.config import auth_settings
from catchup.configs.config import settings
from catchup.mcp.tools.search import read_documents
from catchup.mcp.tools.search import search_documents
from catchup.mcp.tools.v2_sampling import get_v2_backfill_state
from catchup.mcp.tools.v2_sampling import sample_v2_knowledge_store


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

_READ_ONLY = ToolAnnotations(readOnlyHint=True)
_WRITE_ADDITIVE = ToolAnnotations(readOnlyHint=False, destructiveHint=False)
_WRITE_DESTRUCTIVE = ToolAnnotations(readOnlyHint=False, destructiveHint=True)


def _register_tools(mcp: FastMCP) -> None:
    """MCP 인스턴스에 모든 툴을 등록한다."""
    mcp.add_tool(search_documents, annotations=_READ_ONLY)
    mcp.add_tool(read_documents, annotations=_READ_ONLY)
    if settings.MCP_V2_SAMPLING_ENABLED:
        mcp.add_tool(sample_v2_knowledge_store, annotations=_READ_ONLY)
        mcp.add_tool(get_v2_backfill_state, annotations=_READ_ONLY)


_register_tools(mcp)
