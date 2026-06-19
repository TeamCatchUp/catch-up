import httpx
import structlog
from fastapi import APIRouter
from fastapi import Form
from fastapi import HTTPException
from fastapi import Request
from fastapi import status

from catchup.auth.endpoints import KeycloakOAuthEndpoint
from catchup.auth.jwt import create_access_token
from catchup.auth.jwt import create_refresh_token
from catchup.auth.jwt import verify_token
from catchup.components.auth.constants import OAuthIdentityProviderType
from catchup.components.auth.provider import OAuthIdentityProvider
from catchup.configs.config import auth_settings
from catchup.configs.config import settings
from catchup.server.mcp.schemas import OAuthAuthorizationServerMetadata
from catchup.server.mcp.schemas import TokenResponse

logger = structlog.get_logger()

router = APIRouter(tags=["MCP OAuth"])


@router.get(
    path="/.well-known/oauth-authorization-server",
    response_model=OAuthAuthorizationServerMetadata,
    description="MCP OAuth 2.1 Authorization Server 메타데이터를 반환한다.",
)
async def oauth_authorization_server_metadata(
    request: Request,
) -> OAuthAuthorizationServerMetadata:
    """RFC 8414 Authorization Server Metadata를 반환한다."""
    if not settings.MCP_OAUTH_ENABLED:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    kc_base = (
        f"{auth_settings.KC_PUBLIC_URL}"
        f"/realms/{auth_settings.KC_REALM}"
    )
    server_base = str(request.base_url).rstrip("/")

    return OAuthAuthorizationServerMetadata(
        issuer=server_base,
        authorization_endpoint=(
            f"{kc_base}/protocol/openid-connect/auth"
        ),
        token_endpoint=f"{server_base}/oauth/token",
        scopes_supported=["openid", "email", "profile"],
        response_types_supported=["code"],
        grant_types_supported=["authorization_code", "refresh_token"],
        code_challenge_methods_supported=["S256"],
        token_endpoint_auth_methods_supported=[
            "client_secret_post",
            "none",
        ],
    )


@router.post(
    path="/oauth/token",
    response_model=TokenResponse,
    description="OAuth 2.1 토큰 엔드포인트. authorization_code·refresh_token grant를 처리한다.",
)
async def token_endpoint(
    grant_type: str = Form(...),
    code: str | None = Form(default=None),
    redirect_uri: str | None = Form(default=None),
    code_verifier: str | None = Form(default=None),
    refresh_token: str | None = Form(default=None),
) -> TokenResponse:
    """Keycloak code를 교환하거나 refresh token으로 CatchUp JWT를 발급한다."""
    if not settings.MCP_OAUTH_ENABLED:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    if grant_type == "authorization_code":
        return await _handle_authorization_code(
            code=code,
            redirect_uri=redirect_uri,
            code_verifier=code_verifier,
        )

    if grant_type == "refresh_token":
        return _handle_refresh_token(refresh_token)

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"지원하지 않는 grant_type: {grant_type}",
    )


async def _handle_authorization_code(
    code: str | None,
    redirect_uri: str | None,
    code_verifier: str | None,
) -> TokenResponse:
    """Keycloak code를 교환해 CatchUp JWT를 발급한다."""
    if not code or not redirect_uri:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="code와 redirect_uri는 필수입니다.",
        )
    if not code_verifier:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="PKCE code_verifier는 필수입니다.",
        )

    endpoint = KeycloakOAuthEndpoint.from_settings(
        public_base_url=auth_settings.KC_PUBLIC_URL,
        internal_base_url=auth_settings.KC_INTERNAL_URL,
        realm=auth_settings.KC_REALM,
    )
    try:
        async with httpx.AsyncClient() as http_client:
            provider = OAuthIdentityProvider(
                client=http_client,
                endpoint=endpoint,
                provider_type=OAuthIdentityProviderType.KEYCLOAK,
                client_id=auth_settings.KC_CLIENT_ID,
                client_secret=auth_settings.KC_CLIENT_SECRET,
                redirect_uri=redirect_uri,
                scope=["openid", "email", "profile"],
                state="",
            )
            oauth_user = await provider.get_oauth_user_info(
                code=code,
                redirect_uri=redirect_uri,
                code_verifier=code_verifier,
            )
    except Exception as exc:
        logger.warning("mcp_token_exchange_failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Keycloak 인증에 실패했습니다.",
        )

    token_data = {
        "sub": oauth_user.sub,
        "email": oauth_user.email,
        "name": oauth_user.name,
    }
    logger.info("mcp_token_issued", sub=oauth_user.sub)
    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
        token_type="bearer",
        expires_in=auth_settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


def _handle_refresh_token(refresh_token: str | None) -> TokenResponse:
    """CatchUp refresh token으로 새 access token을 발급한다."""
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="refresh_token이 없습니다.",
        )
    try:
        payload = verify_token(refresh_token, "refresh")
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("mcp_refresh_failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유효하지 않은 refresh token입니다.",
        )

    token_data = {
        "sub": payload["sub"],
        "email": payload.get("email"),
        "name": payload.get("name"),
    }
    logger.info("mcp_token_refreshed", sub=payload["sub"])
    return TokenResponse(
        access_token=create_access_token(token_data),
        token_type="bearer",
        expires_in=auth_settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
