from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from catchup.auth.dependencies import get_current_user
from catchup.db.dependencies import get_db
from catchup.db.models import User

router = APIRouter(
    prefix="/api/v1/settings",
    tags=["settings"]
)

class PromptUpdate(BaseModel):
    custom_prompt: str | None

@router.get(
    path="/prompts",
    description="사용자 맞춤형 프롬프트 조회"
)
def get_custom_prompt(
    current_user: User = Depends(get_current_user)
):
    return {"custom_prompt": current_user.custom_prompt}


@router.patch(
    path="/prompts",
    description="사용자 맞춤형 프롬프트 수정"
)
def update_custom_prompt(
    payload: PromptUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    current_user.custom_prompt = payload.custom_prompt
    db.commit()
    
    return {"custom_prompt": current_user.custom_prompt}
