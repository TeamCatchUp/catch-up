from typing import Optional
from pydantic import BaseModel, EmailStr

# OIDC 표준 스키마
class BaseOAuthUserInfoResponse(BaseModel):
    sub: str
    email: EmailStr
    name: str
    picture: Optional[str] = None

    @property
    def unique_id(self) -> str:
        return self.sub

class KeycloakUserInfoResponse(BaseOAuthUserInfoResponse):
    pass

class GoogleUserInfoResponse(BaseOAuthUserInfoResponse):
    given_name: Optional[str] = None
    family_name: Optional[str] = None