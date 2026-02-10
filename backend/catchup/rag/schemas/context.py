from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime

from catchup.db.models import User

    
class GlobalUserContext(BaseModel):
    id: int = Field(..., description="DB 조회를 위한 고유 ID")
    name: str = Field(..., description="사용자 표시 이름")
    email: str = Field(..., description="이메일 (작성자 식별용)")
    # role: Optional[str] = Field(None, description="직군 (답변 난이도 조절용)")
    # team: Optional[str] = Field(None, description="소속 팀 (예: 'Payment Team') - 검색 범위 필터링용")
    
    @classmethod
    def from_db_user(cls, db_user: User):
        return cls(
            id=db_user.id,
            name=db_user.name,
            email=db_user.email
        )


class GlobalCompanyContext(BaseModel):
    name: str
    description: str
    

class GlobalContext(BaseModel):
    user: GlobalUserContext
    #  조직 및 비즈니스 맥락
    company: Optional[GlobalCompanyContext] = None
    # 상대적 시간 표현을 해석하기 위한 기준점 ('오늘', '어제' 등)
    current_time: str = Field(
        default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M (%A)")
    )
    
    
    # TODO: (임시) 현재 활성화된 주요 프로젝트 목록 (Router/Rewrite가 고유명사를 인식하도록 도움)
    # active_projects: List[str] = Field(default_factory=list, description="현재 진행 중인 프로젝트명 목록 (예: ['NexList', 'PayOne'])")

    # --- TODO: 열람 권한 관련 ---
    # allowed_datasources: list[str] = Field(
    #     default_factory=lambda: ["jira", "wiki", "slack"], 
    #     description="접근 권한이 있는 데이터 소스"
    # )