import uuid
from httpx import AsyncClient

from catchup.auth.endpoints import GoogleOAuthEndpoint, KeycloakOAuthEndpoint
from catchup.components.auth.provider import OAuthIdentityProvider
from catchup.components.auth.constants import OAuthIdentityProviderType
from catchup.configs.config import auth_settings


def get_oauth_identity_provider(
    *,
    provider_type: OAuthIdentityProviderType,
    client: AsyncClient
) -> OAuthIdentityProvider:

    dynamic_state = f"{provider_type.value}:{uuid.uuid4().hex}"
    
    if provider_type == OAuthIdentityProviderType.KEYCLOAK:
        endpoint = KeycloakOAuthEndpoint.from_settings(
            public_base_url=auth_settings.KC_PUBLIC_URL,
            internal_base_url=auth_settings.KC_INTERNAL_URL,
            realm=auth_settings.KC_REALM            
        )
        provider_params = {
            "endpoint": endpoint,
            "client_id": auth_settings.KC_CLIENT_ID,
            "client_secret": auth_settings.KC_CLIENT_SECRET,
            "redirect_uri": auth_settings.KC_REDIRECT_URI,
            "scope": ["openid", "email", "profile", "offline_access"],
        }
    
    elif provider_type == OAuthIdentityProviderType.GOOGLE:
        provider_params = {
            "endpoint": GoogleOAuthEndpoint.from_settings(),
            "client_id": auth_settings.GOOGLE_CLIENT_ID,
            "client_secret": auth_settings.GOOGLE_CLIENT_SECRET,
            "redirect_uri": auth_settings.GOOGLE_REDIRECT_URI,
            "scope": ["openid", "email", "profile"],
        }
    
    else:
        raise ValueError(f"지원되지 않는 OAuth 인증 제공자입니다: {provider_type}")

    return OAuthIdentityProvider(
        client=client,
        state=dynamic_state,
        **provider_params
    )