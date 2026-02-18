from fastapi import Depends, HTTPException, status, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from catchup.auth.jwt import verify_token
from catchup.db.dependencies import get_db
from catchup.db.models import User
from catchup.db.users import get_user_by_email


security_scheme = HTTPBearer()

def get_current_user(
    auth: HTTPAuthorizationCredentials = Depends(security_scheme),
    db: Session = Depends(get_db)
) -> User:
    
    access_token = auth.credentials
    
    payload = verify_token(access_token, "access")

    email: str = payload.get("sub")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="토큰에 사용자 정보가 없습니다.",
        )

    user = get_user_by_email(db, email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="존재하지 않는 사용자입니다.",
        )

    return user
