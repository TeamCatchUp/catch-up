from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from catchup.auth.dependencies import get_pending_signup_user
from catchup.db.dependencies import get_db
from catchup.onboarding.schemas import UserSignUpRequest, UserSignUpResponse, UserSignUpSchema
from catchup.onboarding.user import register_user_from_okta


router = APIRouter(
    prefix="/api/v1/onboarding",
    tags=["onboarding"]
)

@router.post(
    path="",
    response_model=UserSignUpResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Okta 유저 최초 회원가입 및 정보 매핑"
)
def signup_okta_user(
    payload: UserSignUpRequest,
    pending_user: dict = Depends(get_pending_signup_user),
    db: Session = Depends(get_db)
):

    signup_data = UserSignUpSchema(
        okta_uid=pending_user["okta_uid"],
        email=pending_user["email"],
        name=pending_user["name"],
        department=payload.department,
        job_level=payload.job_level,
        job_role=payload.job_role
    )
    
    new_user = register_user_from_okta(db, signup_data)

    return new_user
