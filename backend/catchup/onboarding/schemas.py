from pydantic import BaseModel, ConfigDict

from catchup.db.models import CompanySize, JobLevel


# External
class BaseSignUpRequest(BaseModel):
    job_level: JobLevel


class UserSignUpRequest(BaseSignUpRequest):
    department: str
    pass
    

class AdminSignUpRequest(BaseSignUpRequest):
    company_name: str
    company_size: CompanySize
    workspace_name: str


class SignUpResponse(BaseModel):
    id: int
    email: str
    name: str
    department: str
    job_level: str
    provider: str
    
    model_config = ConfigDict(from_attributes=True)


# Internal
class BaseSignUpSchema(BaseModel):
    okta_uid: str
    email: str
    name: str
    job_level: JobLevel


class UserSignUpSchema(BaseSignUpSchema):
    department: str
    pass


class AdminSignUpSchema(BaseSignUpSchema):
    company_name: str
    company_size: CompanySize
    workspace_name: str
