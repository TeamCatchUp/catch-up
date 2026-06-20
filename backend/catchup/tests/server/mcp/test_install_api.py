import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport
from catchup.server.main import app
from catchup.auth.dependencies import get_current_user
from catchup.db.models import User


def _make_user() -> User:
    user = User()
    user.id = 1
    user.email = "test@example.com"
    return user


@pytest.mark.asyncio
async def test_issue_install_token_success():
    mock_redis = AsyncMock()
    mock_redis.setex = AsyncMock()

    app.dependency_overrides[get_current_user] = lambda: _make_user()
    try:
        with patch(
            "catchup.server.mcp.install_api.get_redis_client",
            return_value=mock_redis,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.post(
                    "/api/v1/mcp/install/token",
                    headers={"Authorization": "Bearer fake-jwt"},
                )
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 200
    body = resp.json()
    assert "token" in body
    assert body["expires_in"] == 600
    mock_redis.setex.assert_called_once()
