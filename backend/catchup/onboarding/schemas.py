from pydantic import BaseModel, ConfigDict

from catchup.db.models import JobLevel


class UserSignUpRequest(BaseModel):
    department: str
    job_level: JobLevel
    job_role: str


class UserSignUpSchema(BaseModel):
    okta_uid: str
    email: str
    name: str
    department: str
    job_level: JobLevel
    job_role: str


class UserSignUpResponse(BaseModel):
    id: int
    email: str
    name: str
    department: str
    job_level: str
    job_role: str
    provider: str
    
    model_config = ConfigDict(from_attributes=True)