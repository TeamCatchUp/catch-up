from pydantic import BaseModel


class BaseOAuthEndpoint(BaseModel):
    authentication_url: str
    token_url: str
    user_info_url: str


class KeycloakOAuthEndpoint(BaseOAuthEndpoint):
    @classmethod
    def from_settings(
        cls,
        public_base_url: str,
        internal_base_url: str,
        realm: str
    ) -> "KeycloakOAuthEndpoint":
        base_internal = f"{internal_base_url}/realms/{realm}/protocol/openid-connect"
        base_public = f"{public_base_url}/realms/{realm}/protocol/openid-connect"
        
        return cls(
            authentication_url=f"{base_public}/auth",
            token_url=f"{base_internal}/token",
            user_info_url=f"{base_internal}/userinfo"
        )


class GoogleOAuthEndpoint(BaseOAuthEndpoint):
    @classmethod
    def from_settings(cls) -> "GoogleOAuthEndpoint":
        return cls(
            authentication_url="https://accounts.google.com/o/oauth2/v2/auth",
            token_url="https://oauth2.googleapis.com/token",
            user_info_url="https://www.googleapis.com/oauth2/v3/userinfo"
        )