import structlog
from starlette.responses import JSONResponse
from starlette.types import ASGIApp
from starlette.types import Receive
from starlette.types import Scope
from starlette.types import Send

from catchup.auth.jwt import verify_token
from catchup.configs.config import settings

logger = structlog.get_logger()

_WELL_KNOWN_SUFFIX = "/.well-known/oauth-authorization-server"


def _get_resource_base(scope: Scope) -> str:
    """X-Forwarded-* 헤더를 우선 참조해 public origin URL을 반환한다."""
    headers: dict[bytes, bytes] = dict(scope.get("headers", []))
    host = headers.get(b"host", b"localhost").decode("latin-1")
    proto = headers.get(b"x-forwarded-proto", b"").decode("latin-1")
    if not proto:
        proto = scope.get("scheme", "https")
    return f"{proto}://{host}"


def _make_unauthorized(resource_base: str) -> JSONResponse:
    """RFC 6750 WWW-Authenticate 헤더를 포함한 401 응답을 반환한다."""
    metadata_url = f"{resource_base}{_WELL_KNOWN_SUFFIX}"
    return JSONResponse(
        status_code=401,
        content={"detail": "MCP 엔드포인트는 인증이 필요합니다."},
        headers={
            "WWW-Authenticate": (
                f'Bearer realm="{resource_base}",'
                f' resource_metadata="{metadata_url}"'
            )
        },
    )


def _make_metadata_response(resource_base: str) -> JSONResponse:
    """RFC 8414 AS 메타데이터 JSON 응답을 반환한다."""
    base = resource_base
    return JSONResponse(
        content={
            "issuer": base,
            "authorization_endpoint": f"{base}/api/v1/mcp/oauth/authorize",
            "token_endpoint": f"{base}/api/v1/mcp/oauth/token",
            "registration_endpoint": f"{base}/api/v1/mcp/oauth/register",
            "scopes_supported": ["openid", "email", "profile"],
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code", "refresh_token"],
            "code_challenge_methods_supported": ["S256"],
            "token_endpoint_auth_methods_supported": ["none"],
        }
    )


def _extract_bearer_token(scope: Scope) -> str | None:
    """ASGI scope의 헤더에서 Bearer 토큰을 추출한다."""
    for key, value in scope.get("headers", []):
        if key.lower() == b"authorization":
            raw = value.decode("latin-1")
            if raw.lower().startswith("bearer "):
                return raw[7:].strip()
    return None


class MCPAuthMiddleware:
    """MCP SSE 앱에 인증 게이트와 OAuth 탐색 응답을 추가하는 ASGI 미들웨어."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(
        self, scope: Scope, receive: Receive, send: Send
    ) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        path: str = scope.get("path", "")
        resource_base = _get_resource_base(scope)

        # AS 메타데이터 탐색 요청은 미들웨어 안에서 직접 처리한다.
        # nginx 라우팅에 의존하지 않고 Claude가 어떤 경로로 접근해도 응답한다.
        if path.endswith(_WELL_KNOWN_SUFFIX):
            if not settings.MCP_OAUTH_ENABLED:
                await JSONResponse(
                    {"detail": "Not Found"}, status_code=404
                )(scope, receive, send)
                return
            await _make_metadata_response(resource_base)(scope, receive, send)
            return

        token = _extract_bearer_token(scope)
        if not token:
            await _make_unauthorized(resource_base)(scope, receive, send)
            return

        try:
            verify_token(token, "access")
        except Exception:
            logger.warning("mcp_auth_failed", reason="invalid_token")
            await _make_unauthorized(resource_base)(scope, receive, send)
            return

        await self.app(scope, receive, send)
