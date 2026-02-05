from pydantic import BaseModel, EmailStr


class CurrentUserInfo(BaseModel):
    email: EmailStr
    name: str
    role: str


class TokenRefreshResponse(BaseModel):
    status: str
    detail: str
