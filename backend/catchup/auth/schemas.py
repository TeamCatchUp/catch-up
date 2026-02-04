from pydantic import BaseModel, EmailStr

from catchup.db.models import UserRole


class GoogleUserInfoResponse(BaseModel):
    email: EmailStr
    name: str
    given_name: str | None = None
    family_name: str | None = None
    picture: str | None = None
    provider_id: str


class UserCreate(BaseModel):
    email: EmailStr
    given_name: str | None = None
    family_name: str | None = None
    name: str
    picture: str | None = None
    provider: str = "google"
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
