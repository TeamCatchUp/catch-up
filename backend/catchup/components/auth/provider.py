import logging
from urllib.parse import urlencode
from httpx import AsyncClient

from catchup.auth.endpoints import BaseOAuthEndpoint
from catchup.auth.exceptions import OAuthError
from catchup.auth.schemas import BaseOAuthUserInfoResponse

logger = logging.getLogger(__name__)


class OAuthIdentityProvider:

    def __init__(
        self,
        *,
        client: AsyncClient,
        endpoint: BaseOAuthEndpoint,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        scope: list[str],
        state: str,
    ):
        self.client = client
        self.endpoint = endpoint
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.scope = " ".join(scope)
        self.state = state

    def get_authentication_url(self) -> str:
        """[공통] OAuth IDP 로그인 화면 리다이렉트 URI 반환"""

        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": self.scope,
            "state": self.state,
        }

        return f"{self.endpoint.authentication_url}?{urlencode(params)}"

    async def _get_access_token(self, code: str) -> str:
        """[공통] access token 획득"""

        response = await self.client.post(
            self.endpoint.token_url,
            data={
                "grant_type": "authorization_code",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "code": code,
                "redirect_uri": self.redirect_uri,
                "scope": self.scope,
            },
        )

        if response.status_code != 200:
            logger.error(
                f"[{self.__class__.__name__}] Error while acquiring token: {response.text}"
            )
            raise OAuthError(
                message="인증 토큰을 획득하지 못했습니다.", details=response.text
            )

        return response.json().get("access_token")

    async def _fetch_raw_user_info(self, access_token: str) -> dict:
        """표준 Bearer 토큰 방식을 이용한 유저 정보 획득"""

        response = await self.client.get(
            self.endpoint.user_info_url,
            headers={"Authorization": f"Bearer {access_token}"},
        )

        if response.status_code != 200:
            logger.error(
                f"[{self.__class__.__name__}] Error while fetching raw user info: {response.text}"
            )
            raise OAuthError(
                message="OAuth 사용자 정보 획득에 실패했습니다.", details=response.text
            )
        
        return response.json()

    async def get_oauth_user_info(
        self,
        code: str
    ) -> BaseOAuthUserInfoResponse:
        """가공된 유저 정보 반환"""
        
        token = await self._get_access_token(code)
        raw_user_data = await self._fetch_raw_user_info(token)
        
        return BaseOAuthUserInfoResponse(**raw_user_data)
