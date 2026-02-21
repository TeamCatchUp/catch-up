from fastapi import HTTPException
from sqlalchemy.orm import Session
from catchup.db.models import Company, Workspace, User, UserRole, UserWorkspace
from catchup.db.users import get_okta_user_with_okta_uid
from catchup.onboarding.schemas import AdminSignUpSchema

def register_admin_from_okta(db: Session, data: AdminSignUpSchema) -> User:

    okta_record = get_okta_user_with_okta_uid(db, data.okta_uid)
    if not okta_record:
        raise HTTPException(status_code=404, detail="Okta 유저 정보가 존재하지 않습니다.")
    if okta_record.user_id:
        raise HTTPException(status_code=400, detail="이미 가입이 완료된 유저입니다.")

    try:
        # Company 생성
        new_company = Company(
            name=data.company_name,
            size=data.company_size
        )
        db.add(new_company)
        db.flush()

        # Workspace 생성
        new_workspace = Workspace(
            name=data.workspace_name,
            company_id=new_company.id
        )
        db.add(new_workspace)
        db.flush()
        
        # Admin 등록
        new_user = User(
            email=data.email,
            name=data.name,
            provider="okta",
            role=UserRole.ADMIN, 
            department=data.company_name,  # TODO: 예시고객사 PoC 한정
            job_level=data.job_level,
        )
        db.add(new_user)
        db.flush()

        # user-workspace 연관관계 매핑
        user_workspace = UserWorkspace(
            user_id=new_user.id,
            workspace_id=new_workspace.id
        )
        db.add(user_workspace)

        # OktaUser에 CatchUp user_id 업데이트
        okta_record.user_id = new_user.id

        db.commit()
        db.refresh(new_user)
        
        return new_user

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"어드민 가입 처리 중 오류가 발생했습니다: {str(e)}")