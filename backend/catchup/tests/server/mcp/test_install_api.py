import pytest
from httpx import ASGITransport
from httpx import AsyncClient

from catchup.server.main import app


@pytest.mark.asyncio
async def test_get_mac_script_success():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/v1/mcp/script/mac")

    assert resp.status_code == 200
    assert "text/x-shellscript" in resp.headers["content-type"]
    assert "/api/v1/mcp" in resp.text
    assert "content-disposition" not in resp.headers


@pytest.mark.asyncio
async def test_get_windows_script_success():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/v1/mcp/script/windows")

    assert resp.status_code == 200
    assert "text/plain" in resp.headers["content-type"]
    assert "/api/v1/mcp" in resp.text
    assert "content-disposition" not in resp.headers


@pytest.mark.asyncio
async def test_get_script_unsupported_platform():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/v1/mcp/script/linux")

    assert resp.status_code == 404
