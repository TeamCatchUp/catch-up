from fastapi import HTTPException
from sqlalchemy.orm import Session

from catchup.db.models import User, UserSourceMapping, UserStatus
from catchup.db.user_source_mapping import get_pending_source_premappings
from catchup.db.users import get_okta_user_with_okta_uid
from catchup.db.workspaces import add_user_to_workspace, get_workspace_by_id
from catchup.onboarding.schemas import UserSignUpRequest


def register_user_from_okta(
    db: Session,
    payload: UserSignUpRequest
):
    okta_record = get_okta_user_with_okta_uid(db, payload.okta_uid)
    
    if not okta_record:
        raise HTTPException(status_code=404, detail="어드민에 의해 등록된 Okta 유저가 아닙니다.")
    
    if okta_record.user_id is not None:
        raise HTTPException(status_code=400, detail="이미 가입이 완료된 유저입니다.")
    
    new_user = User(
        email=payload.email,
        name=payload.name,
        provider="okta",
        department=payload.department,
        job_level=payload.job_level,
        status=UserStatus.ACTIVE
    )
    
    db.add(new_user)
    db.flush()
    
    okta_record.user_id = new_user.id
    
    workspace = get_workspace_by_id(db, 1)  # TODO: PoC 한정 workspace id = 1 고정
    add_user_to_workspace(db, new_user, workspace)
    
    resolve_pending_source_mappings(db, new_user)
        
    db.commit()
    db.refresh(new_user)
    
    return new_user


def resolve_pending_source_mappings(db: Session, user: User):
    """
    회원가입 시점에 PreMappingBuffer를 조회해서 대기 중인 외부 툴 데이터를 
    실제 유저 매핑(UserSourceMapping)으로 연결한다.
    """
    
    pending_buffers = get_pending_source_premappings(db, user.email)
    
    for buffer in pending_buffers:
        new_mapping = UserSourceMapping(
            user_id=user.id,
            source_type=buffer.source_type,
            external_user_identifier=buffer.external_user_identifier
        )
        db.add(new_mapping)
        
        buffer.is_registered = True