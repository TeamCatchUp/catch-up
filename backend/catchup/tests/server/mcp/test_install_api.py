from unittest.mock import AsyncMock
from unittest.mock import patch

import pytest
from httpx import ASGITransport
from httpx import AsyncClient

from catchup.auth.dependencies import get_current_user
from catchup.db.models import User
from catchup.server.main import app


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


@pytest.mark.asyncio
async def test_get_mac_script_success():
    mock_redis = AsyncMock()
    mock_redis.getdel = AsyncMock(return_value=b"1")

    with patch(
        "catchup.server.mcp.install_api.get_redis_client",
        return_value=mock_redis,
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(
                "/api/v1/mcp/install/mac",
                params={"token": "test-token"},
            )

    assert resp.status_code == 200
    assert "text/x-shellscript" in resp.headers["content-type"]
    assert "/api/v1/mcp" in resp.text
    assert "install-catchup-mcp.sh" in resp.headers.get(
        "content-disposition", ""
    )


@pytest.mark.asyncio
async def test_get_windows_script_success():
    mock_redis = AsyncMock()
    mock_redis.getdel = AsyncMock(return_value=b"1")

    with patch(
        "catchup.server.mcp.install_api.get_redis_client",
        return_value=mock_redis,
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(
                "/api/v1/mcp/install/windows",
                params={"token": "test-token"},
            )

    assert resp.status_code == 200
    assert "/api/v1/mcp" in resp.text
    assert "install-catchup-mcp.ps1" in resp.headers.get(
        "content-disposition", ""
    )


@pytest.mark.asyncio
async def test_get_script_invalid_token():
    mock_redis = AsyncMock()
    mock_redis.getdel = AsyncMock(return_value=None)

    with patch(
        "catchup.server.mcp.install_api.get_redis_client",
        return_value=mock_redis,
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(
                "/api/v1/mcp/install/mac",
                params={"token": "expired-token"},
            )

    assert resp.status_code == 401
    assert "만료" in resp.json()["detail"]
