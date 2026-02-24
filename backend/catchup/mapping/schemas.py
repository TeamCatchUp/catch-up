from pydantic import BaseModel


class OktaUser(BaseModel):
    sub: str
    email: str
    name: str
    status: str