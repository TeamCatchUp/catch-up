from pydantic import BaseModel


class OAuthAuthorizationServerMetadata(BaseModel):
    """RFC 8414 OAuth 2.0 Authorization Server Metadata."""

    issuer: str
    authorization_endpoint: str
    token_endpoint: str
    scopes_supported: list[str]
    response_types_supported: list[str]
    grant_types_supported: list[str]
    code_challenge_methods_supported: list[str]
    token_endpoint_auth_methods_supported: list[str]


class TokenResponse(BaseModel):
    """OAuth 2.1 토큰 응답."""

    access_token: str
    token_type: str
    expires_in: int
    refresh_token: str | None = None
