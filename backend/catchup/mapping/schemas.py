from pydantic import BaseModel


class OktaUser(BaseModel):
    okta_uid: str
    email: str
    name: str
    status: str