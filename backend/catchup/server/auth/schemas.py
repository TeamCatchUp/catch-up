from pydantic import BaseModel, EmailStr

from catchup.db.models import UserStatus


class CurrentUserInfo(BaseModel):
    email: EmailStr
    name: str
    role: str
    status: UserStatus

class CurrentUserProfile(BaseModel):
    name: str
    email: EmailStr
    picture: str
    department: str
    job_level: str

    


class TokenRefreshResponse(BaseModel):
    status: str
    detail: str
