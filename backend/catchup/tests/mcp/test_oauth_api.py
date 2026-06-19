import json
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from catchup.server.main import app

client = TestClient(app)

_BASE = "/api/v1/mcp/oauth"


@pytest.fixture(autouse=True)
def enable_mcp_oauth(monkeypatch):
    from catchup.configs.config import settings

    monkeypatch.setattr(settings, "MCP_OAUTH_ENABLED", True)


@pytest.fixture()
def mock_redis():
    store: dict = {}

    async def setex(key, ttl, value):
        store[key] = value

    async def get(key):
        v = store.get(key)
        return v.encode() if isinstance(v, str) else v

    async def getdel(key):
        v = store.pop(key, None)
        return v.encode() if isinstance(v, str) else v

    redis = MagicMock()
    redis.setex = AsyncMock(side_effect=setex)
    redis.get = AsyncMock(side_effect=get)
    redis.getdel = AsyncMock(side_effect=getdel)

    with patch(
        "catchup.server.mcp.oauth_api.get_redis_client",
        AsyncMock(return_value=redis),
    ):
        yield store


class TestOAuthAuthorizationServerMetadata:
    def test_returns_metadata_when_enabled(self):
        response = client.get("/.well-known/oauth-authorization-server")

        assert response.status_code == 200
        data = response.json()
        assert "/api/v1/mcp/oauth/token" in data["token_endpoint"]
        assert "/api/v1/mcp/oauth/authorize" in data["authorization_endpoint"]
        assert "/api/v1/mcp/oauth/register" in data["registration_endpoint"]
        assert "S256" in data["code_challenge_methods_supported"]
        assert "none" in data["token_endpoint_auth_methods_supported"]

    def test_returns_404_when_disabled(self, monkeypatch):
        from catchup.configs.config import settings

        monkeypatch.setattr(settings, "MCP_OAUTH_ENABLED", False)
        response = client.get("/.well-known/oauth-authorization-server")

        assert response.status_code == 404


class TestDynamicClientRegistration:
    def test_register_returns_client_id(self, mock_redis):
        response = client.post(
            f"{_BASE}/register",
            json={
                "redirect_uris": ["https://claude.ai/api/mcp/auth_callback"],
                "client_name": "Claude Desktop",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["client_id"].startswith("mcp-")
        assert data["token_endpoint_auth_method"] == "none"

    def test_register_stores_client_in_redis(self, mock_redis):
        client.post(
            f"{_BASE}/register",
            json={"redirect_uris": ["https://claude.ai/api/mcp/auth_callback"]},
        )

        keys = [k for k in mock_redis if k.startswith("mcp:client:")]
        assert len(keys) == 1


class TestAuthorizeEndpoint:
    def test_unknown_client_id_returns_400(self, mock_redis):
        response = client.get(
            f"{_BASE}/authorize",
            params={
                "client_id": "mcp-unknown",
                "redirect_uri": "https://claude.ai/api/mcp/auth_callback",
                "state": "abc",
                "code_challenge": "challenge123",
            },
            follow_redirects=False,
        )

        assert response.status_code == 400

    def test_known_client_redirects_to_keycloak(self, mock_redis):
        reg = client.post(
            f"{_BASE}/register",
            json={"redirect_uris": ["https://claude.ai/api/mcp/auth_callback"]},
        )
        client_id = reg.json()["client_id"]

        response = client.get(
            f"{_BASE}/authorize",
            params={
                "client_id": client_id,
                "redirect_uri": "https://claude.ai/api/mcp/auth_callback",
                "state": "original-state",
                "code_challenge": "challenge123",
                "code_challenge_method": "S256",
            },
            follow_redirects=False,
        )

        from urllib.parse import unquote

        assert response.status_code == 302
        location = unquote(response.headers["location"])
        assert "openid-connect/auth" in location
        assert "challenge123" in location
        assert "/api/v1/mcp/oauth/callback" in location


class TestCallbackEndpoint:
    def test_invalid_state_returns_400(self, mock_redis):
        response = client.get(
            f"{_BASE}/callback",
            params={"code": "authcode", "state": "nonexistent"},
        )

        assert response.status_code == 400

    def test_valid_state_relays_code_to_original_redirect_uri(
        self, mock_redis
    ):
        mock_redis["mcp:state:teststate"] = json.dumps({
            "original_redirect_uri": "https://claude.ai/api/mcp/auth_callback",
            "original_state": "original-state",
        })

        response = client.get(
            f"{_BASE}/callback",
            params={"code": "authcode", "state": "teststate"},
            follow_redirects=False,
        )

        assert response.status_code == 302
        location = response.headers["location"]
        assert "claude.ai" in location
        assert "authcode" in location
        assert "original-state" in location


class TestTokenEndpointAuthorizationCode:
    def test_missing_code_returns_400(self):
        response = client.post(
            f"{_BASE}/token",
            data={"grant_type": "authorization_code", "code_verifier": "v"},
        )

        assert response.status_code == 400

    def test_missing_code_verifier_returns_400(self):
        response = client.post(
            f"{_BASE}/token",
            data={"grant_type": "authorization_code", "code": "authcode"},
        )

        assert response.status_code == 400

    def test_keycloak_failure_returns_401(self):
        mock_provider = MagicMock()
        mock_provider.get_oauth_user_info = AsyncMock(
            side_effect=Exception("keycloak error")
        )

        with patch(
            "catchup.server.mcp.oauth_api.OAuthIdentityProvider",
            return_value=mock_provider,
        ):
            response = client.post(
                f"{_BASE}/token",
                data={
                    "grant_type": "authorization_code",
                    "code": "authcode",
                    "code_verifier": "verifier123",
                },
            )

        assert response.status_code == 401

    def test_successful_code_exchange_returns_tokens(self):
        mock_user = MagicMock()
        mock_user.sub = "user-sub-123"
        mock_user.email = "user@example.com"
        mock_user.name = "Test User"

        mock_provider = MagicMock()
        mock_provider.get_oauth_user_info = AsyncMock(return_value=mock_user)

        with patch(
            "catchup.server.mcp.oauth_api.OAuthIdentityProvider",
            return_value=mock_provider,
        ):
            response = client.post(
                f"{_BASE}/token",
                data={
                    "grant_type": "authorization_code",
                    "code": "authcode",
                    "code_verifier": "verifier123",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"


class TestTokenEndpointRefreshToken:
    def test_valid_refresh_token_returns_new_access_token(self):
        from catchup.auth.jwt import create_refresh_token

        token = create_refresh_token(
            {"sub": "user-123", "email": "user@example.com", "name": "Test"}
        )
        response = client.post(
            f"{_BASE}/token",
            data={"grant_type": "refresh_token", "refresh_token": token},
        )

        assert response.status_code == 200
        assert "access_token" in response.json()

    def test_invalid_refresh_token_returns_401(self):
        response = client.post(
            f"{_BASE}/token",
            data={
                "grant_type": "refresh_token",
                "refresh_token": "invalid-token",
            },
        )

        assert response.status_code == 401


class TestTokenEndpointUnsupportedGrant:
    def test_unknown_grant_type_returns_400(self):
        response = client.post(
            f"{_BASE}/token",
            data={"grant_type": "client_credentials"},
        )

        assert response.status_code == 400
