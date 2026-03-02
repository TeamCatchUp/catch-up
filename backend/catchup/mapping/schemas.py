from pydantic import BaseModel, ConfigDict


class OAuthUserSchema(BaseModel):
    sub: str
    email: str
    name: str
    status: str
    
    model_config = ConfigDict(from_attributes=True)