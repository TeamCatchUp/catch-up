from datetime import datetime
from typing import Optional

import pytz
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field


class GlobalUserContext(BaseModel):
    id: int = Field(..., description="DB 조회를 위한 고유 ID")
    name: str = Field(..., description="사용자 표시 이름")
    email: str = Field(..., description="이메일 (작성자 식별용)")
    department: str = Field(..., description="사용자 부서")

    model_config = ConfigDict(from_attributes=True)


class GlobalCompanyContext(BaseModel):
    id: int = Field(..., description="DB 조회를 위한 고유 ID")
    name: str = Field(..., description="회사 이름")
    description: Optional[str] = Field(default="", description="조직 설명")
    
    model_config = ConfigDict(from_attributes=True)


class GlobalWorkspaceContext(BaseModel):
    id: int = Field(..., description="DB 조회를 위한 고유 ID")
    name: str = Field(..., description="워크스페이스 이름")
    
    model_config = ConfigDict(from_attributes=True)
    
    
class GlobalCurrentTimeContext(BaseModel):
    kst: str = Field(
        default_factory=lambda: datetime.now(pytz.timezone("Asia/Seoul")).strftime("%Y-%m-%d %H:%M (%A)"),
        description="KST"
    )
    
    utc: str = Field(
        default_factory=lambda: datetime.now(pytz.UTC).isoformat(),
        description="UTC"
    )


class GlobalContext(BaseModel):
    user: GlobalUserContext = Field(..., description="사용자 정보")
    workspace: GlobalWorkspaceContext = Field(..., description="워크스페이스 정보")
    company: GlobalCompanyContext = Field(..., description="조직 및 비즈니스 맥락")
    current_time: GlobalCurrentTimeContext = Field(
            default_factory=GlobalCurrentTimeContext, 
            description="현재 시각(kst, utc)"
        )
