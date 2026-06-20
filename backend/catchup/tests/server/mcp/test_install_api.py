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
async def test_get_mac_script_success():
    app.dependency_overrides[get_current_user] = lambda: _make_user()
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/mcp/install/mac")
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 200
    assert "text/x-shellscript" in resp.headers["content-type"]
    assert "/api/v1/mcp" in resp.text
    assert "install-catchup-mcp.sh" in resp.headers.get(
        "content-disposition", ""
    )


@pytest.mark.asyncio
async def test_get_windows_script_success():
    app.dependency_overrides[get_current_user] = lambda: _make_user()
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/mcp/install/windows")
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 200
    assert "text/plain" in resp.headers["content-type"]
    assert "/api/v1/mcp" in resp.text
    assert "install-catchup-mcp.ps1" in resp.headers.get(
        "content-disposition", ""
    )


@pytest.mark.asyncio
async def test_get_script_unsupported_platform():
    app.dependency_overrides[get_current_user] = lambda: _make_user()
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/mcp/install/linux")
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_script_unauthenticated():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/v1/mcp/install/mac")

    assert resp.status_code == 401
