from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime

import pytz

from catchup.db.models import Company, User

    
class GlobalUserContext(BaseModel):
    id: int = Field(..., description="DB 조회를 위한 고유 ID")
    name: str = Field(..., description="사용자 표시 이름")
    email: str = Field(..., description="이메일 (작성자 식별용)")
    # jobtitle : Optional[str] = Field(None, description="직군")
    # team: Optional[str] = Field(None, description="소속 팀")
    
    @classmethod
    def from_db_user(cls, db_user: User):
        return cls(
            id=db_user.id,
            name=db_user.name,
            email=db_user.email
        )


class GlobalCompanyContext(BaseModel):
    id: int = Field(..., description="DB 조회를 위한 고유 ID")
    name: str = Field(..., description="회사 이름")
    description: Optional[str] = Field(default="", description="조직 설명")
    
    @classmethod
    def from_db_company(cls, db_company: Company):
        return cls(
            id=db_company.id,
            name=db_company.name,
            description=db_company.description
        )
    
class GlobalWorkspaceContext(BaseModel):
    id: int = Field(..., description="DB 조회를 위한 고유 ID")
    name: str = Field(..., description="워크스페이스 이름")


class GlobalContext(BaseModel):
    user: GlobalUserContext = Field(..., description="사용자 정보")
    workspace: GlobalWorkspaceContext = Field(..., description="워크스페이스 정보")
    company: GlobalCompanyContext = Field(..., description="조직 및 비즈니스 맥락")
    current_time: str = Field(
        default_factory=lambda: datetime.now(pytz.timezone("Asia/Seoul")).strftime("%Y-%m-%d %H:%M (%A)")
    )