from fastapi import HTTPException
from sqlalchemy.orm import Session
from catchup.db.models import Company, UserStatus, Workspace, User, UserRole, UserWorkspace
from catchup.db.users import get_oauth_user_with_sub
from catchup.onboarding.schemas import AdminSignUpSchema

def register_admin_from_oauth(db: Session, data: AdminSignUpSchema) -> User:

    oauth_user_record = get_oauth_user_with_sub(db, data.sub)
    if not oauth_user_record:
        raise HTTPException(status_code=404, detail="Oauth 유저 정보가 존재하지 않습니다.")
    if oauth_user_record.user_id:
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
            provider="keycloak",
            role=UserRole.ADMIN, 
            department=data.company_name,  # TODO: 예시고객사 PoC 한정
            job_level=data.job_level,
            status=UserStatus.ACTIVE
        )
        db.add(new_user)
        db.flush()

        # user-workspace 연관관계 매핑
        user_workspace = UserWorkspace(
            user_id=new_user.id,
            workspace_id=new_workspace.id
        )
        db.add(user_workspace)

        # OAuthUser CatchUp user_id 업데이트
        oauth_user_record.user_id = new_user.id

        db.commit()
        db.refresh(new_user)
        
        return new_user

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"어드민 가입 처리 중 오류가 발생했습니다: {str(e)}")