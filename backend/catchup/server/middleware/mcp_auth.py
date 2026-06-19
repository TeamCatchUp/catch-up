import structlog
from starlette.responses import JSONResponse
from starlette.types import ASGIApp
from starlette.types import Receive
from starlette.types import Scope
from starlette.types import Send

from catchup.auth.jwt import verify_token

logger = structlog.get_logger()

_UNAUTHORIZED = JSONResponse(
    status_code=401,
    content={"detail": "MCP 엔드포인트는 인증이 필요합니다."},
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
    """MCP SSE 앱에 인증 게이트를 추가하는 ASGI 미들웨어."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(
        self, scope: Scope, receive: Receive, send: Send
    ) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        token = _extract_bearer_token(scope)
        if not token:
            await _UNAUTHORIZED(scope, receive, send)
            return

        try:
            verify_token(token, "access")
        except Exception:
            logger.warning("mcp_auth_failed", reason="invalid_token")
            await _UNAUTHORIZED(scope, receive, send)
            return

        await self.app(scope, receive, send)
