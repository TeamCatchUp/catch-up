from pydantic import BaseModel


class OAuthUserSchema(BaseModel):
    sub: str
    email: str
    name: str
    status: str