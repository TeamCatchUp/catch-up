from typing import Optional
from pydantic import BaseModel, EmailStr

from catchup.db.models import UserRole


class GoogleUserInfoResponse(BaseModel):
    email: EmailStr
    name: str
    given_name: Optional[str] = None
    family_name: Optional[str] = None
    picture: Optional[str] = None
    provider_id: str
    

# TODO: 공통 필드 추상화
class OktaUserInfoResponse(BaseModel):
    sub: str
    name: str
    email: EmailStr
    preferred_username: Optional[str] = None
    given_name: Optional[str] = None
    family_name: Optional[str] = None
    picture: Optional[str] = None

    @property
    def provider_id(self) -> str:
        return self.sub


class UserCreate(BaseModel):
    email: EmailStr
    given_name: Optional[str] = None
    family_name: Optional[str] = None
    name: Optional[str] = None
    picture: Optional[str] = None
    provider: str
    role: UserRole = UserRole.USER

    @classmethod
    def from_google_user(cls, google_user: GoogleUserInfoResponse) -> "UserCreate":
        return cls(
            email=google_user.email,
            name=google_user.name or "",
            picture=google_user.picture,
            given_name=google_user.given_name,
            family_name=google_user.family_name,
            provider="google",
            role=UserRole.USER,
        )
