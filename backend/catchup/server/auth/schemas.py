from pydantic import BaseModel, EmailStr

from catchup.db.models import UserStatus


class CurrentUserInfo(BaseModel):
    email: EmailStr
    name: str
    role: str
    status: UserStatus


class TokenRefreshResponse(BaseModel):
    status: str
    detail: str
