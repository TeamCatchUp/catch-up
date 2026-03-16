from pydantic import BaseModel, ConfigDict, model_validator


class OAuthUserSchema(BaseModel):
    sub: str
    email: str
    name: str
    status: str
    
    model_config = ConfigDict(from_attributes=True)