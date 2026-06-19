from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from catchup.server.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def enable_mcp_oauth(monkeypatch):
    from catchup.configs.config import settings

    monkeypatch.setattr(settings, "MCP_OAUTH_ENABLED", True)


class TestOAuthAuthorizationServerMetadata:
    def test_returns_metadata_when_enabled(self):
        response = client.get("/.well-known/oauth-authorization-server")

        assert response.status_code == 200
        data = response.json()
        assert "issuer" in data
        assert "authorization_endpoint" in data
        assert data["token_endpoint"].endswith("/oauth/token")
        assert "S256" in data["code_challenge_methods_supported"]
        assert "authorization_code" in data["grant_types_supported"]
        assert "refresh_token" in data["grant_types_supported"]

    def test_returns_404_when_disabled(self, monkeypatch):
        from catchup.configs.config import settings

        monkeypatch.setattr(settings, "MCP_OAUTH_ENABLED", False)
        response = client.get("/.well-known/oauth-authorization-server")

        assert response.status_code == 404


class TestTokenEndpointAuthorizationCode:
    def test_missing_code_returns_400(self):
        response = client.post(
            "/oauth/token",
            data={
                "grant_type": "authorization_code",
                "redirect_uri": "claude://callback",
                "code_verifier": "verifier123",
            },
        )

        assert response.status_code == 400
        assert "code" in response.json()["detail"]

    def test_missing_code_verifier_returns_400(self):
        response = client.post(
            "/oauth/token",
            data={
                "grant_type": "authorization_code",
                "code": "authcode",
                "redirect_uri": "claude://callback",
            },
        )

        assert response.status_code == 400
        assert "code_verifier" in response.json()["detail"]

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
                "/oauth/token",
                data={
                    "grant_type": "authorization_code",
                    "code": "authcode",
                    "redirect_uri": "claude://callback",
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
                "/oauth/token",
                data={
                    "grant_type": "authorization_code",
                    "code": "authcode",
                    "redirect_uri": "claude://callback",
                    "code_verifier": "verifier123",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert data["expires_in"] > 0


class TestTokenEndpointRefreshToken:
    def test_missing_refresh_token_returns_400(self):
        response = client.post(
            "/oauth/token",
            data={"grant_type": "refresh_token"},
        )

        assert response.status_code == 400

    def test_invalid_refresh_token_returns_401(self):
        response = client.post(
            "/oauth/token",
            data={
                "grant_type": "refresh_token",
                "refresh_token": "invalid-token",
            },
        )

        assert response.status_code == 401

    def test_valid_refresh_token_returns_new_access_token(self):
        from catchup.auth.jwt import create_refresh_token

        token = create_refresh_token(
            {"sub": "user-123", "email": "user@example.com", "name": "Test"}
        )
        response = client.post(
            "/oauth/token",
            data={
                "grant_type": "refresh_token",
                "refresh_token": token,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert "refresh_token" not in data or data["refresh_token"] is None


class TestTokenEndpointUnsupportedGrant:
    def test_unknown_grant_type_returns_400(self):
        response = client.post(
            "/oauth/token",
            data={"grant_type": "client_credentials"},
        )

        assert response.status_code == 400
        assert "grant_type" in response.json()["detail"]
