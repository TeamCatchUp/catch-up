from typing import Optional
from pydantic import BaseModel, ConfigDict

from catchup.db.models import CompanySize, JobLevel


# External
class BaseSignUpRequest(BaseModel):
    name: str  # 온보딩 화면에서 입력한 이름
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
    

# Pre-mapped 계정 정보
class CandidateItem(BaseModel):
    external_id: str
    full_name: str
    display_name: str
    email: str
    picture: Optional[str]


class MappingCandidates(BaseModel):
    source_type: str
    candidates: Optional[list[CandidateItem]]


# Internal
class BaseSignUpSchema(BaseModel):
    sub: str
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
