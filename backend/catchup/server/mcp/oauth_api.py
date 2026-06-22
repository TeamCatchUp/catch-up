import json
import uuid
from urllib.parse import urlencode

import httpx
import structlog
from fastapi import APIRouter
from fastapi import Form
from fastapi import HTTPException
from fastapi import Request
from fastapi import status
from fastapi.responses import RedirectResponse
from starlette.responses import Response

from catchup.auth.endpoints import KeycloakOAuthEndpoint
from catchup.auth.jwt import create_access_token
from catchup.auth.jwt import create_refresh_token
from catchup.auth.jwt import verify_token
from catchup.components.auth.constants import OAuthIdentityProviderType
from catchup.components.auth.provider import OAuthIdentityProvider
from catchup.configs.config import auth_settings
from catchup.configs.config import settings
from catchup.server.mcp.schemas import DCRRequest
from catchup.server.mcp.schemas import DCRResponse
from catchup.server.mcp.schemas import OAuthAuthorizationServerMetadata
from catchup.server.mcp.schemas import TokenResponse
from catchup.utils.redis import get_redis_client

logger = structlog.get_logger()

# RFC 8414 + RFC 9728: 루트 well-known 엔드포인트 (nginx에서 백엔드로 라우팅됨)
well_known_router = APIRouter(tags=["MCP OAuth"])

router = APIRouter(prefix="/api/v1/mcp", tags=["MCP OAuth"])

_MCP_CLIENT_PREFIX = "mcp:client:"
_MCP_STATE_PREFIX = "mcp:state:"
_CLIENT_TTL = 60 * 60 * 24 * 30  # 30일
_STATE_TTL = 60 * 10  # 10분
_MCP_SCOPES: list[str] = ["openid", "email", "profile"]


def _server_base(request: Request) -> str:
    """X-Forwarded-Proto를 우선 참조해 public origin URL을 반환한다."""
    proto = request.headers.get("x-forwarded-proto", "")
    host = request.headers.get("host", request.url.netloc)
    if proto:
        return f"{proto}://{host}"
    return str(request.base_url).rstrip("/")


def _kc_auth_base() -> str:
    """Keycloak realm 인증 base URL을 반환한다."""
    return (
        f"{auth_settings.KC_PUBLIC_URL}"
        f"/realms/{auth_settings.KC_REALM}"
        f"/protocol/openid-connect"
    )


def _mcp_callback_uri(request: Request) -> str:
    """MCP OAuth 콜백 URI를 반환한다."""
    return f"{_server_base(request)}/api/v1/mcp/oauth/callback"


async def _build_as_metadata(
    request: Request,
) -> OAuthAuthorizationServerMetadata:
    """AS 메타데이터를 구성한다."""
    if not settings.MCP_OAUTH_ENABLED:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    base = _server_base(request)
    issuer = f"{base}/api/v1/mcp"
    return OAuthAuthorizationServerMetadata(
        issuer=issuer,
        authorization_endpoint=f"{base}/api/v1/mcp/oauth/authorize",
        token_endpoint=f"{base}/api/v1/mcp/oauth/token",
        registration_endpoint=f"{base}/api/v1/mcp/oauth/register",
        scopes_supported=_MCP_SCOPES,
        response_types_supported=["code"],
        grant_types_supported=["authorization_code", "refresh_token"],
        code_challenge_methods_supported=["S256"],
        token_endpoint_auth_methods_supported=["none"],
        jwks_uri=f"{base}/api/v1/mcp/oauth/jwks",
        subject_types_supported=["public"],
        id_token_signing_alg_values_supported=["RS256"],
    )


@router.get(
    path="/.well-known/openid-configuration",
    response_model=OAuthAuthorizationServerMetadata,
    description="OpenID Connect 디스커버리 문서를 반환한다. AS 메타데이터와 동일하다.",
)
@router.get(
    path="/.well-known/oauth-authorization-server",
    response_model=OAuthAuthorizationServerMetadata,
    description="RFC 8414 Authorization Server 메타데이터를 반환한다.",
)
async def oauth_authorization_server_metadata(
    request: Request,
) -> OAuthAuthorizationServerMetadata:
    """MCP OAuth 2.1 AS 메타데이터를 반환한다."""
    return await _build_as_metadata(request)


@well_known_router.get(
    path="/.well-known/oauth-authorization-server",
    response_model=OAuthAuthorizationServerMetadata,
    description="RFC 8414 root AS 메타데이터 — Claude fallback 탐색 경로.",
)
async def root_oauth_authorization_server_metadata(
    request: Request,
) -> OAuthAuthorizationServerMetadata:
    """루트 경로 AS 메타데이터를 반환한다. Claude의 fallback 탐색 경로."""
    return await _build_as_metadata(request)


@well_known_router.get(
    path="/.well-known/oauth-protected-resource",
    description="RFC 9728 Protected Resource 메타데이터를 반환한다.",
)
@well_known_router.get(
    path="/.well-known/oauth-protected-resource/{path:path}",
    description="RFC 9728 Protected Resource 메타데이터 (경로 기반 변형).",
)
async def oauth_protected_resource_metadata(request: Request) -> dict:
    """RFC 9728 Protected Resource 메타데이터를 반환한다.

    Claude가 authorization_servers 필드로 AS 메타데이터를 탐색한다.
    """
    if not settings.MCP_OAUTH_ENABLED:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    base = _server_base(request)
    resource = f"{base}/api/v1/mcp"
    return {
        "resource": resource,
        "authorization_servers": [resource],
        "scopes_supported": _MCP_SCOPES,
        "bearer_methods_supported": ["header"],
    }


