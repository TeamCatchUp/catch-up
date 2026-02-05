import httpx
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from catchup.auth.schemas import GoogleUserInfoResponse, UserCreate
from catchup.configs.config import auth_settings
from catchup.db.models import User
from catchup.db.users import create_new_user, get_user_by_email


class GoogleOAuthService:
    TOKEN_URL = "https://oauth2.googleapis.com/token"
    USER_INFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"

    async def get_google_user(self, code: str) -> GoogleUserInfoResponse:
        async with httpx.AsyncClient() as client:
            access_token = await self._get_access_token(client, code)
            return await self._fetch_user_info(client, access_token)

    async def _get_access_token(self, client: httpx.AsyncClient, code: str) -> str:
        response = await client.post(
            self.TOKEN_URL,
            data={
                "code": code,
                "client_id": auth_settings.GOOGLE_CLIENT_ID,
                "client_secret": auth_settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri": auth_settings.GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
            },
        )

        if response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="유효하지 않은 Google Code입니다.",
            )

        return response.json().get("access_token")

    async def _fetch_user_info(
        self, client: httpx.AsyncClient, access_token: str
    ) -> GoogleUserInfoResponse:
        response = await client.get(
            self.USER_INFO_URL, headers={"Authorization": f"Bearer {access_token}"}
        )

        if response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Google 사용자 정보를 가져오지 못했습니다.",
            )

        data = response.json()

        return GoogleUserInfoResponse(
            email=data["email"],
            name=data.get("name"),
            picture=data.get("picture"),
            given_name=data.get("given_name"),
            family_name=data.get("family_name"),
            provider_id=data["sub"],
        )

    def get_or_register_google_user(
        self, db: Session, google_user: GoogleUserInfoResponse
    ) -> User:
        existing_user = get_user_by_email(db, google_user.email)

        if existing_user:
            return existing_user

        new_user_data = UserCreate.from_google_user(google_user)

        return create_new_user(db, new_user_data)
