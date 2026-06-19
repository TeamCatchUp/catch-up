from starlette.responses import PlainTextResponse
from starlette.testclient import TestClient
from starlette.types import ASGIApp

from catchup.auth.jwt import create_access_token
from catchup.server.middleware.mcp_auth import MCPAuthMiddleware


def _make_app() -> ASGIApp:
    async def inner(scope, receive, send):
        response = PlainTextResponse("ok")
        await response(scope, receive, send)

    return MCPAuthMiddleware(inner)


client = TestClient(_make_app(), raise_server_exceptions=False)


def test_no_token_returns_401():
    response = client.get("/api/mcp")
    assert response.status_code == 401


def test_invalid_token_returns_401():
    response = client.get(
        "/api/mcp", headers={"Authorization": "Bearer not-a-real-token"}
    )
    assert response.status_code == 401


def test_valid_token_passes_through():
    token = create_access_token(
        {"sub": "user-123", "email": "user@example.com"}
    )
    response = client.get(
        "/api/mcp", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert response.text == "ok"


def test_non_http_scope_passes_through():
    """lifespan 등 HTTP 외 scope는 인증 없이 통과한다."""
    passed = []

    async def inner(scope, receive, send):
        passed.append(scope["type"])

    middleware = MCPAuthMiddleware(inner)

    import asyncio

    async def run():
        await middleware({"type": "lifespan"}, None, None)

    asyncio.run(run())
    assert passed == ["lifespan"]