@router.get(
    path="/oauth/jwks",
    description="JWKS 엔드포인트. mcp-remote Zod 검증 호환용 더미 응답을 반환한다.",
)
async def jwks() -> dict:
    """JSON Web Key Set을 반환한다. CatchUp은 HS256 대칭키를 사용하므로 keys는 비어있다."""
    if not settings.MCP_OAUTH_ENABLED:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return {"keys": []}


@router.post(
    path="/oauth/register",
    response_model=DCRResponse,
    status_code=status.HTTP_201_CREATED,
    description="RFC 7591 Dynamic Client Registration. CatchUp 자체 client_id를 발급한다.",
)
async def register_client(body: DCRRequest) -> DCRResponse:
    """MCP 클라이언트를 등록하고 CatchUp 자체 client_id를 발급한다."""
    if not settings.MCP_OAUTH_ENABLED:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    client_id = f"mcp-{uuid.uuid4().hex[:16]}"
    payload = {
        "client_id": client_id,
        "redirect_uris": body.redirect_uris,
        "client_name": body.client_name or "MCP Client",
    }
    redis = await get_redis_client()
    await redis.setex(
        f"{_MCP_CLIENT_PREFIX}{client_id}",
        _CLIENT_TTL,
        json.dumps(payload),
    )
    logger.info("mcp_client_registered", client_id=client_id)
    return DCRResponse(
        client_id=client_id,
        client_name=payload["client_name"],
        redirect_uris=body.redirect_uris,
        token_endpoint_auth_method="none",
        grant_types=["authorization_code", "refresh_token"],
        response_types=["code"],
    )


@router.get(
    path="/oauth/authorize",
    description="OAuth 2.1 인증 엔드포인트. KC 로그인 화면으로 프록시한다.",
)
async def authorize(
    request: Request,
    client_id: str,
    redirect_uri: str,
    state: str,
    code_challenge: str,
    code_challenge_method: str = "S256",
    response_type: str = "code",
    scope: str = "openid email profile",
) -> Response:
    """client_id를 검증하고 KC 인증 화면으로 리다이렉트한다."""
    if not settings.MCP_OAUTH_ENABLED:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    redis = await get_redis_client()
    raw = await redis.get(f"{_MCP_CLIENT_PREFIX}{client_id}")
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="등록되지 않은 client_id입니다.",
        )

    internal_state = uuid.uuid4().hex
    await redis.setex(
        f"{_MCP_STATE_PREFIX}{internal_state}",
        _STATE_TTL,
        json.dumps({
            "original_redirect_uri": redirect_uri,
            "original_state": state,
        }),
    )

    kc_auth_url = (
        f"{_kc_auth_base()}/auth"
        f"?{urlencode({
            'client_id': auth_settings.KC_CLIENT_ID,
            'redirect_uri': _mcp_callback_uri(request),
            'response_type': 'code',
            'scope': scope,
            'state': internal_state,
            'code_challenge': code_challenge,
            'code_challenge_method': code_challenge_method,
        })}"
    )
    logger.info("mcp_authorize_redirect", client_id=client_id)
    return RedirectResponse(url=kc_auth_url, status_code=302)


@router.get(
    path="/oauth/callback",
    description="KC 인증 콜백. code를 원래 redirect_uri로 중계한다.",
)
async def oauth_callback(code: str, state: str) -> Response:
    """KC 콜백을 수신해 원래 Claude redirect_uri로 code를 전달한다."""
    redis = await get_redis_client()
    raw = await redis.getdel(f"{_MCP_STATE_PREFIX}{state}")
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="유효하지 않거나 만료된 state입니다.",
        )

    payload = json.loads(raw)

    target_url = (
        f"{payload['original_redirect_uri']}"
        f"?{urlencode({'code': code, 'state': payload['original_state']})}"
    )
    logger.info("mcp_callback_relayed")
    return RedirectResponse(url=target_url, status_code=302)


@router.post(
    path="/oauth/token",
    response_model=TokenResponse,
    description="OAuth 2.1 토큰 엔드포인트. authorization_code·refresh_token grant를 처리한다.",
)
async def token_endpoint(
    request: Request,
    grant_type: str = Form(...),
    code: str | None = Form(default=None),
    redirect_uri: str | None = Form(default=None),
    code_verifier: str | None = Form(default=None),
    refresh_token: str | None = Form(default=None),
) -> TokenResponse:
    """KC code를 교환하거나 refresh token으로 CatchUp JWT를 발급한다."""
    if not settings.MCP_OAUTH_ENABLED:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    if grant_type == "authorization_code":
        return await _handle_authorization_code(
            code=code,
            redirect_uri=_mcp_callback_uri(request),
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
    redirect_uri: str,
    code_verifier: str | None,
) -> TokenResponse:
    """KC code를 교환해 CatchUp JWT를 발급한다."""
    if not code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="code는 필수입니다.",
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
                scope=_MCP_SCOPES,
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
