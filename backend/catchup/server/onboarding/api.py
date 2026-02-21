from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from catchup.auth.dependencies import get_pending_signup_user
from catchup.db.dependencies import get_db
from catchup.onboarding.admin import register_admin_from_okta
from catchup.onboarding.schemas import AdminSignUpRequest, AdminSignUpSchema, UserSignUpRequest, SignUpResponse, UserSignUpSchema
from catchup.onboarding.user import register_user_from_okta


router = APIRouter(
    prefix="/api/v1/onboarding",
    tags=["onboarding"]
)

@router.post(
    path="",
    response_model=SignUpResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Okta 유저 최초 회원가입 및 정보 매핑",
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
    )
    
    new_user = register_user_from_okta(db, signup_data)

    return new_user


@router.post(
    path="/admin",
    response_model=SignUpResponse,
    status_code=status.HTTP_201_CREATED,
    summary="루트 어드민 온보딩",
    description="루트 어드민이 회사를 등록하고 워크스페이스를 생성한다."
)
def signup_root_admin(
    payload: AdminSignUpRequest,
    pending_user: dict = Depends(get_pending_signup_user),
    db: Session = Depends(get_db)
):
    admin_data = AdminSignUpSchema(
        okta_uid=pending_user["okta_uid"],
        email=pending_user["email"],
        name=pending_user["name"],
        job_level=payload.job_level,
        company_name=payload.company_name,
        company_size=payload.company_size,
        workspace_name=payload.workspace_name
    )
    
    new_admin = register_admin_from_okta(db, admin_data)
    
    return new_admin